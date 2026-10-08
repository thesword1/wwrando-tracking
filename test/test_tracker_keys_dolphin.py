# In-game test of the dungeon key counts in a dungeon's location list header (tracker_ui.c, trk_draw_keys): gives
# Dragon Roost Cavern small keys and then its big key through the Archipelago give-item array (so through execItemGet
# and the tracker's small key counters), and opens its list from the sea chart's list page; then opens Forbidden
# Woods' list from the dungeon map after getting its small key there. The text itself is host-tested
# (test_tracker_ui.py); these are for the screenshots, which are printed (run with -s); set WW_TRACKER_SCREENSHOT_DIR
# to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin. WW_TRACKER_DOLPHIN_CACHE keeps the
# built ISOs and in-game savestates.

import time

from test_tracker_dolphin import CUSTOM_SYMBOLS, SAVE_KEYS_ADDR, pytestmark, read_state  # noqa: F401
from test_tracker_ui_dolphin import (  # noqa: F401 (fixtures)
  PAGE_GROUP, PAGE_GROUPS, PAGE_NONE, er_cache_dir, er_dolphin, er_iso, keep_screenshot, read_ui_state,
)
from test_tracker_ui_menu_dolphin import FW_SPAWN, MENU_DMAP, group_index, open_menu, page_drawn, spawn_dolphin

DRC_SMALL_KEY, DRC_BIG_KEY, FW_SMALL_KEY = 0x13, 0x14, 0x1D
DRC_SAVED_DUNGEON_ITEM_ADDR = 0x803C4F88 + 0x24*3 + 0x21


def give(dolphin, item_id: int):
  give_array = CUSTOM_SYMBOLS["give_archipelago_item_array"]
  dolphin.memory.write_u8(give_array, item_id)
  dolphin.wait_for(lambda memory: memory.read_u8(give_array) == 0xFF, timeout=10, message=f"Item 0x{item_id:02X} was not given")
  time.sleep(0.3)

def open_drc_list(dolphin, drc: int):
  ui = lambda: read_ui_state(dolphin.memory)
  dolphin.pad.press("D_UP")
  dolphin.wait_for(page_drawn, timeout=10, message="The tracker doesn't draw on the sea chart")
  time.sleep(1)
  dolphin.pad.press("Z")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS, timeout=5, message="Z didn't open the list page")
  assert ui()["page_sel"] == 0  # Dragon Roost Cavern, the first group
  dolphin.pad.press("A")
  dolphin.wait_for(
    lambda memory: (state := ui())["page"] == PAGE_GROUP and state["page_group"] == drc and page_drawn(memory),
    timeout=5, message="A didn't open Dragon Roost Cavern's list",
  )
  time.sleep(0.5)

def close_chart(dolphin):
  ui = lambda: read_ui_state(dolphin.memory)
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS, timeout=5, message="B didn't go back to the list page")
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="B didn't close the list page")
  dolphin.pad.press("B")
  time.sleep(2)


def test_keys_on_chart(er_dolphin):
  dolphin = er_dolphin
  memory = dolphin.memory
  drc = group_index("Dragon Roost Cavern")
  give(dolphin, DRC_SMALL_KEY)
  give(dolphin, DRC_SMALL_KEY)
  assert memory.read_u8(SAVE_KEYS_ADDR) == 2
  assert not memory.read_u8(DRC_SAVED_DUNGEON_ITEM_ADDR) & 0x04
  open_drc_list(dolphin, drc)
  keep_screenshot(dolphin.screenshot(), "keys-drc")  # Keys 2/4, BK struck through
  close_chart(dolphin)

  give(dolphin, DRC_BIG_KEY)
  assert memory.read_u8(DRC_SAVED_DUNGEON_ITEM_ADDR) & 0x04
  open_drc_list(dolphin, drc)
  keep_screenshot(dolphin.screenshot(), "keys-drc-bk")  # Keys 2/4, BK owned


def test_keys_on_dungeon_map(tmp_path_factory, tmp_path):
  dolphin = spawn_dolphin(FW_SPAWN, tmp_path_factory, tmp_path)
  try:
    memory = dolphin.memory
    fw = group_index("Forbidden Woods")
    give(dolphin, FW_SMALL_KEY)
    assert memory.read_u8(SAVE_KEYS_ADDR + 1) == 1
    open_menu(dolphin, ["D_UP"], MENU_DMAP, "The dungeon map didn't open")
    dolphin.pad.press("Z")
    dolphin.wait_for(
      lambda memory: (state := read_ui_state(memory))["page"] == PAGE_GROUP and state["page_group"] == fw
      and page_drawn(memory), timeout=5, message="Z didn't open Forbidden Woods' list",
    )
    time.sleep(0.5)
    keep_screenshot(dolphin.screenshot(), "keys-dmap-fw")  # Keys 1/1 (all: grey), BK struck through
    dolphin.pad.press("Z")
    time.sleep(0.5)
  finally:
    dolphin.stop()
