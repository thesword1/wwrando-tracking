# Host tests of the tracker C runtime's check detection, save data and per-frame update
# (asm/tracker/tracker_detect.c, tracker_save.c, tracker_runtime.c), with game memory mocked.
#
# Flags are set the way Archipelago's TWWClient.py reads them (whole big-endian bitfields and bit
# numbers from tracker/location_data.py), independently of the byte/mask resolution in
# tracker/locations.py that the C code uses.

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from tracker.location_data import LocationType
from tracker.locations import ISLAND_NUMBER_TO_NAME, SPECIAL_CHECKS, STATIC_LOCATIONS, SpecialCheck
from tracker.serialize import build_tracker_tables, serialize_tracker_tables
from test_aptww_fixtures import FIXTURES_DIR, load_plando
from test_tracker_serialize import tables_from_plando
from tracker_c_host import TrackerHost

SAVED_STAGE_INFO_ADDR = 0x803C4F88
LIVE_STAGE_INFO_ADDR = 0x803C5380
CURRENT_STAGE_ID_ADDR = 0x803C53A4
CHARTS_BITFIELD_ADDR = 0x803C4CFC
CURRENT_STAGE_NAME_ADDR = 0x803C9D3C
CURRENT_SPAWN_ADDR = 0x803C9D44
CURRENT_ROOM_ADDR = 0x803C9D46

SAVE_ADDR = 0x803C532C
SAVE_KEYS_ADDR = SAVE_ADDR + 0x04
SAVE_MANUAL_ADDR = SAVE_ADDR + 0x10
SAVE_VISITED_ADDR = SAVE_ADDR + 0x40

SEED_TAG = 0x1234

# TWWClient.py: (field offset in the stage info, field size in bytes).
STAGE_FIELDS = {
  LocationType.CHEST: (0x00, 4),
  LocationType.SWTCH: (0x04, 10),
  LocationType.PCKUP: (0x14, 4),
}


def all_locations_tables():
  return build_tracker_tables(STATIC_LOCATIONS, None, {}, None, None)

@pytest.fixture
def full(tracker: TrackerHost):
  """Tracker loaded with every location, vanilla charts, no entrances."""
  tables = all_locations_tables()
  tracker.set_tables(serialize_tracker_tables(tables, SEED_TAG))
  tracker.tables = tables
  return tracker

@pytest.fixture
def entrance_rando(tracker: TrackerHost):
  tables = tables_from_plando(load_plando(FIXTURES_DIR / "entrance_rando.aptww"))
  tracker.set_tables(serialize_tracker_tables(tables, SEED_TAG))
  tracker.tables = tables
  return tracker


def set_big_endian_bit(tracker: TrackerHost, address: int, size: int, bit: int):
  value = int.from_bytes(tracker.read_bytes(address, size), "big") | (1 << bit)
  tracker.write_bytes(address, value.to_bytes(size, "big"))

def set_location_flag(tracker: TrackerHost, location_name: str, live: bool = False):
  """Sets a location's flag as TWWClient.py reads it. live: the current stage's copy."""
  data = STATIC_LOCATIONS[location_name].data
  match data.type:
    case LocationType.CHEST | LocationType.SWTCH | LocationType.PCKUP:
      offset, size = STAGE_FIELDS[data.type]
      base = LIVE_STAGE_INFO_ADDR if live else SAVED_STAGE_INFO_ADDR + 0x24*data.stage_id
      set_big_endian_bit(tracker, base + offset, size, data.bit)
    case LocationType.CHART:
      set_big_endian_bit(tracker, CHARTS_BITFIELD_ADDR, 8, data.bit)
    case LocationType.BOCTO:
      set_big_endian_bit(tracker, data.address, 2, data.bit)
    case LocationType.EVENT:
      set_big_endian_bit(tracker, data.address, 1, data.bit)
    case _:
      raise ValueError(data.type)

def flag_key(location_name: str):
  data = STATIC_LOCATIONS[location_name].data
  if data.type in STAGE_FIELDS:
    return (data.type, data.stage_id, data.bit)
  if data.type == LocationType.CHART:
    return (data.type, data.bit)
  return (data.type, data.address, data.bit)

