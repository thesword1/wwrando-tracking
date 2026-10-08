"""
Read/write access to the emulated GameCube RAM of a running Dolphin process.

Dolphin keeps the emulated memory in a shared memory object (/dev/shm/dolphin-emu.<pid>).
We locate the mapping of MEM1 in /proc/<pid>/maps and access it through /proc/<pid>/mem,
which requires that the harness may ptrace Dolphin (same user and
/proc/sys/kernel/yama/ptrace_scope <= 1 with Dolphin being a descendant of the harness,
or ptrace_scope == 0). This works through the flatpak sandbox because the sandboxed
process still belongs to the same user.

Unlike dolphin-memory-engine (which hooks the first process named dolphin-emu it finds),
this targets one specific PID, so it never touches another Dolphin instance the user may
have open.
"""

import struct
from pathlib import Path

MEM1_START = 0x80000000
MEM1_SIZE = 0x01800000


class DolphinMemoryError(Exception):
  pass


def find_mem1_host_address(pid: int) -> int:
  maps_path = Path(f"/proc/{pid}/maps")
  try:
    lines = maps_path.read_text().splitlines()
  except OSError as e:
    raise DolphinMemoryError(f"Could not read {maps_path}: {e}") from e

  for line in lines:
    parts = line.split(maxsplit=5)
    if len(parts) < 6:
      continue
    addr_range, _perms, offset, _dev, _inode, path = parts
    if "dolphin-emu." not in path and "dolphinmem" not in path:
      continue
    if int(offset, 16) != 0:
      continue
    start, end = (int(x, 16) for x in addr_range.split("-"))
    if end - start >= MEM1_SIZE:
      return start

  raise DolphinMemoryError(f"No emulated RAM mapping found in process {pid}. Is a game running?")


class DolphinMemory:
  def __init__(self, pid: int):
    self.pid = pid
    self.host_base = find_mem1_host_address(pid)
    try:
      self._mem = open(f"/proc/{pid}/mem", "r+b", buffering=0)
    except OSError as e:
      raise DolphinMemoryError(
        f"Could not open /proc/{pid}/mem ({e}). "
        "Check /proc/sys/kernel/yama/ptrace_scope (must allow ptrace of this process)."
      ) from e

  def close(self):
    self._mem.close()

  def _host_address(self, address: int, size: int) -> int:
    # Accept cached (0x8...) and uncached (0xC...) virtual addresses.
    offset = (address & 0x3FFFFFFF) if (address & 0xFE000000) in (0x80000000, 0xC0000000) else -1
    if offset < 0 or offset + size > MEM1_SIZE:
      raise DolphinMemoryError(f"Address range 0x{address:08X}+0x{size:X} is outside of MEM1")
    return self.host_base + offset

  def read_bytes(self, address: int, size: int) -> bytes:
    self._mem.seek(self._host_address(address, size))
    data = self._mem.read(size)
    if len(data) != size:
      raise DolphinMemoryError(f"Short read at 0x{address:08X}")
    return data

  def write_bytes(self, address: int, data: bytes):
    self._mem.seek(self._host_address(address, len(data)))
    self._mem.write(data)

  def _read(self, fmt: str, address: int):
    return struct.unpack(fmt, self.read_bytes(address, struct.calcsize(fmt)))[0]

  def _write(self, fmt: str, address: int, value):
    self.write_bytes(address, struct.pack(fmt, value))

  def read_u8(self, address: int) -> int: return self._read(">B", address)
  def read_u16(self, address: int) -> int: return self._read(">H", address)
  def read_u32(self, address: int) -> int: return self._read(">I", address)
  def read_s8(self, address: int) -> int: return self._read(">b", address)
  def read_s16(self, address: int) -> int: return self._read(">h", address)
  def read_s32(self, address: int) -> int: return self._read(">i", address)
  def read_f32(self, address: int) -> float: return self._read(">f", address)

  def write_u8(self, address: int, value: int): self._write(">B", address, value)
  def write_u16(self, address: int, value: int): self._write(">H", address, value)
  def write_u32(self, address: int, value: int): self._write(">I", address, value)
  def write_s8(self, address: int, value: int): self._write(">b", address, value)
  def write_s16(self, address: int, value: int): self._write(">h", address, value)
  def write_s32(self, address: int, value: int): self._write(">i", address, value)
  def write_f32(self, address: int, value: float): self._write(">f", address, value)

  def read_cstring(self, address: int, max_length: int = 0x100) -> str:
    data = self.read_bytes(address, max_length)
    return data.split(b"\0", 1)[0].decode("shift_jis", errors="replace")
