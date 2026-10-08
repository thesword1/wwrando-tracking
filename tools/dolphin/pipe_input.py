"""
Scripted input through Dolphin's "Pipe" input backend.

Each FIFO in <user>/Pipes/ is an input device that accepts newline-terminated commands:
  PRESS <button> / RELEASE <button>   buttons: A B X Y Z START L R D_UP D_DOWN D_LEFT D_RIGHT
  SET <L|R> <0..1>                    analog triggers
  SET <MAIN|C> <x 0..1> <y 0..1>      sticks, 0.5 0.5 is neutral
Dolphin polls the pipes once per input update (about once per frame), so a press has to be
held for a couple of frames to be seen by the game.
"""

import errno
import os
import time

from .config import PIPE_BUTTONS

# Friendlier aliases for the D-pad.
BUTTON_ALIASES = {
  "UP": "D_UP", "DOWN": "D_DOWN", "LEFT": "D_LEFT", "RIGHT": "D_RIGHT",
  "DPAD_UP": "D_UP", "DPAD_DOWN": "D_DOWN", "DPAD_LEFT": "D_LEFT", "DPAD_RIGHT": "D_RIGHT",
}

DEFAULT_PRESS_TIME = 0.1 # About 6 frames at full speed.


class PipeWriter:
  def __init__(self, path, timeout: float = 30.0):
    self.path = path
    # Opening a FIFO for writing with O_NONBLOCK fails with ENXIO until Dolphin has opened
    # the read end, which happens when the input backend is initialized.
    deadline = time.monotonic() + timeout
    while True:
      try:
        self.fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        break
      except OSError as e:
        if e.errno != errno.ENXIO or time.monotonic() > deadline:
          raise
        time.sleep(0.1)
    os.set_blocking(self.fd, True)

  def send(self, *commands: str):
    os.write(self.fd, "".join(f"{c}\n" for c in commands).encode("ascii"))

  def close(self):
    os.close(self.fd)


def _button(name: str) -> str:
  name = name.upper()
  name = BUTTON_ALIASES.get(name, name)
  if name not in PIPE_BUTTONS:
    raise ValueError(f"Unknown button {name!r}")
  return name


class PipeController:
  """Emulated GameCube controller in port 1."""

  def __init__(self, path, timeout: float = 30.0):
    self.pipe = PipeWriter(path, timeout)

  def close(self):
    self.pipe.close()

  def hold(self, *buttons: str):
    self.pipe.send(*(f"PRESS {_button(b)}" for b in buttons))

  def release(self, *buttons: str):
    self.pipe.send(*(f"RELEASE {_button(b)}" for b in buttons))

  def press(self, *buttons: str, duration: float = DEFAULT_PRESS_TIME, after: float = DEFAULT_PRESS_TIME):
    """Press the buttons together, hold them for duration seconds, then wait after seconds."""
    self.hold(*buttons)
    time.sleep(duration)
    self.release(*buttons)
    time.sleep(after)

  def press_sequence(self, buttons, duration: float = DEFAULT_PRESS_TIME, after: float = DEFAULT_PRESS_TIME):
    for button in buttons:
      self.press(button, duration=duration, after=after)

  def set_main_stick(self, x: float, y: float):
    """x/y in -1..1; positive y is up."""
    self.pipe.send(f"SET MAIN {(x+1)/2:.4f} {(1-y)/2:.4f}")

  def set_c_stick(self, x: float, y: float):
    """x/y in -1..1; positive y is up."""
    self.pipe.send(f"SET C {(x+1)/2:.4f} {(1-y)/2:.4f}")

  def set_trigger(self, trigger: str, value: float):
    """Analog trigger (L or R) in 0..1. Use hold("L") for the digital click."""
    trigger = trigger.upper()
    if trigger not in ("L", "R"):
      raise ValueError(f"Unknown trigger {trigger!r}")
    self.pipe.send(f"SET {trigger} {value:.4f}")

  def tilt(self, x: float, y: float, duration: float, after: float = DEFAULT_PRESS_TIME):
    self.set_main_stick(x, y)
    time.sleep(duration)
    self.set_main_stick(0, 0)
    time.sleep(after)

  def reset(self):
    """Release everything and center the sticks."""
    self.pipe.send(
      *(f"RELEASE {b}" for b in PIPE_BUTTONS),
      "SET MAIN 0.5 0.5", "SET C 0.5 0.5", "SET L 0", "SET R 0",
    )
