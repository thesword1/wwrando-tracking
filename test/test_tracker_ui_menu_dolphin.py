# In-game test of the tracker's pages on the dungeon map and the Quest Status screen
# (asm/tracker/tracker_ui_menu.c). Builds AP-mode ISOs of the entrance_rando fixture that boot straight into
# Forbidden Woods, the Savage Labyrinth (a secret cave behind a randomized entrance, so it's its own group) and the
# sea, and checks through the UI state in RAM that Z opens the current group's list there, that X marks, and that
# B/Z close it again without reaching the menu. Screenshots are printed (run with -s); set
# WW_TRACKER_SCREENSHOT_DIR to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin. WW_TRACKER_DOLPHIN_CACHE keeps
# the built ISOs and in-game savestates.

import struct
import time
from pathlib import Path

import pytest

from test_aptww_fixtures import load_plando
from test_tracker_dolphin import (
  CUSTOM_SYMBOLS, FIXTURE, build_tracker_iso, make_cache_dir, pytestmark, read_state,  # noqa: F401
)
from test_tracker_serialize import tables_from_plando
from test_tracker_ui_dolphin import PAGE_GROUP, PAGE_GROUPS, PAGE_NONE, TOGGLE_MARKED, SAVE_MANUAL_ADDR, keep_screenshot, run_dolphin

FW_SPAWN = "kindan,0,0"
CAVE_SPAWN = "Cave09,0,0"
SEA_SPAWN = "sea,44,0"

# TrkUiState up to menu (asm/tracker/tracker_ui.h).
UI_STATE_FORMAT = ">IIBBBBbBBBBBBBIB"
MENU_DMAP, MENU_COLLECT = 2, 3


def read_ui_state(memory) -> dict:
  data = memory.read_bytes(CUSTOM_SYMBOLS["tracker_ui_state"], struct.calcsize(UI_STATE_FORMAT))
  names = [
    "proc_frame", "draw_frame", "view", "list_group", "sel", "scroll", "stick_dir", "stick_timer", "flash_timer", "last_toggle",
    "page", "page_sel", "page_scroll", "page_group", "collect_draw_frame", "menu",
  ]
  return dict(zip(names, struct.unpack(UI_STATE_FORMAT, data)))

def menu_open(memory, menu: int) -> bool:
  ui = read_ui_state(memory)
  return ui["menu"] == menu and read_state(memory)["frame_count"] - ui["proc_frame"] <= 2

def page_drawn(memory) -> bool:
  return read_state(memory)["frame_count"] - read_ui_state(memory)["draw_frame"] <= 2


TABLES = tables_from_plando(load_plando(FIXTURE))
GROUPS = TABLES.groups()

def group_index(name: str) -> int:
  return next(i for i, g in enumerate(GROUPS) if g.name == name)

def page_list() -> list[int]:
  return [i for i, g in enumerate(GROUPS) if g.id >= 50 and TABLES.location_set.locations_in_group(g)]


def spawn_dolphin(spawn: str, tmp_path_factory, tmp_path: Path):
  cache_dir = make_cache_dir(tmp_path_factory, FIXTURE, spawn)
  iso = build_tracker_iso(cache_dir, FIXTURE, spawn)
  return run_dolphin(iso, cache_dir, tmp_path / "dolphin-user")


def open_menu(dolphin, buttons: list[str], menu: int, message: str):
  """Presses the buttons until the menu is open. Right after booting into a stage, the stage's title card blocks
  the menus for a while."""
  deadline = time.monotonic() + 20
  while True:
    for button in buttons:
      dolphin.pad.press(button)
      time.sleep(1.5)
    if menu_open(dolphin.memory, menu):
      break
    assert time.monotonic() < deadline, message
    # Close whatever opened instead.
    dolphin.pad.press("B")
    time.sleep(1.5)
  time.sleep(0.5)


def mark_first(dolphin, group: int):
  loc = TABLES.location_set.locations_in_group(GROUPS[group])[0]
  bit_addr, mask = SAVE_MANUAL_ADDR + loc.index // 8, 1 << (loc.index % 8)
  dolphin.pad.press("X")
  dolphin.wait_for(lambda memory: memory.read_u8(bit_addr) & mask, timeout=5, message="X didn't mark the location")
  assert read_ui_state(dolphin.memory)["last_toggle"] == TOGGLE_MARKED


