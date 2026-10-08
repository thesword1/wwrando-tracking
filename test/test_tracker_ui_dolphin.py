# In-game test of the tracker's sea chart UI (asm/tracker/tracker_ui.c): builds an AP-mode ISO with the
# tracker (progression_all fixture, so most sea squares have locations) that boots straight into
# gameplay on Outset, opens the sea chart with D-pad Up and checks through the UI state in RAM that the
# tracker draws on the chart's world view, and only there. Screenshots are printed (run with -s) for a
# human to look at; set WW_TRACKER_SCREENSHOT_DIR to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin. Like
# test_tracker_dolphin.py, WW_TRACKER_DOLPHIN_CACHE keeps the built ISO and an in-game savestate.

import os
import shutil
import struct
import time
from pathlib import Path

import pytest

from test_aptww_fixtures import FIXTURES_DIR, load_plando
from test_tracker_dolphin import (
  CUSTOM_SYMBOLS, FIXTURE as ENTRANCE_RANDO_FIXTURE, TRK_STATE_MAGIC, build_tracker_iso, make_cache_dir, pytestmark,  # noqa: F401
  read_state,
)
from test_tracker_serialize import tables_from_plando

FIXTURE = FIXTURES_DIR / "progression_all.aptww"
TEST_SPAWN = "sea,44,0"

UI_STATE_FORMAT = ">IIBBBBbBBBBBBB"
VIEW_NONE, VIEW_WORLD, VIEW_SQUARE = 0, 1, 2
PAGE_NONE, PAGE_GROUPS, PAGE_GROUP = 0, 1, 2
TOGGLE_MARKED, TOGGLE_UNMARKED, TOGGLE_REFUSED = 1, 2, 3

SAVE_ADDR = 0x803C532C
SAVE_SIZE = 0x50
SAVE_MANUAL_ADDR = SAVE_ADDR + 0x10
SAVE_VISITED_ADDR = SAVE_ADDR + 0x40


def read_ui_state(memory) -> dict:
  data = memory.read_bytes(CUSTOM_SYMBOLS["tracker_ui_state"], struct.calcsize(UI_STATE_FORMAT))
  names = [
    "proc_frame", "draw_frame", "view", "list_group", "sel", "scroll", "stick_dir", "stick_timer", "flash_timer", "last_toggle",
    "page", "page_sel", "page_scroll", "page_group",
  ]
  return dict(zip(names, struct.unpack(UI_STATE_FORMAT, data)))

def is_drawing(memory) -> bool:
  frame = read_state(memory)["frame_count"]
  return frame - read_ui_state(memory)["draw_frame"] <= 2

def keep_screenshot(path: Path, name: str) -> Path:
  print(f"Screenshot ({name}):", path)
  target_dir = os.environ.get("WW_TRACKER_SCREENSHOT_DIR")
  if target_dir:
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, Path(target_dir) / f"{name}.png")
  return path


