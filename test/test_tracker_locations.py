import ast
import os
import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from logic.logic import Logic
from tracker.location_data import LOCATION_DATA, LocationType
from tracker.locations import (
  CHARTS_BITFIELD_ADDR, CAVE_EXITS, ISLAND_NUMBER_TO_NAME, LIVE_STAGE_INFO_ADDR, SAVED_STAGE_INFO_ADDR,
  STATIC_LOCATIONS, GroupKind, build_tracker_location_set, resolve_check,
)
from test_aptww_fixtures import FIXTURE_PATHS, load_plando

ALL_ENTRANCES_RANDOMIZED = {
  "randomize_dungeon_entrances": 1,
  "randomize_secret_cave_entrances": 1,
  "randomize_miniboss_entrances": 1,
  "randomize_boss_entrances": 1,
  "randomize_secret_cave_inner_entrances": 1,
  "randomize_fairy_fountain_entrances": 1,
}

# The APWorld is only a reference, so these comparisons are skipped when it isn't checked out next
# to this repository (or at AP_TWW_WORLD_PATH).
AP_TWW_WORLD_PATH = Path(os.environ.get(
  "AP_TWW_WORLD_PATH", REPO_ROOT.parent / "Archipelago-main" / "worlds" / "tww"
))
needs_apworld = pytest.mark.skipif(
  not (AP_TWW_WORLD_PATH / "Locations.py").is_file(), reason="Archipelago TWW world not found"
)

def load_apworld_locations() -> tuple[dict[str, tuple], dict[str, int]]:
  # Locations.py imports Archipelago's BaseClasses, so read its tables without importing it.
  tree = ast.parse((AP_TWW_WORLD_PATH / "Locations.py").read_text())
  tables = {}
  for node in tree.body:
    if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
      tables[node.target.id] = node.value

  def value(node):
    if isinstance(node, ast.Attribute):
      return node.attr
    if isinstance(node, ast.BinOp):
      return None # Flags
    return ast.literal_eval(node)

  locations = {}
  for key, call in zip(tables["LOCATION_TABLE"].keys, tables["LOCATION_TABLE"].values):
    args = [value(arg) for arg in call.args]
    # (type, stage ID, bit, address)
    locations[key.value] = (args[4], args[3], args[5], args[6] if len(args) > 6 else None)
  salvage_bits = ast.literal_eval(tables["ISLAND_NAME_TO_SALVAGE_BIT"])
  return locations, salvage_bits


def test_every_logic_location_has_data():
  item_locations = Logic.load_and_parse_item_locations()
  assert list(LOCATION_DATA) == list(item_locations)
  assert len(STATIC_LOCATIONS) == 320

def test_display_names():
  for name, data in LOCATION_DATA.items():
    assert 0 < len(data.display_name) <= 28, name
    assert data.display_name.isascii() and data.display_name.isprintable(), name

  for entrance_options in [None, ALL_ENTRANCES_RANDOMIZED]:
    location_set = build_tracker_location_set(STATIC_LOCATIONS, entrance_options=entrance_options)
    for group in location_set.groups():
      display_names = [loc.display_name for loc in location_set.locations_in_group(group)]
      assert len(display_names) == len(set(display_names)), group

@needs_apworld
def test_detection_data_matches_apworld():
  ap_locations, ap_salvage_bits = load_apworld_locations()
  assert set(ap_locations) - set(LOCATION_DATA) == {"Defeat Ganondorf"}

  for name, (ap_type, ap_stage_id, ap_bit, ap_address) in ap_locations.items():
    if name == "Defeat Ganondorf":
      continue
    data = LOCATION_DATA[name]
    assert (data.type.name, data.stage_id, data.bit, data.address) == (ap_type, ap_stage_id, ap_bit, ap_address), name

  # Sunken Treasure bits are the salvage bits of each island's vanilla chart.
  for island_name, salvage_bit in ap_salvage_bits.items():
    assert LOCATION_DATA[f"{island_name} - Sunken Treasure"].bit == salvage_bit

def test_logic_only_locations_are_never_progress():
  # The APWorld has no flag for these, and they can never hold progress items.
  item_locations = Logic.load_and_parse_item_locations()
  for name, data in LOCATION_DATA.items():
    if data.type == LocationType.NONE:
      types = item_locations[name]["Types"]
      assert "Consumables only" in types or "No progression" in types, name


