# In-game test of GO MODE (the goal slot of the tracker's logic, asm/tracker/tracker_logic.c, drawn by tracker_ui.c and
# tracker_ui_menu.c): boots the progression_all ISO, gives the items Ganondorf needs through the Archipelago give-item
# array (so through execItemGet) but one Triforce shard, checks that the sea chart doesn't show GO MODE, gives the last
# shard, and checks that the goal bit is set and GO MODE is drawn on the sea chart and on the Quest Status screen.
# Screenshots are printed (run with -s); set WW_TRACKER_SCREENSHOT_DIR to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin. WW_TRACKER_DOLPHIN_CACHE keeps the
# built ISO and an in-game savestate.

import time

from test_tracker_dolphin import CUSTOM_SYMBOLS, pytestmark, read_state  # noqa: F401
from test_tracker_ui_dolphin import dolphin, keep_screenshot, read_ui_state, ui_cache_dir, ui_iso  # noqa: F401 (fixtures)

# TrkState.goal_in_logic (asm/tracker/tracker_state.h).
GOAL_IN_LOGIC_OFFSET = 0x16C

# Everything "Can Reach and Defeat Ganondorf" needs in this seed (no required bosses), as item IDs given one at a time
# so that progressive items count up.
GOAL_ITEMS = [
  0x31, 0x2D, 0x34, 0x25, 0x2F, 0x33,  # Bombs, Boomerang, Deku Leaf, Grappling Hook, Hookshot, Skull Hammer
  0x27, 0x27, 0x27,  # Progressive Bow x3 (Light Arrows)
  0x38, 0x38, 0x38, 0x38,  # Progressive Sword x4
  0x3B, 0xB1,  # Progressive Shield, Progressive Magic Meter
  0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67,  # Triforce Shards 1-7
]
LAST_SHARD = 0x68


def goal_in_logic(memory) -> bool:
  return memory.read_u8(CUSTOM_SYMBOLS["tracker_state"] + GOAL_IN_LOGIC_OFFSET) == 1

def is_drawing_go_mode(memory) -> bool:
  return read_state(memory)["frame_count"] - read_ui_state(memory)["go_mode_frame"] <= 2

def is_drawing(memory) -> bool:
  return read_state(memory)["frame_count"] - read_ui_state(memory)["draw_frame"] <= 2

def give(dolphin, item_id: int):
  give_array = CUSTOM_SYMBOLS["give_archipelago_item_array"]
  dolphin.memory.write_u8(give_array, item_id)
  dolphin.wait_for(lambda memory: memory.read_u8(give_array) == 0xFF, timeout=10, message=f"Item 0x{item_id:02X} was not given")
  time.sleep(0.2)

def evaluations(memory) -> int:
  return memory.read_u32(CUSTOM_SYMBOLS["tracker_state"] + 0xA0)


def test_go_mode(dolphin):
  memory = dolphin.memory
  assert not goal_in_logic(memory)
  for item_id in GOAL_ITEMS:
    give(dolphin, item_id)
  # The magic meter fills up gradually; the evaluation runs 30 frames after the last item get.
  time.sleep(3)
  assert not goal_in_logic(memory)

  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing, timeout=10, message="The tracker isn't drawn on the sea chart")
  time.sleep(1.5)
  assert not is_drawing_go_mode(memory)
  keep_screenshot(dolphin.screenshot(), "go-mode-not-yet")
  dolphin.pad.press("B")
  time.sleep(2)

  evals = evaluations(memory)
  give(dolphin, LAST_SHARD)
  dolphin.wait_for(lambda memory: evaluations(memory) > evals, timeout=5, message="The item get didn't re-evaluate")
  assert goal_in_logic(memory)

  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing_go_mode, timeout=10, message="GO MODE isn't drawn on the sea chart")
  time.sleep(1.5)
  keep_screenshot(dolphin.screenshot(), "go-mode-chart")
  dolphin.pad.press("B")
  time.sleep(2)
  assert not is_drawing_go_mode(memory)

  # Quest Status: under the "Z: tracker" hint.
  dolphin.pad.press("START")
  time.sleep(1.5)
  dolphin.pad.press("R")
  dolphin.wait_for(is_drawing_go_mode, timeout=10, message="GO MODE isn't drawn on the Quest Status screen")
  time.sleep(1)
  keep_screenshot(dolphin.screenshot(), "go-mode-collect")
  dolphin.pad.press("START")
  time.sleep(2)
  assert not is_drawing_go_mode(memory)