@pytest.fixture(scope="module")
def ui_cache_dir(tmp_path_factory) -> Path:
  return make_cache_dir(tmp_path_factory, FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def ui_iso(ui_cache_dir: Path) -> Path:
  return build_tracker_iso(ui_cache_dir, FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def er_cache_dir(tmp_path_factory) -> Path:
  return make_cache_dir(tmp_path_factory, ENTRANCE_RANDO_FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def er_iso(er_cache_dir: Path) -> Path:
  return build_tracker_iso(er_cache_dir, ENTRANCE_RANDO_FIXTURE, TEST_SPAWN)

def run_dolphin(iso: Path, cache_dir: Path, user_dir: Path):
  """Boots the ISO into gameplay (or the cached in-game savestate)."""
  from tools.dolphin.harness import Dolphin

  savestate = cache_dir / "ingame.sav"
  dolphin = Dolphin(iso, user_dir, initial_save_state=savestate if savestate.exists() else None)
  dolphin.start()
  try:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    dolphin.wait_for(
      lambda memory: (state := read_state(memory))["magic"] == TRK_STATE_MAGIC and state["in_game"],
      timeout=90, message="Gameplay was not reached",
    )
    time.sleep(1)
    if not savestate.exists():
      shutil.copyfile(dolphin.save_state(1), savestate)
  except BaseException:
    dolphin.stop()
    raise
  return dolphin

@pytest.fixture
def dolphin(ui_iso: Path, ui_cache_dir: Path, tmp_path: Path):
  dolphin = run_dolphin(ui_iso, ui_cache_dir, tmp_path / "dolphin-user")
  try:
    yield dolphin
  finally:
    dolphin.stop()

@pytest.fixture
def er_dolphin(er_iso: Path, er_cache_dir: Path, tmp_path: Path):
  dolphin = run_dolphin(er_iso, er_cache_dir, tmp_path / "dolphin-user")
  try:
    yield dolphin
  finally:
    dolphin.stop()


def test_chart_overview(dolphin):
  memory = dolphin.memory
  assert not is_drawing(memory)

  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing, timeout=10, message="The tracker doesn't draw on the sea chart")
  assert read_ui_state(memory)["view"] == VIEW_WORLD
  keep_screenshot(dolphin.screenshot(), "chart-overview")

  # Counters follow manual marks.
  num_checked = read_state(memory)["num_checked"]
  memory.write_u8(SAVE_MANUAL_ADDR, 0xFF)
  dolphin.wait_for(lambda memory: read_state(memory)["num_checked"] == num_checked + 8, timeout=5, message="Marks not counted")
  keep_screenshot(dolphin.screenshot(), "chart-overview-marked")

  # The chart's own controls still work.
  dolphin.pad.press("A")
  dolphin.wait_for(lambda memory: read_ui_state(memory)["view"] == VIEW_SQUARE, timeout=5, message="A didn't zoom in")
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: read_ui_state(memory)["view"] == VIEW_WORLD, timeout=5, message="B didn't zoom back out")

  # Closing the chart stops the drawing.
  dolphin.pad.press("D_DOWN")
  time.sleep(1.5)
  assert not is_drawing(memory)


def test_square_view(dolphin):
  memory = dolphin.memory
  tables = tables_from_plando(load_plando(FIXTURE))
  groups = tables.groups()
  outset = next(i for i, g in enumerate(groups) if g.name == "Outset Island")
  locations = tables.location_set.locations_in_group(groups[outset])

  # The cursor starts on Outset, where the player is. A zooms into its square view.
  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing, timeout=10, message="The tracker doesn't draw on the sea chart")
  dolphin.pad.press("A")
  dolphin.wait_for(
    lambda memory: read_ui_state(memory)["view"] == VIEW_SQUARE and is_drawing(memory), timeout=5,
    message="The tracker doesn't draw on the square view",
  )
  ui = read_ui_state(memory)
  assert (ui["list_group"], ui["sel"]) == (outset, 0)
  keep_screenshot(dolphin.screenshot(), "square-view")

  # The main stick selects, X marks the selected location. The mark is in the save data.
  dolphin.pad.tilt(0, -1, duration=0.1)
  dolphin.wait_for(lambda memory: read_ui_state(memory)["sel"] == 1, timeout=5, message="Stick down didn't select")
  loc = locations[1]
  bit_addr, mask = SAVE_MANUAL_ADDR + loc.index // 8, 1 << (loc.index % 8)
  assert SAVE_ADDR <= bit_addr < SAVE_ADDR + SAVE_SIZE
  dolphin.pad.press("X")
  dolphin.wait_for(lambda memory: memory.read_u8(bit_addr) & mask, timeout=5, message="X didn't mark the location")
  assert read_ui_state(memory)["last_toggle"] == TOGGLE_MARKED
  keep_screenshot(dolphin.screenshot(), "square-view-marked")
  dolphin.pad.press("X")
  dolphin.wait_for(lambda memory: not memory.read_u8(bit_addr) & mask, timeout=5, message="X didn't unmark the location")

  # Auto-detected locations can't be unmarked.
  first = locations[0]
  memory.write_u8(first.check.address, memory.read_u8(first.check.address) | first.check.mask)
  dolphin.pad.tilt(0, 1, duration=0.1)
  dolphin.wait_for(lambda memory: read_ui_state(memory)["sel"] == 0, timeout=5, message="Stick up didn't select")
  dolphin.pad.press("X")
  dolphin.wait_for(lambda memory: read_ui_state(memory)["last_toggle"] == TOGGLE_REFUSED, timeout=5, message="Toggle wasn't refused")
  assert not memory.read_u8(SAVE_MANUAL_ADDR + first.index // 8) & (1 << (first.index % 8))

  # B still zooms back out.
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: read_ui_state(memory)["view"] == VIEW_WORLD, timeout=5, message="B didn't zoom back out")


def test_list_page(er_dolphin):
  dolphin = er_dolphin
  memory = dolphin.memory
  tables = tables_from_plando(load_plando(ENTRANCE_RANDO_FIXTURE))
  groups = tables.groups()
  drc = next(i for i, g in enumerate(groups) if g.name == "Dragon Roost Cavern")
  ui = lambda: read_ui_state(memory)

  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing, timeout=10, message="The tracker doesn't draw on the sea chart")
  dolphin.pad.press("Z")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS, timeout=5, message="Z didn't open the list page")
  assert ui()["page_sel"] == 0  # Dragon Roost Cavern, the first group
  keep_screenshot(dolphin.screenshot(), "list-page")

  # The chart's buttons are blocked: D-pad Down doesn't close the chart and B only closes the page.
  dolphin.pad.press("D_DOWN")
  time.sleep(0.5)
  assert ui()["page"] == PAGE_GROUPS and is_drawing(memory)
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="B didn't close the page")
  time.sleep(0.5)
  assert is_drawing(memory) and ui()["view"] == VIEW_WORLD

  # The dungeon's entrance is shown once the player has been through it.
  entrance = next(e for e in tables.entrance_set.entrances if e.exit.display_name == "Dragon Roost Cavern")
  visited_addr = SAVE_VISITED_ADDR + entrance.index // 8
  memory.write_u8(visited_addr, memory.read_u8(visited_addr) | 1 << (entrance.index % 8))
  dolphin.pad.press("Z")
  dolphin.pad.press("A")
  dolphin.wait_for(
    lambda memory: (state := ui())["page"] == PAGE_GROUP and state["page_group"] == drc, timeout=5,
    message="A didn't open the group",
  )
  keep_screenshot(dolphin.screenshot(), "list-page-group")

  # X marks a location in the group.
  loc = tables.location_set.locations_in_group(groups[drc])[0]
  bit_addr, mask = SAVE_MANUAL_ADDR + loc.index // 8, 1 << (loc.index % 8)
  dolphin.pad.press("X")
  dolphin.wait_for(lambda memory: memory.read_u8(bit_addr) & mask, timeout=5, message="X didn't mark the location")

  # B goes back to the groups, Z closes the page, and then D-pad Down closes the chart again.
  dolphin.pad.press("B")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_GROUPS, timeout=5, message="B didn't go back")
  dolphin.pad.press("Z")
  dolphin.wait_for(lambda memory: ui()["page"] == PAGE_NONE, timeout=5, message="Z didn't close the page")
  dolphin.pad.press("D_DOWN")
  time.sleep(1.5)
  assert not is_drawing(memory)
