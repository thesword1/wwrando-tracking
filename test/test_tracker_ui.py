# Host tests of the sea chart UI's state logic (asm/tracker/tracker_ui.c). The drawing itself only
# runs in the game; test_tracker_ui_dolphin.py covers it.

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

import ctypes

from test_tracker_c_runtime import enter_game, entrance_rando, full, index_of, set_location_flag  # noqa: F401 (fixtures)
from tracker_c_host import TrackerHost
from tracker.entrances import EXITS

EXIT_GROUPS = {name: exit.group.name for name, exit in EXITS.items()}

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
BTN_X, BTN_Z, BTN_A, BTN_B = 1, 2, 4, 8
VIEW_NONE, VIEW_WORLD, VIEW_SQUARE = 0, 1, 2
PAGE_NONE, PAGE_GROUPS, PAGE_GROUP = 0, 1, 2
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
  rows = LIST_ROWS - len(full.ui_info_lines(windfall))
  assert count > rows

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
  assert full.ui_state.scroll == count - rows
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
  assert full.ui_state.scroll == count - rows
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


def page_groups(tracker: TrackerHost) -> list[int]:
  count = ctypes.c_uint16()
  tracker.lib.tracker_ui_page_group(0, ctypes.byref(count))
  return [tracker.lib.tracker_ui_page_group(n, None) for n in range(count.value)]


def test_page_groups(full: TrackerHost):
  groups = full.tables.groups()
  expected = [i for i, g in enumerate(groups) if g.id >= 50 and full.tables.location_set.locations_in_group(g)]
  assert expected
  assert page_groups(full) == expected
  assert full.lib.tracker_ui_page_group(len(expected), None) == -1


def ui_input(tracker: TrackerHost, view: int, buttons: int = 0, stick: int = 0, square_group: int = -1) -> bool:
  return tracker.lib.tracker_ui_input(view, square_group, buttons, stick)


def test_page_navigation(entrance_rando: TrackerHost):
  tracker = entrance_rando
  enter_game(tracker)
  tracker.lib.tracker_frame()
  ui = tracker.ui_state
  ui.list_group = NO_GROUP
  page = page_groups(tracker)

  # Outside the page the chart's own input runs, and only Z opens the page (not in other views).
  assert not ui_input(tracker, VIEW_WORLD, BTN_A | BTN_B)
  assert not ui_input(tracker, VIEW_NONE, BTN_Z)
  assert ui.page == PAGE_NONE
  assert ui_input(tracker, VIEW_WORLD, BTN_Z)
  assert (ui.page, ui.page_sel) == (PAGE_GROUPS, 0)
  # Everything is consumed while the page is shown.
  assert ui_input(tracker, VIEW_WORLD)
  push_page = lambda stick: (ui_input(tracker, VIEW_WORLD, stick=stick), ui_input(tracker, VIEW_WORLD))
  push_page(STICK_DOWN)
  push_page(STICK_DOWN)
  assert ui.page_sel == 2
  push_page(STICK_UP)
  push_page(STICK_UP)
  push_page(STICK_UP)
  assert ui.page_sel == len(page) - 1
  assert ui.page_scroll == len(page) - LIST_ROWS
  push_page(STICK_DOWN)
  assert (ui.page_sel, ui.page_scroll) == (0, 0)

  # A opens the selected group's list, which works like a square's.
  assert ui_input(tracker, VIEW_WORLD, BTN_A)
  assert (ui.page, ui.page_group) == (PAGE_GROUP, page[0])
  group = tracker.tables.groups()[page[0]]
  first = tracker.tables.location_set.locations_in_group(group)[0]
  assert ui_input(tracker, VIEW_WORLD, BTN_X)
  assert tracker.lib.tracker_is_manual(first.index)
  assert ui.list_group == page[0]
  # B goes back to the groups, B again closes the page.
  assert ui_input(tracker, VIEW_WORLD, BTN_B)
  assert ui.page == PAGE_GROUPS
  assert ui_input(tracker, VIEW_WORLD, BTN_B)
  assert ui.page == PAGE_NONE
  assert not ui_input(tracker, VIEW_WORLD)

  # Z closes the page from either level, and also opens it from square view, where the stick and X
  # otherwise work on the square's list without consuming the input.
  assert ui_input(tracker, VIEW_SQUARE, BTN_Z, square_group=page[1])
  assert ui_input(tracker, VIEW_SQUARE, BTN_A)
  assert ui.page == PAGE_GROUP
  assert ui_input(tracker, VIEW_SQUARE, BTN_Z)
  assert ui.page == PAGE_NONE
  square = group_index(tracker, tracker.tables.groups()[10].name)
  assert not ui_input(tracker, VIEW_SQUARE, BTN_X, square_group=square)
  assert ui.list_group == square


