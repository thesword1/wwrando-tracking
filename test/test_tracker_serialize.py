import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from tracker.locations import ENTRANCE_CATEGORIES, STATIC_LOCATIONS
from tracker.serialize import (
  FORMAT_VERSION, HEADER_SIZE, MAGIC, NUM_SECTIONS, TRACKER_DATA_RESERVE_SIZE, Section, build_tracker_tables,
  compute_seed_tag, parse_tracker_tables, serialize_tracker_tables,
)
from test_aptww_fixtures import FIXTURE_PATHS, load_plando
from tracker_c_host import TRACKER_C_DIR

ALL_ENTRANCES_RANDOMIZED = {option_name: 1 for option_name in ENTRANCE_CATEGORIES}


def tables_from_plando(plando: dict):
  options = plando["Options"]
  required_bosses = plando["Required Bosses"] if options.get("required_bosses") else None
  return build_tracker_tables(plando["Locations"], plando["Charts"], plando["Entrances"], options, required_bosses)


def test_reserve_size_matches_patch():
  asm = (REPO_ROOT / "asm" / "patches" / "tracker.asm").read_text()
  match = re.search(r"^tracker_data:\s*\n\s*\.space\s+(0x[0-9A-F]+)", asm, re.IGNORECASE | re.MULTILINE)
  assert int(match.group(1), 16) == TRACKER_DATA_RESERVE_SIZE

def test_c_constants_match():
  header = (TRACKER_C_DIR / "tracker_tables.h").read_text()
  def define(name):
    return int(re.search(rf"#define {name} (0x[0-9A-F]+|\d+)", header).group(1), 0)
  assert define("TRK_MAGIC").to_bytes(4, "big") == MAGIC
  assert define("TRK_FORMAT_VERSION") == FORMAT_VERSION
  assert define("TRK_HEADER_SIZE") == HEADER_SIZE
  for section in Section:
    assert re.search(rf"TRK_SEC_{section.name} = {section.value},", header), section
  assert re.search(rf"TRK_NUM_SECTIONS = {NUM_SECTIONS},", header)

def test_seed_tag():
  tags = {compute_seed_tag(f"seed {i}") for i in range(1000)}
  assert all(0 < tag <= 0xFFFF for tag in tags)
  assert len(tags) > 980
  assert compute_seed_tag("abc") == compute_seed_tag("abc")

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_round_trip_fixture(path: Path):
  plando = load_plando(path)
  tables = tables_from_plando(plando)
  blob = serialize_tracker_tables(tables, 0x1234)
  assert len(blob) <= TRACKER_DATA_RESERVE_SIZE
  parsed = parse_tracker_tables(blob)
  assert parsed["seed_tag"] == 0x1234
  assert parsed["total_size"] == len(blob)

  locations = tables.location_set.locations
  assert len(parsed["locations"]) == len(locations)
  for loc, entry in zip(locations, parsed["locations"]):
    group_id, type_value, stage_id, mask, address, name, special, flags = entry
    assert group_id == loc.group.id
    assert type_value == loc.check.type.value
    assert stage_id == (0xFF if loc.check.stage_id is None else loc.check.stage_id)
    assert mask == loc.check.mask
    assert address == (loc.check.address or 0)
    assert name == loc.display_name
    assert special == (0xFF if loc.check.special is None else loc.check.special.value)

  group_ids = [group[0] for group in parsed["groups"]]
  assert group_ids == sorted(group_ids)
  assert group_ids[:49] == list(range(1, 50))
  covered = 0
  for group_id, kind, first, count, name in parsed["groups"]:
    in_group = [i for i, loc in enumerate(locations) if loc.group.id == group_id]
    assert in_group == list(range(first, first + count)), name
    covered += count
  assert covered == len(locations)

  entrances = tables.entrance_set.entrances
  assert [entry[5] for entry in parsed["entrances"]] == [e.exit.display_name for e in entrances]
  assert len(parsed["triggers"]) == len(tables.entrance_set.stage_triggers())
  for stage, room, spawn, entrance_index in parsed["triggers"]:
    assert 0 < len(stage) <= 8
    assert entrance_index < len(entrances)
    if (stage, room, spawn) == ("sea", 0x2A, 1):
      assert entrances[entrance_index].exit.name == "Cliff Plateau Isles Inner Cave"
    else:
      assert (room, spawn) == (0xFF, 0xFF)
  exit_group_ids = {entry[2] for entry in parsed["entrances"]}
  assert exit_group_ids <= set(group_ids)

  stage_names = [stage for stage, _ in parsed["stages"]]
  assert stage_names == sorted(stage_names) and len(set(stage_names)) == len(stage_names)
  for stage, group_id in parsed["stages"]:
    assert 0 < len(stage) <= 8
    assert group_id in group_ids
    assert tables.stage_groups[stage].id == group_id

  assert [chart[0] for chart in parsed["charts"]] == list(range(1, 50))
  for chart, entry in zip(tables.charts, parsed["charts"]):
    assert entry[2] == chart.chart_number
    assert entry[8] == chart.name

def test_size_budget_worst_case():
  # Every location and every entrance tracked.
  pairings = {}
  from tracker.locations import VANILLA_EXIT_TO_ENTRANCE
  for zone_exit, zone_entrance in VANILLA_EXIT_TO_ENTRANCE.items():
    pairings[zone_entrance.entrance_name] = zone_exit.unique_name
  tables = build_tracker_tables(STATIC_LOCATIONS, None, pairings, ALL_ENTRANCES_RANDOMIZED, None)
  blob = serialize_tracker_tables(tables, 1)
  # Leave at least a third of the reserve for the logic bytecode.
  assert len(blob) <= 0x4000
  parsed = parse_tracker_tables(blob)
  assert len(parsed["locations"]) == len(STATIC_LOCATIONS)
