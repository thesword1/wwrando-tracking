# End-to-end test that the tracker's save data (manual marks, small keys obtained, visited entrances)
# is written to the memory card by the game's own save and comes back when the file is loaded.
#
# Session 1 boots an ISO that starts straight in gameplay (--test, new game), marks a location through
# the sea chart's Z page, gets a DRC small key through the Archipelago give-item array, visits the
# Cliff Plateau Isles inner cave's exit, then saves through the pause menu (Quest Status > Save),
# which creates the save file on Dolphin's GCI-folder memory card. Session 2 boots an ISO of the same
# seed without --test, in the same Dolphin user directory, loads Quest Log 1 from the file select
# screen and checks the tracker save data and the chart.
#
# Needs flatpak Dolphin and WW_ISO_PATH. Only runs with -m dolphin. WW_TRACKER_DOLPHIN_CACHE keeps
# the built ISOs (no savestates: the memory card has to be written by the game).

import time
from pathlib import Path

import pytest

from test_aptww_fixtures import load_plando
from test_tracker_dolphin import (
  CUSTOM_SYMBOLS, DRC_SMALL_KEY, FIXTURE, SAVE_ADDR, SAVE_KEYS_ADDR, SAVE_VISITED_ADDR, TEST_SPAWN, TRK_STATE_MAGIC,
  build_tracker_iso, make_cache_dir, pytestmark, read_state,  # noqa: F401
)
from test_tracker_serialize import tables_from_plando
from test_tracker_ui_dolphin import PAGE_GROUP, PAGE_GROUPS, PAGE_NONE, SAVE_MANUAL_ADDR, is_drawing, keep_screenshot, read_ui_state

CURRENT_ROOM_ADDR = 0x803C9D46
CURRENT_SPAWN_ADDR = 0x803C9D44
STAGE_NAME_ADDR = 0x803C9D3C


