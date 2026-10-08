"""
Launches the flatpak build of Dolphin with an isolated user directory and exposes scripted
input, RAM access, screenshots and savestates. See docs/dev/dolphin-harness.md.
"""

import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from . import config
from .memory import DolphinMemory, DolphinMemoryError
from .pipe_input import PipeController, PipeWriter, DEFAULT_PRESS_TIME

FLATPAK_APP_ID = "org.DolphinEmu.dolphin-emu"


class DolphinError(Exception):
  pass


def _wait_until(predicate, timeout: float, interval: float = 0.1, message: str = "Timed out"):
  deadline = time.monotonic() + timeout
  while True:
    result = predicate()
    if result:
      return result
    if time.monotonic() > deadline:
      raise DolphinError(message)
    time.sleep(interval)


def _find_dolphin_pid(user_dir: Path) -> int | None:
  """Host PID of the dolphin-emu process that was started with this user directory."""
  for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
      continue
    try:
      if (proc / "comm").read_text().strip() != "dolphin-emu":
        continue
      args = (proc / "cmdline").read_bytes().split(b"\0")
    except OSError:
      continue
    if str(user_dir).encode() in args:
      return int(proc.name)
  return None


class Dolphin:
  """
  Usage:
    with Dolphin(iso_path) as dolphin:
      dolphin.wait_for_game_id("GZLE01")
      dolphin.pad.press("START")
      print(dolphin.screenshot())
  """

  def __init__(
    self,
    iso_path,
    user_dir=None,
    *,
    video_backend: str = "Vulkan",
    unlimited_speed: bool = False,
    audio: bool = False,
    batch: bool = True,
    initial_save_state=None,
    extra_config: dict[str, str] | None = None,
    flatpak_app_id: str = FLATPAK_APP_ID,
  ):
    self.iso_path = Path(iso_path).resolve()
    if user_dir is None:
      user_dir = tempfile.mkdtemp(prefix="dolphin-user-")
    self.user_dir = Path(user_dir).resolve()
    self.video_backend = video_backend
    self.unlimited_speed = unlimited_speed
    self.audio = audio
    self.batch = batch
    self.initial_save_state = Path(initial_save_state).resolve() if initial_save_state else None
    # Passed as -C System.Section.Key=Value, e.g. {"Dolphin.Core.CPUThread": "False"}.
    self.extra_config = extra_config or {}
    self.flatpak_app_id = flatpak_app_id

    self.process: subprocess.Popen | None = None
    self.pid: int | None = None
    self.pad: PipeController | None = None
    self._hotkey_pipes: dict[str, PipeWriter] = {}
    self._memory: DolphinMemory | None = None
    self.log_path = self.user_dir / "harness-dolphin.log"

  # --- lifecycle ---

  def start(self, timeout: float = 60.0):
    if shutil.which("flatpak") is None:
      raise DolphinError("flatpak is not installed")
    config.write_user_dir(
      self.user_dir,
      video_backend=self.video_backend,
      unlimited_speed=self.unlimited_speed,
      audio=self.audio,
    )

    # The flatpak has read-only access to the host filesystem, but its /tmp is private, so
    # the user directory (and anything under /tmp) has to be exposed explicitly.
    cmd = ["flatpak", "run", f"--filesystem={self.user_dir}"]
    for path in (self.iso_path, self.initial_save_state):
      if path is not None:
        cmd.append(f"--filesystem={path.parent}:ro")
    cmd += [self.flatpak_app_id, "-u", str(self.user_dir), "-e", str(self.iso_path)]
    if self.batch:
      cmd.append("-b")
    if self.initial_save_state:
      cmd += ["-s", str(self.initial_save_state)]
    for key, value in self.extra_config.items():
      cmd += ["-C", f"{key}={value}"]

    with open(self.log_path, "wb") as log:
      self.process = subprocess.Popen(
        cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True,
      )

    def find_pid():
      if self.process.poll() is not None:
        raise DolphinError(f"Dolphin exited early, see {self.log_path}")
      return _find_dolphin_pid(self.user_dir)
    self.pid = _wait_until(find_pid, timeout, message="Dolphin process did not appear")

    pipes_dir = self.user_dir / "Pipes"
    self.pad = PipeController(pipes_dir / config.PAD_PIPE, timeout)
    for name in config.HOTKEY_PIPES:
      self._hotkey_pipes[name] = PipeWriter(pipes_dir / name, timeout)
    return self

  def stop(self, timeout: float = 15.0):
    """Ask Dolphin to quit (SIGTERM, which stops emulation cleanly) and kill it if it hangs."""
    for pipe in [self.pad, *self._hotkey_pipes.values()]:
      if pipe is not None:
        try:
          pipe.close()
        except OSError:
          pass
    self.pad = None
    self._hotkey_pipes = {}
    if self._memory is not None:
      self._memory.close()
      self._memory = None

    if self.pid is not None:
      try:
        os.kill(self.pid, signal.SIGTERM)
      except ProcessLookupError:
        pass
    if self.process is not None:
      try:
        self.process.wait(timeout)
      except subprocess.TimeoutExpired:
        if self.pid is not None:
          try:
            os.kill(self.pid, signal.SIGKILL)
          except ProcessLookupError:
            pass
        os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(5)
    self.process = None
    self.pid = None

  @property
  def running(self) -> bool:
    return self.process is not None and self.process.poll() is None

  def __enter__(self):
    return self.start()

  def __exit__(self, *exc):
    self.stop()

  # --- memory ---

  @property
  def memory(self) -> DolphinMemory:
    if self._memory is None:
      if self.pid is None:
        raise DolphinError("Dolphin is not running")
      self._memory = DolphinMemory(self.pid)
    return self._memory

  def wait_for_game_id(self, game_id: str = "GZLE01", timeout: float = 60.0):
    """Wait until the emulated RAM exists and holds the given game ID at 0x80000000."""
    def check():
      try:
        return self.memory.read_bytes(0x80000000, 6) == game_id.encode("ascii")
      except DolphinMemoryError:
        self._memory = None
        return False
    _wait_until(check, timeout, message=f"Game ID {game_id} not found in RAM")

  def wait_for(self, predicate, timeout: float = 30.0, interval: float = 0.05, message: str = "Timed out"):
    """Poll predicate(memory) until it returns a truthy value."""
    return _wait_until(lambda: predicate(self.memory), timeout, interval, message)

  # --- hotkeys ---

  def _hotkey(self, pipe: str, button: str, duration: float = DEFAULT_PRESS_TIME):
    writer = self._hotkey_pipes[pipe]
    writer.send(f"PRESS {button}")
    time.sleep(duration)
    writer.send(f"RELEASE {button}")

  def toggle_pause(self):
    self._hotkey("hk_misc", config.MISC_HOTKEYS["General/Toggle Pause"])

  def frame_advance(self):
    self._hotkey("hk_misc", config.MISC_HOTKEYS["General/Frame Advance"])

  def toggle_speed_limit(self):
    self._hotkey("hk_misc", config.MISC_HOTKEYS["Emulation Speed/Disable Emulation Speed Limit"])

  @property
  def screenshot_dir(self) -> Path:
    return self.user_dir / "ScreenShots"

  def screenshot(self, timeout: float = 10.0) -> Path:
    """Take a screenshot of the emulated output (no OSD/window chrome) and return its PNG path."""
    def snapshot():
      return {p: p.stat().st_mtime_ns for p in self.screenshot_dir.rglob("*.png")}
    before = snapshot()
    # Dolphin names screenshots after the current second; avoid overwriting the previous one.
    if before and time.time() - max(before.values()) / 1e9 < 1.1:
      time.sleep(1.1)
    self._hotkey("hk_misc", config.MISC_HOTKEYS["General/Take Screenshot"])

    def new_png():
      changed = [p for p, mtime in snapshot().items() if before.get(p) != mtime]
      return changed[0] if changed else None
    path = _wait_until(new_png, timeout, message="Screenshot was not written")
    # Wait until the PNG is completely written.
    _wait_until(lambda: path.stat().st_size > 0 and _png_complete(path), timeout, message="Screenshot incomplete")
    return path

  def _state_file(self, slot: int) -> Path:
    game_id = self.memory.read_bytes(0x80000000, 6).decode("ascii")
    return self.user_dir / "StateSaves" / f"{game_id}.s{slot:02d}"

  def save_state(self, slot: int = 1, timeout: float = 15.0) -> Path:
    if not 1 <= slot <= len(config.SLOT_BUTTONS):
      raise ValueError(f"Invalid savestate slot {slot}")
    path = self._state_file(slot)
    old_mtime = path.stat().st_mtime_ns if path.exists() else None
    self._hotkey("hk_save", config.SLOT_BUTTONS[slot-1])

    def written():
      if not path.exists() or path.stat().st_mtime_ns == old_mtime:
        return False
      # Savestates are compressed in a background thread; wait for the size to settle.
      size = path.stat().st_size
      time.sleep(0.3)
      return size > 0 and path.stat().st_size == size
    _wait_until(written, timeout, message=f"Savestate slot {slot} was not written")
    return path

  def load_state(self, slot: int = 1, settle: float = 0.5):
    if not 1 <= slot <= len(config.SLOT_BUTTONS):
      raise ValueError(f"Invalid savestate slot {slot}")
    if not self._state_file(slot).exists():
      raise DolphinError(f"Savestate slot {slot} does not exist")
    self._hotkey("hk_load", config.SLOT_BUTTONS[slot-1])
    time.sleep(settle)


def _png_complete(path: Path) -> bool:
  with open(path, "rb") as f:
    f.seek(-12, os.SEEK_END)
    return f.read(12)[4:8] == b"IEND"