def read_like_twwclient(memory: dict[int, int], address: int, size: int) -> int:
  return int.from_bytes(bytes(memory.get(address + i, 0) for i in range(size)), "big")

@pytest.mark.parametrize("name", [n for n, d in LOCATION_DATA.items() if d.type != LocationType.NONE])
def test_check_descriptor_matches_twwclient_bit_numbering(name: str):
  # Set the location's bit the way TWWClient.py reads it, and check that the descriptor's single
  # byte and mask see it. Also check no other bit of that field satisfies the descriptor.
  data = LOCATION_DATA[name]
  check = resolve_check(name, data)

  if data.type == LocationType.SPECL:
    assert check.special is not None
    return

  if data.type in (LocationType.CHEST, LocationType.PCKUP, LocationType.SWTCH):
    offset, size = {LocationType.CHEST: (0x00, 4), LocationType.SWTCH: (0x04, 10), LocationType.PCKUP: (0x14, 4)}[data.type]
    field_address = SAVED_STAGE_INFO_ADDR + 0x24*data.stage_id + offset
    assert check.live_address == check.address - field_address + LIVE_STAGE_INFO_ADDR + offset
  elif data.type == LocationType.CHART:
    field_address, size = CHARTS_BITFIELD_ADDR, 8
  elif data.type == LocationType.BOCTO:
    field_address, size = data.address, 2
  else:
    field_address, size = data.address, 1

  for bit in range(size * 8):
    memory = {}
    for i, byte in enumerate((1 << bit).to_bytes(size, "big")):
      memory[field_address + i] = byte
    assert bool((read_like_twwclient(memory, field_address, size) >> data.bit) & 1) == (bit == data.bit)
    assert ((memory.get(check.address, 0) & check.mask) == check.mask) == (bit == data.bit)


def test_groups_without_entrance_rando():
  location_set = build_tracker_location_set(STATIC_LOCATIONS)
  groups = location_set.groups()
  # Every square has at least its Sunken Treasure.
  assert {g.id for g in groups if g.kind == GroupKind.SQUARE} == set(range(1, 49+1))
  assert not [g for g in groups if g.kind == GroupKind.CAVE]

  by_name = {loc.name: loc for loc in location_set.locations}
  assert by_name["Outset Island - Savage Labyrinth - Floor 30"].group.name == "Outset Island"
  assert by_name["Ice Ring Isle - Inner Cave - Chest"].group.name == "Ice Ring Isle"
  assert by_name["Cliff Plateau Isles - Highest Isle"].group.name == "Cliff Plateau Isles"
  assert by_name["Outset Island - Great Fairy"].group.name == "Outset Island"
  assert by_name["Forsaken Fortress Sector - Sunken Treasure"].group.id == 1
  assert by_name["Five-Star Isles - Sunken Treasure"].group.id == 49
  assert by_name["Dragon Roost Cavern - Gohma Heart Container"].group.name == "Dragon Roost Cavern"
  assert by_name["Forbidden Woods - Mothula Miniboss Room"].group.name == "Forbidden Woods"
  assert by_name["Forsaken Fortress - Helmaroc King Heart Container"].group.name == "Forsaken Fortress"
  assert by_name["Hyrule - Master Sword Chamber"].group.name == "Hyrule"
  assert by_name["Mailbox - Letter from Baito"].group.name == "Mailbox"
  assert by_name["The Great Sea - Ghost Ship"].group.name == "The Great Sea"

  # Groups are contiguous and in ID order.
  ids = [loc.group.id for loc in location_set.locations]
  assert ids == sorted(ids)
  assert [loc.index for loc in location_set.locations] == list(range(len(location_set.locations)))

def test_groups_with_entrance_rando():
  location_set = build_tracker_location_set(STATIC_LOCATIONS, entrance_options=ALL_ENTRANCES_RANDOMIZED)
  cave_exit_names = {ex.unique_name for ex in CAVE_EXITS}
  for loc in location_set.locations:
    if loc.zone_exit in cave_exit_names:
      assert loc.group.kind == GroupKind.CAVE and loc.group.name == loc.zone_exit, loc.name
    else:
      assert loc.group.kind != GroupKind.CAVE, loc.name
  # Dungeon interiors and arenas stay with their dungeon.
  by_name = {loc.name: loc for loc in location_set.locations}
  assert by_name["Earth Temple - Jalhalla Heart Container"].group.name == "Earth Temple"
  assert by_name["Wind Temple - Wizzrobe Miniboss Room"].group.name == "Wind Temple"

