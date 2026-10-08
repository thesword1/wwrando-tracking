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
