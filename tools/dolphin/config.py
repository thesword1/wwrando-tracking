"""
Writes the config files of an isolated Dolphin user directory used by the harness.

Only files inside the given user directory are touched; the user's own Dolphin
configuration (~/.var/app/org.DolphinEmu.dolphin-emu) is never read or modified.
"""

import os
from pathlib import Path

# Names of the FIFO files created in <user>/Pipes/. Dolphin exposes each one as an input
# device called "Pipe/0/<name>".
PAD_PIPE = "pad1"
HOTKEY_PIPES = ("hk_misc", "hk_save", "hk_load")

# The 12 buttons a Pipe device understands.
PIPE_BUTTONS = ("A", "B", "X", "Y", "Z", "START", "L", "R", "D_UP", "D_DOWN", "D_LEFT", "D_RIGHT")

# Hotkeys bound to buttons of the "hk_misc" pipe.
MISC_HOTKEYS = {
  "General/Take Screenshot": "A",
  "General/Toggle Pause": "B",
  "General/Frame Advance": "X",
  "Emulation Speed/Disable Emulation Speed Limit": "Y",
}
# Savestate slots 1-10 are bound to buttons of the "hk_save" / "hk_load" pipes in this order.
SLOT_BUTTONS = PIPE_BUTTONS[:10]

GC_PAD_MAPPING = {
  "Buttons/A": "`Button A`",
  "Buttons/B": "`Button B`",
  "Buttons/X": "`Button X`",
  "Buttons/Y": "`Button Y`",
  "Buttons/Z": "`Button Z`",
  "Buttons/Start": "`Button START`",
  "D-Pad/Up": "`Button D_UP`",
  "D-Pad/Down": "`Button D_DOWN`",
  "D-Pad/Left": "`Button D_LEFT`",
  "D-Pad/Right": "`Button D_RIGHT`",
  "Main Stick/Up": "`Axis MAIN Y -`",
  "Main Stick/Down": "`Axis MAIN Y +`",
  "Main Stick/Left": "`Axis MAIN X -`",
  "Main Stick/Right": "`Axis MAIN X +`",
  "C-Stick/Up": "`Axis C Y -`",
  "C-Stick/Down": "`Axis C Y +`",
  "C-Stick/Left": "`Axis C X -`",
  "C-Stick/Right": "`Axis C X +`",
  "Triggers/L": "`Button L`",
  "Triggers/R": "`Button R`",
  "Triggers/L-Analog": "`Axis L +`",
  "Triggers/R-Analog": "`Axis R +`",
}


def _write_ini(path: Path, sections: dict[str, dict[str, str]]):
  lines = []
  for section, values in sections.items():
    lines.append(f"[{section}]")
    for key, value in values.items():
      lines.append(f"{key} = {value}")
    lines.append("")
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text("\n".join(lines))


def _pipe_control(pipe: str, button: str) -> str:
  return f"`Pipe/0/{pipe}:Button {button}`"


def write_user_dir(
  user_dir: Path,
  *,
  video_backend: str = "Vulkan",
  unlimited_speed: bool = False,
  audio: bool = False,
  window_size: tuple[int, int] = (640, 528),
):
  user_dir = Path(user_dir)
  config_dir = user_dir / "Config"
  pipes_dir = user_dir / "Pipes"
  pipes_dir.mkdir(parents=True, exist_ok=True)

  # Dolphin only enumerates pipes at startup, so the FIFOs must exist before launch.
  for name in (PAD_PIPE,) + HOTKEY_PIPES:
    fifo = pipes_dir / name
    if fifo.exists() and not fifo.is_fifo():
      fifo.unlink()
    if not fifo.exists():
      os.mkfifo(fifo)

  _write_ini(config_dir / "Dolphin.ini", {
    "Core": {
      "GFXBackend": video_backend,
      "SkipIPL": "True",
      "SIDevice0": "6", # Standard controller
      "SIDevice1": "0",
      "SIDevice2": "0",
      "SIDevice3": "0",
      "EmulationSpeed": "0.0" if unlimited_speed else "1.0",
      "AutoDiscChange": "False",
    },
    "Interface": {
      "ConfirmStop": "False",
      "UsePanicHandlers": "False",
      "OnScreenDisplayMessages": "False",
      "PauseOnFocusLost": "False",
      "ShowActiveTitle": "True",
    },
    "Input": {
      # Hotkeys and pad input are otherwise ignored while the render window is unfocused.
      "BackgroundInput": "True",
    },
    "Display": {
      "Fullscreen": "False",
      "RenderToMain": "False",
      "RenderWindowWidth": str(window_size[0]),
      "RenderWindowHeight": str(window_size[1]),
      "RenderWindowAutoSize": "False",
      "KeepWindowOnTop": "False",
    },
    "DSP": {
      "Backend": "Cubeb" if audio else "No Audio Output",
    },
    "Analytics": {
      "PermissionAsked": "True",
      "Enabled": "False",
    },
    "AutoUpdate": {
      "UpdateTrack": "",
    },
    "General": {
      "ShowFrameCount": "False",
    },
  })

  _write_ini(config_dir / "GCPadNew.ini", {
    "GCPad1": {"Device": f"Pipe/0/{PAD_PIPE}", **GC_PAD_MAPPING},
  })

  hotkeys = {"Device": f"Pipe/0/{HOTKEY_PIPES[0]}"}
  for name, button in MISC_HOTKEYS.items():
    hotkeys[name] = _pipe_control("hk_misc", button)
  for i, button in enumerate(SLOT_BUTTONS):
    hotkeys[f"Save State/Save State Slot {i+1}"] = _pipe_control("hk_save", button)
    hotkeys[f"Load State/Load State Slot {i+1}"] = _pipe_control("hk_load", button)
  _write_ini(config_dir / "Hotkeys.ini", {"Hotkeys": hotkeys})

  _write_ini(config_dir / "GFX.ini", {
    "Settings": {
      "InternalResolution": "1",
      "ShowFPS": "False",
    },
  })