def test_dungeon_map(tmp_path_factory, tmp_path):
  dolphin = spawn_dolphin(FW_SPAWN, tmp_path_factory, tmp_path)
  try:
    memory = dolphin.memory
    ui = lambda: read_ui_state(memory)
    fw = group_index("Forbidden Woods")
    open_menu(dolphin, ["D_UP"], MENU_DMAP, "The dungeon map didn't open")
    assert not page_drawn(memory)
    keep_screenshot(dolphin.screenshot(), "dmap")

    # Z opens Forbidden Woods' list.
    dolphin.pad.press("Z")
    dolphin.wait_for(
      lambda memory: (state := ui())["page"] == PAGE_GROUP and state["page_group"] == fw and page_drawn(memory), timeout=5,
      message="Z didn't open Forbidden Woods' list",
    )
    keep_screenshot(dolphin.screenshot(), "dmap-fw-list")
    mark_first(dolphin, fw)
    keep_screenshot(dolphin.screenshot(), "dmap-fw-list-marked")

    # The map's close buttons only reach the tracker: D-pad Down does nothing, B goes to the list page.
    dolphin.pad.press("D_DOWN")
    time.sleep(0.5)
    assert ui()["page"] == PAGE_GROUP and menu_open(memory, MENU_DMAP)
    dolphin.pad.press("B")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS, timeout=5, message="B didn't go to the list page")
    assert page_list()[ui()["page_sel"]] == fw
    time.sleep(0.3)
    assert menu_open(memory, MENU_DMAP)
    keep_screenshot(dolphin.screenshot(), "dmap-list-page")
    dolphin.pad.press("B")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="B didn't close the page")
    time.sleep(0.5)
    assert menu_open(memory, MENU_DMAP) and not page_drawn(memory)

    # Z closes the list too, and then B closes the map as usual.
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUP, timeout=5, message="Z didn't open the list again")
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="Z didn't close the list")
    dolphin.pad.press("B")
    time.sleep(1.5)
    assert not menu_open(memory, MENU_DMAP)
  finally:
    dolphin.stop()


def open_quest_status(dolphin):
  open_menu(dolphin, ["START", "R"], MENU_COLLECT, "Quest Status didn't open")


def test_quest_status_in_cave(tmp_path_factory, tmp_path):
  dolphin = spawn_dolphin(CAVE_SPAWN, tmp_path_factory, tmp_path)
  try:
    memory = dolphin.memory
    ui = lambda: read_ui_state(memory)
    savage = group_index("Savage Labyrinth")
    open_quest_status(dolphin)
    keep_screenshot(dolphin.screenshot(), "collect")

    dolphin.pad.press("Z")
    dolphin.wait_for(
      lambda memory: (state := ui())["page"] == PAGE_GROUP and state["page_group"] == savage and page_drawn(memory), timeout=5,
      message="Z didn't open the Savage Labyrinth's list",
    )
    keep_screenshot(dolphin.screenshot(), "collect-cave-list")
    mark_first(dolphin, savage)

    # Start and R don't reach the pause menu while the list is shown.
    dolphin.pad.press("START")
    dolphin.pad.press("R")
    time.sleep(1)
    assert ui()["page"] == PAGE_GROUP and menu_open(memory, MENU_COLLECT)
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="Z didn't close the list")
    time.sleep(0.5)
    assert menu_open(memory, MENU_COLLECT)
    dolphin.pad.press("B")
    time.sleep(1.5)
    assert not menu_open(memory, MENU_COLLECT)
  finally:
    dolphin.stop()


def test_quest_status_on_sea(tmp_path_factory, tmp_path):
  # The sea isn't one group: Z opens the list page.
  dolphin = spawn_dolphin(SEA_SPAWN, tmp_path_factory, tmp_path)
  try:
    memory = dolphin.memory
    ui = lambda: read_ui_state(memory)
    open_quest_status(dolphin)
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS and page_drawn(memory), timeout=5, message="Z didn't open the list page")
    keep_screenshot(dolphin.screenshot(), "collect-list-page")
    dolphin.pad.press("B")
    dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="B didn't close the page")
    time.sleep(0.5)
    assert menu_open(memory, MENU_COLLECT)
  finally:
    dolphin.stop()