def auto_checked(tracker: TrackerHost) -> set[str]:
  return {loc.name for loc in tracker.tables.location_set.locations if tracker.lib.tracker_is_auto_checked(loc.index)}

def index_of(tracker: TrackerHost, location_name: str) -> int:
  return next(loc.index for loc in tracker.tables.location_set.locations if loc.name == location_name)

def enter_game(tracker: TrackerHost, stage_name: str = "sea", room: int = 44, spawn: int = 0):
  tracker.write_cstring(CURRENT_STAGE_NAME_ADDR, stage_name, 8)
  tracker.write_u8(CURRENT_ROOM_ADDR, room & 0xFF)
  tracker.write_u16(CURRENT_SPAWN_ADDR, spawn & 0xFFFF)


REGULAR_TYPES = [LocationType.CHEST, LocationType.SWTCH, LocationType.PCKUP, LocationType.CHART, LocationType.BOCTO, LocationType.EVENT]

@pytest.mark.parametrize("location_type", REGULAR_TYPES, ids=lambda t: t.name)
def test_saved_flags(full: TrackerHost, location_type: LocationType):
  names = [name for name, loc in STATIC_LOCATIONS.items() if loc.data.type == location_type]
  assert names
  full.write_u8(CURRENT_STAGE_ID_ADDR, 0xFF)
  for name in names:
    full.reset_ram()
    full.write_u8(CURRENT_STAGE_ID_ADDR, 0xFF)
    set_location_flag(full, name)
    expected = {other for other in STATIC_LOCATIONS if flag_key(other) == flag_key(name)}
    assert auto_checked(full) == expected, name

@pytest.mark.parametrize("location_type", list(STAGE_FIELDS), ids=lambda t: t.name)
def test_live_stage_flags(full: TrackerHost, location_type: LocationType):
  names = [name for name, loc in STATIC_LOCATIONS.items() if loc.data.type == location_type]
  for name in names:
    data = STATIC_LOCATIONS[name].data
    full.reset_ram()
    set_location_flag(full, name, live=True)
    # Only counts while the player is in that stage.
    other_stage = (data.stage_id + 1) % 0xE
    full.write_u8(CURRENT_STAGE_ID_ADDR, other_stage)
    assert name not in auto_checked(full)
    full.write_u8(CURRENT_STAGE_ID_ADDR, data.stage_id)
    expected = {other for other in STATIC_LOCATIONS if flag_key(other) == flag_key(name)}
    assert auto_checked(full) == expected, name

def test_chart_detection_follows_chart_mapping(tracker: TrackerHost):
  plando = load_plando(FIXTURES_DIR / "charts_required_bosses.aptww")
  tables = tables_from_plando(plando)
  tracker.set_tables(serialize_tracker_tables(tables, SEED_TAG))
  tracker.tables = tables
  sunken_treasures = [loc for loc in tables.location_set.locations if loc.check.type == LocationType.CHART]
  assert sunken_treasures
  for loc in sunken_treasures:
    tracker.reset_ram()
    # Salvaging with the chart that leads here in this seed sets that chart's vanilla island's bit.
    source_island = next(chart.vanilla_island_number for chart in tables.charts if chart.name == loc.chart_name)
    set_location_flag(tracker, f"{ISLAND_NUMBER_TO_NAME[source_island]} - Sunken Treasure")
    assert auto_checked(tracker) == {loc.name}

def test_none_type_is_never_auto_checked(full: TrackerHost):
  names = [name for name, loc in STATIC_LOCATIONS.items() if loc.data.type == LocationType.NONE]
  assert names
  full.write_bytes(0x803C4C08, b"\xFF" * 0x778) # Every save flag set
  for name in names:
    assert not full.lib.tracker_is_auto_checked(index_of(full, name))


SPECIAL_LOCATIONS = {special: name for name, (special, _) in SPECIAL_CHECKS.items()}

