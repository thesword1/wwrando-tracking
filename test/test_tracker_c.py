# Host tests of the tracker C runtime's table reader (asm/tracker/tracker_tables.c) against
# tracker/serialize.py.

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from tracker.serialize import Section, serialize_tracker_tables
from test_aptww_fixtures import FIXTURE_PATHS, load_plando
from test_tracker_serialize import tables_from_plando
from tracker_c_host import TrackerHost, TrkChart, TrkEntrance, TrkGroup, TrkLocation, TrkTrigger


def test_invalid_tables(tracker: TrackerHost):
  tracker.set_tables(bytes(0x100))
  assert not tracker.lib.trk_tables_valid()
  blob = bytearray(serialize_tracker_tables(tables_from_plando(load_plando(FIXTURE_PATHS[0])), 0xBEEF))
  tracker.set_tables(bytes(blob))
  assert tracker.lib.trk_tables_valid()
  blob[5] = 99 # Format version
  tracker.set_tables(bytes(blob))
  assert not tracker.lib.trk_tables_valid()

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_reader_matches_serializer(tracker: TrackerHost, path: Path):
  tables = tables_from_plando(load_plando(path))
  tracker.set_tables(serialize_tracker_tables(tables, 0xBEEF))
  lib = tracker.lib
  assert lib.trk_tables_valid()
  assert lib.trk_seed_tag() == 0xBEEF
  assert lib.trk_table_flags() == 0

  locations = tables.location_set.locations
  assert lib.trk_count(Section.LOCATIONS) == len(locations)
  for loc in locations:
    entry = tracker.get("trk_get_location", TrkLocation, loc.index)
    assert entry.group_id == loc.group.id
    assert entry.type == loc.check.type.value
    assert entry.stage_id == (0xFF if loc.check.stage_id is None else loc.check.stage_id)
    assert entry.mask == loc.check.mask
    assert entry.address == (loc.check.address or 0)
    assert tracker.string(entry.name) == loc.display_name
    assert entry.special == (0xFF if loc.check.special is None else loc.check.special.value)

  groups = tables.groups()
  assert lib.trk_count(Section.GROUPS) == len(groups)
  for i, group in enumerate(groups):
    entry = tracker.get("trk_get_group", TrkGroup, i)
    assert (entry.id, entry.kind) == (group.id, group.kind.value)
    assert tracker.string(entry.name) == group.name
    group_locations = tables.location_set.locations_in_group(group)
    assert entry.num_locations == len(group_locations)
    if group_locations:
      assert entry.first_location == group_locations[0].index
    assert lib.trk_find_group(group.id) == i
  assert lib.trk_find_group(0) == -1

  entrances = tables.entrance_set.entrances
  assert lib.trk_count(Section.ENTRANCES) == len(entrances)
  for seed_entrance in entrances:
    entry = tracker.get("trk_get_entrance", TrkEntrance, seed_entrance.index)
    assert entry.island_number == (seed_entrance.entrance.island_number or 0)
    assert entry.exit_group == seed_entrance.exit.group.id
    assert tracker.string(entry.entrance_name) == seed_entrance.entrance.display_name
    assert tracker.string(entry.exit_name) == seed_entrance.exit.display_name

  triggers = tables.entrance_set.stage_triggers()
  assert lib.trk_count(Section.TRIGGERS) == len(triggers)
  for i, (trigger, entrance_index) in enumerate(triggers):
    entry = tracker.get("trk_get_trigger", TrkTrigger, i)
    assert entry.stage_name.decode("ascii") == trigger.stage_name
    assert entry.room == (0xFF if trigger.room_num is None else trigger.room_num)
    assert entry.spawn == (0xFF if trigger.spawn_id is None else trigger.spawn_id)
    assert entry.entrance_index == entrance_index

  assert lib.trk_count(Section.CHARTS) == 49
  for i, chart in enumerate(tables.charts):
    entry = tracker.get("trk_get_chart", TrkChart, i)
    assert entry.destination_square == chart.destination_island_number
    assert entry.chart_number == chart.chart_number
    assert entry.item_id == chart.item_id
    assert 0x803C4CDC + entry.owned_offset == chart.owned_address
    assert entry.owned_mask == chart.owned_mask
    assert 0x803C4CFC + entry.salvaged_offset == chart.salvaged_address
    assert entry.salvaged_mask == chart.salvaged_mask
    assert tracker.string(entry.name) == chart.name

  assert lib.trk_count(Section.LOGIC) == 0
  assert lib.trk_count(Section.ITEMS) == 0

def test_mock_ram(tracker: TrackerHost):
  tracker.write_u16(0x803C4C0A, 0x0C34)
  assert tracker.read_bytes(0x803C4C0A, 2) == b"\x0C\x34"
  tracker.reset_ram()
  assert tracker.read_u8(0x803C4C0A) == 0
