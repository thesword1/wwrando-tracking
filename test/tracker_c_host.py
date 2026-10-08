# Builds the tracker C runtime (asm/tracker/) for the host and wraps it with ctypes, with game
# memory mocked by a RAM buffer inside the library. Used by the test_tracker_c*.py tests.

import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACKER_C_DIR = REPO_ROOT / "asm" / "tracker"

RAM_BASE = 0x80000000
RAM_SIZE = 0x01800000


class TrkLocation(ctypes.Structure):
  _fields_ = [
    ("group_id", ctypes.c_uint8), ("type", ctypes.c_uint8), ("stage_id", ctypes.c_uint8), ("mask", ctypes.c_uint8),
    ("address", ctypes.c_uint32), ("name", ctypes.c_uint16), ("special", ctypes.c_uint8), ("flags", ctypes.c_uint8),
  ]

class TrkGroup(ctypes.Structure):
  _fields_ = [
    ("id", ctypes.c_uint8), ("kind", ctypes.c_uint8), ("first_location", ctypes.c_uint16),
    ("num_locations", ctypes.c_uint16), ("name", ctypes.c_uint16),
  ]

class TrkEntrance(ctypes.Structure):
  _fields_ = [
    ("island_number", ctypes.c_uint8), ("parent_group", ctypes.c_uint8), ("exit_group", ctypes.c_uint8),
    ("category", ctypes.c_uint8), ("entrance_name", ctypes.c_uint16), ("exit_name", ctypes.c_uint16),
  ]

class TrkTrigger(ctypes.Structure):
  _fields_ = [
    ("stage_name", ctypes.c_char * 8), ("room", ctypes.c_uint8), ("spawn", ctypes.c_uint8),
    ("entrance_index", ctypes.c_uint8),
  ]

class TrkChart(ctypes.Structure):
  _fields_ = [
    ("destination_square", ctypes.c_uint8), ("vanilla_square", ctypes.c_uint8), ("chart_number", ctypes.c_uint8),
    ("item_id", ctypes.c_uint8), ("owned_offset", ctypes.c_uint8), ("owned_mask", ctypes.c_uint8),
    ("salvaged_offset", ctypes.c_uint8), ("salvaged_mask", ctypes.c_uint8), ("name", ctypes.c_uint16),
  ]


def build_host_library(build_dir: Path) -> Path:
  if shutil.which("make") is None or shutil.which("gcc") is None:
    pytest.skip("make and gcc are needed to build the tracker C runtime for the host")
  subprocess.run(
    ["make", "-C", str(TRACKER_C_DIR), "host", f"BUILD_DIR={build_dir}", "CC=gcc"],
    check=True, capture_output=True, text=True,
  )
  return build_dir / "libtracker_host.so"


class TrackerHost:
  def __init__(self, library_path: Path):
    self.lib = ctypes.CDLL(str(library_path))
    lib = self.lib
    lib.trk_host_ram_base.restype = ctypes.c_void_p
    lib.trk_host_set_data.argtypes = [ctypes.c_char_p]
    lib.trk_tables_valid.restype = ctypes.c_bool
    lib.trk_seed_tag.restype = ctypes.c_uint16
    lib.trk_table_flags.restype = ctypes.c_uint16
    lib.trk_count.restype = ctypes.c_uint16
    lib.trk_count.argtypes = [ctypes.c_int]
    lib.trk_string.restype = ctypes.c_char_p
    lib.trk_string.argtypes = [ctypes.c_uint16]
    lib.trk_find_group.argtypes = [ctypes.c_uint8]
    for name, struct_type in [
      ("trk_get_location", TrkLocation), ("trk_get_group", TrkGroup), ("trk_get_entrance", TrkEntrance),
      ("trk_get_trigger", TrkTrigger), ("trk_get_chart", TrkChart),
    ]:
      getattr(lib, name).argtypes = [ctypes.c_uint16, ctypes.POINTER(struct_type)]
    self._data = None
    self.ram_base = lib.trk_host_ram_base()

  def set_tables(self, blob: bytes):
    # Keep a reference so the buffer outlives the C pointer to it.
    self._data = ctypes.create_string_buffer(blob, len(blob))
    self.lib.trk_host_set_data(self._data)

  def reset_ram(self):
    self.lib.trk_host_reset_ram()

  def _ram_offset(self, address: int, size: int) -> int:
    assert RAM_BASE <= address and address + size <= RAM_BASE + RAM_SIZE, f"{address:08X}"
    return self.ram_base + address - RAM_BASE

  def write_bytes(self, address: int, data: bytes):
    ctypes.memmove(self._ram_offset(address, len(data)), data, len(data))

  def read_bytes(self, address: int, size: int) -> bytes:
    return ctypes.string_at(self._ram_offset(address, size), size)

  def write_u8(self, address: int, value: int):
    self.write_bytes(address, bytes([value]))

  def read_u8(self, address: int) -> int:
    return self.read_bytes(address, 1)[0]

  def write_u16(self, address: int, value: int):
    self.write_bytes(address, value.to_bytes(2, "big"))

  def get(self, name: str, struct_type, index: int):
    out = struct_type()
    getattr(self.lib, name)(index, ctypes.byref(out))
    return out

  def string(self, offset: int) -> str:
    return self.lib.trk_string(offset).decode("ascii")