def test_inner_caves_follow_their_outer_cave():
  only_caves = {"randomize_secret_cave_entrances": 1}
  by_name = {loc.name: loc for loc in build_tracker_location_set(STATIC_LOCATIONS, entrance_options=only_caves).locations}
  # The inner cave's own entrance isn't randomized, but the cave it's in is.
  assert by_name["Ice Ring Isle - Inner Cave - Chest"].group.name == "Ice Ring Isle Inner Cave"
  assert by_name["Outset Island - Great Fairy"].group.name == "Outset Island"

  only_inner = {"randomize_secret_cave_inner_entrances": 1}
  by_name = {loc.name: loc for loc in build_tracker_location_set(STATIC_LOCATIONS, entrance_options=only_inner).locations}
  assert by_name["Ice Ring Isle - Inner Cave - Chest"].group.name == "Ice Ring Isle Inner Cave"
  assert by_name["Ice Ring Isle - Cave - Chest"].group.name == "Ice Ring Isle"

def test_required_bosses_hide_other_dungeons():
  required = ["Dragon Roost Cavern - Gohma Heart Container", "Earth Temple - Jalhalla Heart Container"]
  location_set = build_tracker_location_set(STATIC_LOCATIONS, required_bosses=required)
  dungeon_names = {g.name for g in location_set.groups() if g.kind == GroupKind.DUNGEON}
  assert dungeon_names == {"Dragon Roost Cavern", "Earth Temple"}

  location_set = build_tracker_location_set(STATIC_LOCATIONS, required_bosses=["Forsaken Fortress"])
  assert {g.name for g in location_set.groups() if g.kind == GroupKind.DUNGEON} == {"Forsaken Fortress"}

def test_unknown_location_name_is_rejected():
  with pytest.raises(KeyError):
    build_tracker_location_set(["Outset Island - Not A Location"])


def expected_salvage_bits_like_twwclient(chart_mapping: list[int]) -> dict[str, int]:
  # TWWContext.update_salvage_locations_map, with the vanilla salvage bit of each island.
  salvage_locations_map = {}
  for offset in range(49):
    island_name = ISLAND_NUMBER_TO_NAME[offset + 1]
    salvage_bit = LOCATION_DATA[f"{island_name} - Sunken Treasure"].bit
    shuffled_island_name = ISLAND_NUMBER_TO_NAME[chart_mapping[offset]]
    salvage_locations_map[f"{shuffled_island_name} - Sunken Treasure"] = salvage_bit
  return salvage_locations_map

def test_random_chart_mapping():
  rng = random.Random(0)
  chart_mapping = list(range(1, 49+1))
  rng.shuffle(chart_mapping)
  location_set = build_tracker_location_set(STATIC_LOCATIONS, chart_mapping=chart_mapping)
  expected_bits = expected_salvage_bits_like_twwclient(chart_mapping)
  sunken = [loc for loc in location_set.locations if loc.check.type == LocationType.CHART]
  assert len(sunken) == 49
  for loc in sunken:
    bit = expected_bits[loc.name]
    assert (loc.check.address, loc.check.mask) == (CHARTS_BITFIELD_ADDR + 7 - bit//8, 1 << (bit % 8))
    # The chart that leads here is the vanilla chart of the island it was taken from.
    assert loc.group.name == loc.name.removesuffix(" - Sunken Treasure")


@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_build_from_aptww_fixture(path: Path):
  plando = load_plando(path)
  options = plando["Options"]
  required_bosses = plando["Required Bosses"] if options["required_bosses"] else None
  location_set = build_tracker_location_set(
    plando["Locations"], plando["Charts"], options, required_bosses,
  )

  assert {loc.name for loc in location_set.locations} == set(plando["Locations"]) - {"Defeat Ganondorf"}

  expected_bits = expected_salvage_bits_like_twwclient(plando["Charts"])
  for loc in location_set.locations:
    if loc.check.type == LocationType.CHART:
      bit = expected_bits[loc.name]
      assert (loc.check.address, loc.check.mask) == (CHARTS_BITFIELD_ADDR + 7 - bit//8, 1 << (bit % 8))
      assert loc.chart_name is not None

  any_cave_entrances = options["randomize_secret_cave_entrances"] or options["randomize_fairy_fountain_entrances"]
  cave_groups = [g for g in location_set.groups() if g.kind == GroupKind.CAVE]
  assert bool(cave_groups) == bool(any_cave_entrances)