@pytest.mark.parametrize("value, checked", [(0x00, False), (0x02, False), (0x04, False), (0x06, True), (0x07, True), (0xFE, True)])
def test_lenzo_assistant(full: TrackerHost, value: int, checked: bool):
  name = SPECIAL_LOCATIONS[SpecialCheck.LENZO_ASSISTANT]
  full.write_u8(STATIC_LOCATIONS[name].data.address, value)
  assert full.lib.tracker_is_auto_checked(index_of(full, name)) == checked

@pytest.mark.parametrize("special", [SpecialCheck.LETTER_HOSKITS_GIRLFRIEND, SpecialCheck.LETTER_BAITOS_MOTHER, SpecialCheck.LETTER_GRANDMA], ids=lambda s: s.name)
@pytest.mark.parametrize("value, checked", [(0x00, False), (0x01, False), (0x02, False), (0x03, True), (0x07, True)])
def test_letters(full: TrackerHost, special: SpecialCheck, value: int, checked: bool):
  name = SPECIAL_LOCATIONS[special]
  full.write_u8(STATIC_LOCATIONS[name].data.address, value)
  assert auto_checked(full) == ({name} if checked else set())

def test_maggie_delivery(full: TrackerHost):
  index = index_of(full, SPECIAL_LOCATIONS[SpecialCheck.MAGGIE_DELIVERY])
  delivery_bag = 0x803C4C8E
  owned_bits = 0x803C4C98
  full.write_bytes(delivery_bag, b"\xFF" * 8)
  assert not full.lib.tracker_is_auto_checked(index) # Never owned Moblin's Letter
  full.write_u32(owned_bits, 1 << 15)
  for slot in range(8):
    full.write_u8(delivery_bag + slot, 0x9B)
    assert not full.lib.tracker_is_auto_checked(index) # Still in the bag
    full.write_u8(delivery_bag + slot, 0xFF)
  full.write_u8(delivery_bag + 3, 0x99) # Other letters don't matter
  assert full.lib.tracker_is_auto_checked(index)
  full.write_u32(owned_bits, 0xFFFFFFFF & ~(1 << 15))
  assert not full.lib.tracker_is_auto_checked(index)

@pytest.mark.parametrize("statue_1, statue_2, checked", [
  (0x40, 0x0F, True), (0xFF, 0xFF, True), (0x00, 0x0F, False), (0x40, 0x07, False), (0x40, 0x0E, False), (0xBF, 0xFF, False),
])
def test_ankle_all_statues(full: TrackerHost, statue_1: int, statue_2: int, checked: bool):
  index = index_of(full, SPECIAL_LOCATIONS[SpecialCheck.ANKLE_ALL_STATUES])
  full.write_u8(0x803C523E, statue_1)
  full.write_u8(0x803C5249, statue_2)
  assert full.lib.tracker_is_auto_checked(index) == checked

def test_out_of_range_and_invalid_tables(tracker: TrackerHost):
  lib = tracker.lib
  tracker.set_tables(bytes(0x100))
  assert not lib.tracker_is_auto_checked(0)
  assert not lib.tracker_toggle_manual(0)
  lib.tracker_frame()
  assert tracker.state.magic == 0
  assert tracker.read_bytes(SAVE_ADDR, 0x50) == bytes(0x50)
  tables = all_locations_tables()
  tracker.set_tables(serialize_tracker_tables(tables, SEED_TAG))
  assert not lib.tracker_is_auto_checked(len(tables.location_set.locations))
  assert not lib.tracker_toggle_manual(len(tables.location_set.locations))