def test_group_entrance(entrance_rando: TrackerHost):
  tracker = entrance_rando
  entrances = tracker.tables.entrance_set.entrances
  def expected(group_name):
    candidates = [e.index for e in entrances if e.exit.group.name == group_name]
    own = [e.index for e in entrances if e.exit.group.name == group_name and e.exit.display_name == group_name]
    return (own or candidates or [-1])[0]
  for name in ["Dragon Roost Cavern", "Savage Labyrinth", "Ganon's Tower", "Needle Rock Isle Secret Cave", "Wind Temple"]:
    assert tracker.lib.tracker_ui_group_entrance(group_index(tracker, name)) == expected(name), name
  # A dungeon is reached through its dungeon entrance, not the boss door into its boss arena.
  drc_entrance = entrances[tracker.lib.tracker_ui_group_entrance(group_index(tracker, "Dragon Roost Cavern"))]
  assert drc_entrance.exit.display_name == "Dragon Roost Cavern"
  assert tracker.lib.tracker_ui_group_entrance(group_index(tracker, "Ganon's Tower")) == -1


INFO_ENTRANCE, INFO_CHART = 0, 1
SAVE_VISITED_ADDR = 0x803C532C + 0x40
GET_MAP_ADDR = 0x803C4CDC

def load_fixture(tracker: TrackerHost, fixture: str):
  from test_aptww_fixtures import FIXTURES_DIR, load_plando
  from test_tracker_serialize import tables_from_plando
  from tracker.serialize import serialize_tracker_tables
  tables = tables_from_plando(load_plando(FIXTURES_DIR / f"{fixture}.aptww"))
  tracker.set_tables(serialize_tracker_tables(tables, 0x1234))
  tracker.tables = tables
  enter_game(tracker)
  tracker.lib.tracker_frame()


def test_entrance_info_lines(entrance_rando: TrackerHost):
  tracker = entrance_rando
  enter_game(tracker)
  tracker.lib.tracker_frame()
  entrances = tracker.tables.entrance_set.entrances

  # The tracked entrances on a square's island, hidden until visited.
  outset = group_index(tracker, "Outset Island")
  expected = [e.index for e in entrances if e.entrance.island_number == 44 and not e.entrance.nested_in]
  assert len(expected) == 2
  assert tracker.ui_info_lines(outset) == [(INFO_ENTRANCE, 0, i) for i in expected]
  tracker.write_u8(SAVE_VISITED_ADDR + expected[0] // 8, 1 << (expected[0] % 8))
  assert tracker.ui_info_lines(outset) == [(INFO_ENTRANCE, 1, expected[0]), (INFO_ENTRANCE, 0, expected[1])]

  # Entrances nested in a group (a dungeon's miniboss and boss doors) are on that group's list.
  fw = group_index(tracker, "Forbidden Woods")
  nested = [e.index for e in entrances if e.entrance.nested_in and EXIT_GROUPS[e.entrance.nested_in] == "Forbidden Woods"]
  assert nested
  assert [index for _, _, index in tracker.ui_info_lines(fw)] == nested

  # No charts in this seed's locations, and nothing on a square without tracked entrances.
  assert tracker.ui_info_lines(group_index(tracker, "Windfall Island")) == []


def test_chart_info_line(tracker: TrackerHost):
  load_fixture(tracker, "charts_required_bosses")
  charts = tracker.tables.charts
  assert any(c.vanilla_island_number != c.destination_island_number for c in charts)
  outset = group_index(tracker, "Outset Island")
  chart = next(c for c in charts if c.destination_island_number == 44)
  assert tracker.ui_info_lines(outset) == [(INFO_CHART, 0, 43)]
  # Revealed once the chart that leads here is owned (not the island's vanilla chart).
  tracker.write_u8(chart.owned_address, tracker.read_u8(chart.owned_address) | chart.owned_mask)
  assert tracker.ui_info_lines(outset) == [(INFO_CHART, 1, 43)]


def test_info_lines_take_list_rows(tracker: TrackerHost):
  load_fixture(tracker, "progression_all")
  windfall = group_index(tracker, "Windfall Island")
  assert tracker.ui_info_lines(windfall) == [(INFO_CHART, 0, 10)]
  tracker.ui_state.list_group = NO_GROUP
  rows = LIST_ROWS - 1
  for _ in range(rows):
    push(tracker, windfall, STICK_DOWN)
  assert (tracker.ui_state.sel, tracker.ui_state.scroll) == (rows, 1)