@pytest.fixture(scope="module")
def test_iso(tmp_path_factory) -> Path:
  return build_tracker_iso(make_cache_dir(tmp_path_factory, FIXTURE, TEST_SPAWN), FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def normal_iso(tmp_path_factory) -> Path:
  return build_tracker_iso(make_cache_dir(tmp_path_factory, FIXTURE, ""), FIXTURE, "")


def stage_name(memory) -> str:
  return memory.read_cstring(STAGE_NAME_ADDR, 8)

def wait_in_game(dolphin, timeout: float):
  dolphin.wait_for(
    lambda memory: (state := read_state(memory))["magic"] == TRK_STATE_MAGIC and state["in_game"],
    timeout=timeout, message="Gameplay was not reached",
  )

def press(dolphin, button: str, wait: float):
  dolphin.pad.press(button)
  time.sleep(wait)

def save_game(dolphin):
  """Quest Status > Save, creating the save file on the empty memory card."""
  press(dolphin, "START", 1.5)
  press(dolphin, "R", 1.5)  # Quest Status
  dolphin.pad.tilt(0, -1, duration=0.15)
  time.sleep(0.3)
  dolphin.pad.tilt(0, -1, duration=0.15)  # The cursor is on Save
  time.sleep(0.5)
  press(dolphin, "A", 2)  # Would you like to save? Yes
  press(dolphin, "A", 2)  # Would you like to create a save file? (defaults to No)
  dolphin.pad.tilt(-1, 0, duration=0.15)
  time.sleep(0.5)
  press(dolphin, "A", 3)  # Yes: "A save file has been created."
  press(dolphin, "A", 3)  # Would you like to save? Yes
  press(dolphin, "A", 3)  # "The game has been saved."
  keep_screenshot(dolphin.screenshot(), "save-saved")
  press(dolphin, "A", 3)  # Would you like to continue playing? Yes
  press(dolphin, "B", 2)  # Close the pause menu


def test_tracker_data_survives_save_and_load(test_iso: Path, normal_iso: Path, tmp_path: Path):
  from tools.dolphin.harness import Dolphin

  tables = tables_from_plando(load_plando(FIXTURE))
  groups = tables.groups()
  drc = next(i for i, g in enumerate(groups) if g.name == "Dragon Roost Cavern")
  loc = tables.location_set.locations_in_group(groups[drc])[0]
  manual_addr, manual_mask = SAVE_MANUAL_ADDR + loc.index // 8, 1 << (loc.index % 8)
  entrance = next(e for e in tables.entrance_set.entrances if e.entrance.name == "Secret Cave Entrance on Overlook Island")
  visited_addr, visited_mask = SAVE_VISITED_ADDR + entrance.index // 8, 1 << (entrance.index % 8)
  user_dir = tmp_path / "dolphin-user"
  card = user_dir / "GC" / "USA" / "Card A"

  # Session 1: new game, set tracker data, save.
  with Dolphin(test_iso, user_dir) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    wait_in_game(dolphin, 90)
    time.sleep(2)
    memory = dolphin.memory

    # Mark Dragon Roost Cavern's first location: chart, Z page, A on Dragon Roost Cavern, X.
    press(dolphin, "D_UP", 0.5)
    dolphin.wait_for(is_drawing, timeout=10, message="The sea chart didn't open")
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: read_ui_state(memory)["page"] == PAGE_GROUPS, timeout=5, message="Z didn't open the page")
    dolphin.pad.press("A")
    dolphin.wait_for(lambda memory: read_ui_state(memory)["page"] == PAGE_GROUP, timeout=5, message="A didn't open the group")
    assert read_ui_state(memory)["page_group"] == drc
    dolphin.pad.press("X")
    dolphin.wait_for(lambda memory: memory.read_u8(manual_addr) & manual_mask, timeout=5, message="X didn't mark")
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: read_ui_state(memory)["page"] == PAGE_NONE, timeout=5, message="Z didn't close the page")
    press(dolphin, "D_DOWN", 2)
    assert not is_drawing(memory)

    # A DRC small key, through execItemGet.
    memory.write_u8(CUSTOM_SYMBOLS["give_archipelago_item_array"], DRC_SMALL_KEY)
    dolphin.wait_for(lambda memory: memory.read_u8(SAVE_KEYS_ADDR) == 1, timeout=10, message="The small key wasn't counted")

    # Visit the Cliff Plateau Isles inner cave's exit (spawn 1 of sea room 0x2A).
    memory.write_u8(CURRENT_ROOM_ADDR, 0x2A)
    memory.write_u16(CURRENT_SPAWN_ADDR, 1)
    try:
      dolphin.wait_for(lambda memory: memory.read_u8(visited_addr) & visited_mask, timeout=10, message="Visit wasn't recorded")
    finally:
      memory.write_u8(CURRENT_ROOM_ADDR, 44)
      memory.write_u16(CURRENT_SPAWN_ADDR, 0)

    saved = memory.read_bytes(SAVE_ADDR, 0x50)
    save_game(dolphin)
    files = list(card.glob("*.gci"))
    assert len(files) == 1, "The game didn't write a save file to the memory card"
    assert memory.read_bytes(SAVE_ADDR, 0x50) == saved

  # Session 2: boot normally, load the file and check the tracker data came back.
  with Dolphin(normal_iso, user_dir) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    memory = dolphin.memory
    dolphin.wait_for(lambda memory: stage_name(memory) == "sea_T", timeout=60, message="The title screen wasn't reached")
    # The RAM still holds nothing from session 1: the reserve area is only filled by loading the file.
    # (dSv_info_c::init runs once at boot, which resets the tracker save data before any file is
    # loaded; loading must not reset it again.)
    assert memory.read_u8(manual_addr) & manual_mask == 0
    resets_before_load = read_state(memory)["save_resets"]
    deadline = time.monotonic() + 60
    while stage_name(memory) != "Name":
      assert time.monotonic() < deadline, "The file select screen wasn't reached"
      press(dolphin, "START", 2)
    time.sleep(2)
    press(dolphin, "A", 2)  # Quest Log 1
    keep_screenshot(dolphin.screenshot(), "save-file-select")
    press(dolphin, "A", 1)  # Start
    wait_in_game(dolphin, 60)
    time.sleep(2)

    assert memory.read_bytes(SAVE_ADDR, 0x50) == saved
    state = read_state(memory)
    assert state["save_resets"] == resets_before_load, "The loaded tracker data was reset"
    assert memory.read_u8(manual_addr) & manual_mask
    assert memory.read_u8(SAVE_KEYS_ADDR) == 1
    assert memory.read_u8(visited_addr) & visited_mask
    assert state["num_checked"] >= 1

    # The mark shows on the chart.
    press(dolphin, "D_UP", 0.5)
    dolphin.wait_for(is_drawing, timeout=10, message="The sea chart didn't open")
    dolphin.pad.press("Z")
    dolphin.wait_for(lambda memory: read_ui_state(memory)["page"] == PAGE_GROUPS, timeout=5, message="Z didn't open the page")
    dolphin.pad.press("A")
    dolphin.wait_for(lambda memory: read_ui_state(memory)["page"] == PAGE_GROUP, timeout=5, message="A didn't open the group")
    time.sleep(0.5)
    keep_screenshot(dolphin.screenshot(), "save-loaded-mark")