def test_manual_marks(full: TrackerHost):
  lib = full.lib
  name = "Outset Island - Underneath Link's House"
  index = index_of(full, name)
  assert not lib.tracker_is_checked(index)
  assert lib.tracker_toggle_manual(index)
  assert lib.tracker_is_manual(index) and lib.tracker_is_checked(index)
  assert not lib.tracker_is_auto_checked(index)
  assert full.read_u8(SAVE_MANUAL_ADDR + (index >> 3)) == 1 << (index & 7)
  assert lib.tracker_toggle_manual(index)
  assert not lib.tracker_is_checked(index)
  assert full.read_bytes(SAVE_MANUAL_ADDR, 48) == bytes(48)

  # Auto-detected checks are locked: they can't be marked or unmarked.
  set_location_flag(full, name)
  assert lib.tracker_is_checked(index)
  assert not lib.tracker_toggle_manual(index)
  assert not lib.tracker_is_manual(index)

  last = len(full.tables.location_set.locations) - 1
  assert lib.tracker_toggle_manual(last)
  assert full.read_u8(SAVE_MANUAL_ADDR + (last >> 3)) == 1 << (last & 7)


def test_save_reset_on_new_or_other_seed(full: TrackerHost):
  lib = full.lib
  enter_game(full)
  lib.tracker_frame()
  assert full.state.save_resets == 1
  assert full.read_u8(SAVE_ADDR) == 1
  assert full.read_u16(SAVE_ADDR + 2) == SEED_TAG

  lib.tracker_toggle_manual(5)
  lib.tracker_count_small_key(2)
  lib.tracker_frame()
  assert lib.tracker_is_manual(5)
  assert full.state.save_resets == 1

  # A save from another seed.
  full.write_u16(SAVE_ADDR + 2, SEED_TAG + 1)
  lib.tracker_frame()
  assert full.state.save_resets == 2
  assert not lib.tracker_is_manual(5)
  assert lib.tracker_small_keys_obtained(2) == 0
  assert full.read_u16(SAVE_ADDR + 2) == SEED_TAG

  # A save from before the tracker existed (or with another layout).
  lib.tracker_toggle_manual(5)
  full.write_u8(SAVE_ADDR, 0)
  lib.tracker_frame()
  assert not lib.tracker_is_manual(5)

def test_no_save_changes_outside_gameplay(full: TrackerHost):
  lib = full.lib
  for stage_name in ["", "sea_T", "Name"]:
    enter_game(full, stage_name)
    lib.tracker_frame()
    assert not full.state.in_game
    assert full.read_bytes(SAVE_ADDR, 0x50) == bytes(0x50)
  assert full.state.magic == 0x54524B53
  assert full.state.frame_count == 3
  # Stage names that merely start with those are gameplay.
  enter_game(full, "Names")
  assert lib.tracker_is_in_game()


@pytest.mark.parametrize("dungeon", range(5))
def test_small_keys_obtained(full: TrackerHost, dungeon: int):
  lib = full.lib
  enter_game(full)
  lib.tracker_frame()
  for i in range(3):
    lib.tracker_count_small_key(dungeon)
  assert lib.tracker_small_keys_obtained(dungeon) == 3
  assert [lib.tracker_small_keys_obtained(d) for d in range(5)] == [3 if d == dungeon else 0 for d in range(5)]
  assert full.read_u8(SAVE_KEYS_ADDR + dungeon) == 3
  full.write_u8(SAVE_KEYS_ADDR + dungeon, 0xFF)
  lib.tracker_count_small_key(dungeon)
  assert lib.tracker_small_keys_obtained(dungeon) == 0xFF

def test_small_key_before_first_frame_initialises_save(full: TrackerHost):
  # A key from the starting items is given right after the new-game reset, before any frame.
  full.lib.tracker_count_small_key(0)
  assert full.read_u8(SAVE_ADDR) == 1
  assert full.lib.tracker_small_keys_obtained(0) == 1


def visited(tracker: TrackerHost) -> set[str]:
  return {e.entrance.name for e in tracker.tables.entrance_set.entrances if tracker.lib.tracker_is_entrance_visited(e.index)}

