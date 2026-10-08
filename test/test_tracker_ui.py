# Host tests of the sea chart UI's state logic (asm/tracker/tracker_ui.c). The drawing itself only
# runs in the game; test_tracker_ui_dolphin.py covers it.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from test_tracker_c_runtime import enter_game, full, index_of, set_location_flag  # noqa: F401 (fixture)
from tracker_c_host import TrackerHost

# enum TrkUiStatus
UI_NONE, UI_DONE, UI_IN_LOGIC, UI_OUT_OF_LOGIC, UI_UNKNOWN = range(5)
COUNTER_UNKNOWN = 0xFF


def group_index(tracker: TrackerHost, name: str) -> int:
  return next(i for i, g in enumerate(tracker.tables.groups()) if g.name == name)


def test_group_counters(full: TrackerHost):
  tables = full.tables
  groups = tables.groups()
  enter_game(full)
  full.lib.tracker_frame()
  for i, group in enumerate(groups):
    counter = full.ui_counter(i)
    total = len(tables.location_set.locations_in_group(group))
    if total == 0:
      assert counter.status == UI_NONE, group.name
      continue
    # No logic yet: every counter shows the remaining count only.
    assert (counter.remaining, counter.available, counter.status) == (total, COUNTER_UNKNOWN, UI_UNKNOWN), group.name

  outset = group_index(full, "Outset Island")
  outset_locations = tables.location_set.locations_in_group(groups[outset])
  set_location_flag(full, "Outset Island - Underneath Link's House")
  full.lib.tracker_toggle_manual(index_of(full, "Outset Island - Mesa the Grasscutter's House"))
  full.lib.tracker_frame()
  assert full.ui_counter(outset).remaining == len(outset_locations) - 2
  assert full.ui_counter(outset).status == UI_UNKNOWN

  for loc in outset_locations:
    if not full.lib.tracker_is_checked(loc.index):
      full.lib.tracker_toggle_manual(loc.index)
  full.lib.tracker_frame()
  counter = full.ui_counter(outset)
  assert (counter.remaining, counter.status) == (0, UI_DONE)


# tracker_ui.h
BTN_X = 1
STICK_UP, STICK_DOWN = 72, -72
LIST_ROWS = 15
REPEAT_DELAY, REPEAT_RATE = 14, 4
NO_GROUP = 0xFF
TOGGLE_MARKED, TOGGLE_UNMARKED, TOGGLE_REFUSED = 1, 2, 3


def list_input(tracker: TrackerHost, group: int, buttons: int = 0, stick: int = 0, frames: int = 1):
  for _ in range(frames):
    tracker.lib.tracker_ui_list_input(group, buttons, stick)

def push(tracker: TrackerHost, group: int, stick: int):
  list_input(tracker, group, stick=stick)
  list_input(tracker, group)


def test_list_selection(full: TrackerHost):
  enter_game(full)
  full.lib.tracker_frame()
  full.ui_state.list_group = NO_GROUP
  windfall = group_index(full, "Windfall Island")
  count = len(full.tables.location_set.locations_in_group(full.tables.groups()[windfall]))
  assert count > LIST_ROWS

  list_input(full, windfall)
  assert (full.ui_state.list_group, full.ui_state.sel, full.ui_state.scroll) == (windfall, 0, 0)
  push(full, windfall, STICK_DOWN)
  push(full, windfall, STICK_DOWN)
  assert full.ui_state.sel == 2
  push(full, windfall, STICK_UP)
  assert full.ui_state.sel == 1
  # A small push doesn't move.
  push(full, windfall, 20)
  assert full.ui_state.sel == 1

  # A fresh push wraps around; holding repeats and stops at the ends.
  push(full, windfall, STICK_UP)
  push(full, windfall, STICK_UP)
  assert full.ui_state.sel == count - 1
  assert full.ui_state.scroll == count - LIST_ROWS
  list_input(full, windfall, stick=STICK_DOWN)
  assert full.ui_state.sel == 0 and full.ui_state.scroll == 0
  list_input(full, windfall, stick=STICK_DOWN, frames=REPEAT_DELAY - 1)
  assert full.ui_state.sel == 0
  list_input(full, windfall, stick=STICK_DOWN)
  assert full.ui_state.sel == 1
  list_input(full, windfall, stick=STICK_DOWN, frames=REPEAT_RATE)
  assert full.ui_state.sel == 2
  list_input(full, windfall, stick=STICK_DOWN, frames=REPEAT_RATE*count)
  assert full.ui_state.sel == count - 1
  assert full.ui_state.scroll == count - LIST_ROWS
  list_input(full, windfall)

  # Another group starts at the top.
  outset = group_index(full, "Outset Island")
  list_input(full, outset)
  assert (full.ui_state.list_group, full.ui_state.sel, full.ui_state.scroll) == (outset, 0, 0)


def test_list_toggle(full: TrackerHost):
  enter_game(full)
  full.lib.tracker_frame()
  full.ui_state.list_group = NO_GROUP
  outset = group_index(full, "Outset Island")
  first = full.tables.location_set.locations_in_group(full.tables.groups()[outset])[0]
  assert first.name == "Outset Island - Underneath Link's House"

  list_input(full, outset, BTN_X)
  assert full.ui_state.last_toggle == TOGGLE_MARKED
  assert full.lib.tracker_is_manual(first.index)
  assert full.lib.tracker_ui_location_status(first.index) == UI_DONE
  # Counts are updated right away.
  assert full.state.group_checked[outset] == 1
  list_input(full, outset, BTN_X)
  assert full.ui_state.last_toggle == TOGGLE_UNMARKED
  assert not full.lib.tracker_is_manual(first.index)
  assert full.lib.tracker_ui_location_status(first.index) == UI_UNKNOWN
  assert full.state.group_checked[outset] == 0

  # Auto-detected checks can't be unmarked: the row flashes instead.
  set_location_flag(full, first.name)
  list_input(full, outset, BTN_X)
  assert full.ui_state.last_toggle == TOGGLE_REFUSED
  assert not full.lib.tracker_is_manual(first.index)
  assert full.ui_state.flash_timer > 0
  assert full.lib.tracker_ui_location_status(first.index) == UI_DONE
  list_input(full, outset, frames=30)
  assert full.ui_state.flash_timer == 0
