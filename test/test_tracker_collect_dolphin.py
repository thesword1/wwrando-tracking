# In-game test of the Triforce shard counter on the Quest Status screen (asm/tracker/tracker_collect.c):
# opens the pause menu's Quest Status screen, sets the owned shards in RAM to 0, 3 and 8 and checks
# through the UI state in RAM that the counter is drawn, then that it isn't drawn over the options
# window or after the menu is closed. Screenshots are printed (run with -s) for a human to look at; set
# WW_TRACKER_SCREENSHOT_DIR to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin.
# WW_TRACKER_DOLPHIN_CACHE keeps the built ISO and an in-game savestate.

import time

from test_tracker_dolphin import pytestmark, read_state  # noqa: F401
from test_tracker_ui_dolphin import er_cache_dir, er_dolphin, er_iso, keep_screenshot, read_ui_state  # noqa: F401 (fixtures)

TRIFORCE_ADDR = 0x803C4CC6


def is_drawing_counter(memory) -> bool:
  return read_state(memory)["frame_count"] - read_ui_state(memory)["collect_draw_frame"] <= 2


def test_triforce_counter(er_dolphin):
  dolphin = er_dolphin
  memory = dolphin.memory
  assert not is_drawing_counter(memory)

  dolphin.pad.press("START")
  time.sleep(1.5)
  dolphin.pad.press("R")  # Quest Status
  dolphin.wait_for(is_drawing_counter, timeout=10, message="The Triforce counter isn't drawn on the Quest Status screen")
  time.sleep(1)

  for shards, bits in [(0, 0x00), (3, 0x25), (8, 0xFF)]:
    memory.write_u8(TRIFORCE_ADDR, bits)
    time.sleep(0.5)
    assert is_drawing_counter(memory)
    keep_screenshot(dolphin.screenshot(), f"triforce-{shards}")

  # Not drawn over the options window (the cursor starts on the Triforce; Options is below it).
  dolphin.pad.tilt(0, -1, duration=0.15)
  time.sleep(0.3)
  dolphin.pad.press("A")
  time.sleep(1.5)
  assert not is_drawing_counter(memory)
  keep_screenshot(dolphin.screenshot(), "triforce-options")
  dolphin.pad.press("B")
  dolphin.wait_for(is_drawing_counter, timeout=5, message="The counter isn't drawn again after closing the options")

  # Closing the pause menu stops the drawing.
  dolphin.pad.press("START")
  time.sleep(2)
  assert not is_drawing_counter(memory)