def test_entrance_triggers(entrance_rando: TrackerHost):
  tracker = entrance_rando
  lib = tracker.lib
  entrances = {e.entrance.name: e for e in tracker.tables.entrance_set.entrances}
  enter_game(tracker, "sea", 11, 0)
  lib.tracker_frame()
  assert visited(tracker) == set()
  assert tracker.state.last_visited_entrance == 0xFF

  # In this seed, the Secret Cave Entrance on Fire Mountain leads into Savage Labyrinth.
  enter_game(tracker, "Cave09", 0, 0)
  lib.tracker_frame()
  assert visited(tracker) == {"Secret Cave Entrance on Fire Mountain"}
  assert tracker.state.last_visited_entrance == entrances["Secret Cave Entrance on Fire Mountain"].index
  assert tracker.state.stage_name == b"Cave09"
  bit = entrances["Secret Cave Entrance on Fire Mountain"].index
  assert tracker.read_u8(SAVE_VISITED_ADDR + (bit >> 3)) & (1 << (bit & 7))

  # The deeper Savage Labyrinth stages count too. Leftover bytes after the name don't matter.
  tracker.reset_ram()
  tracker.write_bytes(CURRENT_STAGE_NAME_ADDR, b"Cave10\0X")
  lib.tracker_frame()
  assert visited(tracker) == {"Secret Cave Entrance on Fire Mountain"}

  # Every exit stage of the seed.
  for seed_entrance in tracker.tables.entrance_set.entrances:
    for trigger in seed_entrance.exit.triggers:
      tracker.reset_ram()
      enter_game(tracker, trigger.stage_name, trigger.room_num or 0, trigger.spawn_id or 0)
      lib.tracker_frame()
      assert visited(tracker) == {seed_entrance.entrance.name}, trigger

def test_cliff_plateau_inner_cave_trigger(entrance_rando: TrackerHost):
  tracker = entrance_rando
  lib = tracker.lib
  # In this seed, the Secret Cave Entrance on Overlook Island leads to Cliff Plateau Isles Inner Cave.
  for room, spawn in [(0x2A, 2), (0x29, 1), (0x2A, 0)]:
    tracker.reset_ram()
    enter_game(tracker, "sea", room, spawn)
    lib.tracker_frame()
    assert visited(tracker) == set(), (room, spawn)
  enter_game(tracker, "sea", 0x2A, 1)
  lib.tracker_frame()
  assert visited(tracker) == {"Secret Cave Entrance on Overlook Island"}
  assert tracker.state.room == 0x2A and tracker.state.spawn == 1

def test_visited_bits_persist_and_reset(entrance_rando: TrackerHost):
  tracker = entrance_rando
  enter_game(tracker, "Cave09")
  tracker.lib.tracker_frame()
  enter_game(tracker, "sea", 1, 0)
  tracker.lib.tracker_frame()
  assert visited(tracker) == {"Secret Cave Entrance on Fire Mountain"}
  tracker.write_u16(SAVE_ADDR + 2, 0) # Save from another seed
  tracker.lib.tracker_frame()
  assert visited(tracker) == set()


def test_group_counts(full: TrackerHost):
  lib = full.lib
  tables = full.tables
  groups = tables.groups()
  enter_game(full)
  lib.tracker_frame()
  assert full.state.num_locations == len(tables.location_set.locations)
  assert full.state.num_groups == len(groups)
  assert full.state.num_checked == 0

  set_location_flag(full, "Outset Island - Underneath Link's House")
  set_location_flag(full, "Outset Island - Mesa the Grasscutter's House")
  set_location_flag(full, "Dragon Roost Cavern - First Room")
  lib.tracker_toggle_manual(index_of(full, "Windfall Island - Jail - Maze Chest"))
  lib.tracker_frame()
  assert full.state.num_auto_checked == len(auto_checked(full))
  assert full.state.num_checked == full.state.num_auto_checked + 1

  for group_index, group in enumerate(groups):
    expected = sum(lib.tracker_is_checked(loc.index) for loc in tables.location_set.locations_in_group(group))
    assert full.state.group_checked[group_index] == expected, group.name
    assert full.group_counts(group_index) == (expected, len(tables.location_set.locations_in_group(group)))
  outset = next(i for i, g in enumerate(groups) if g.name == "Outset Island")
  windfall = next(i for i, g in enumerate(groups) if g.name == "Windfall Island")
  assert full.state.group_checked[outset] >= 2
  assert full.state.group_checked[windfall] >= 1
