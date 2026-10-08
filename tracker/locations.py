# Patch-time location table for the in-game tracker.
#
# Every item location gets a group (where the tracker lists it) and a detection descriptor (which
# byte and bits of game memory say it has been checked). build_tracker_location_set() narrows the
# full table down to one seed's tracked locations and resolves the parts that depend on the seed.
#
# Groups:
# - Sea squares 1-49 (row-major, 1 = Forsaken Fortress Sector), for locations on or around an
#   island. Sunken Treasure locations are named after the island they are salvaged at, so they are
#   always on that island's square. Only which chart leads there (and so which salvage bit marks
#   them) depends on the seed.
# - List-page groups for everything that isn't on an island: one per dungeon (boss and miniboss
#   arenas belong to their dungeon, even when boss/miniboss entrances are randomized), Hyrule,
#   Ganon's Tower, Mailbox and The Great Sea.
# - One list-page group per secret cave, inner cave and fairy fountain. A cave's locations sit on
#   the square of its island entrance instead when no entrance on the way to the cave is
#   randomized in this seed. When any of them is randomized, the cave's location is unknown until
#   the player finds it, so the tracker lists it by cave name rather than spoiling where it is.
#   Which category of entrances is randomized comes from the options, never from the seed's actual
#   entrance pairings, so even a randomized entrance that happens to keep its vanilla destination
#   gives nothing away.
#
# Detection: see LocationType in tracker/location_data.py. Descriptors are resolved to absolute
# byte addresses with the same bit numbering as Archipelago's TWWClient.py.

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
import os
import re
from typing import Any

from logic.logic import Logic
from randomizers import entrances
from randomizers.entrances import ZoneEntrance, ZoneExit
from tracker.location_data import LOCATION_DATA, LocationData, LocationType
from wwrando_paths import DATA_PATH

SAVED_STAGE_INFO_ADDR = 0x803C4F88
STAGE_INFO_SIZE = 0x24
LIVE_STAGE_INFO_ADDR = 0x803C5380
CHARTS_BITFIELD_ADDR = 0x803C4CFC

# The goal "location" in Archipelago. It's not an item location and isn't tracked.
IGNORED_LOCATION_NAMES = {"Defeat Ganondorf"}


class SpecialCheck(Enum):
  # (address & 0x06) == 0x06. Archipelago also accepts 0x07, which implies the same.
  LENZO_ASSISTANT = 0
  # The flag is unknown. Checked once the player has owned Moblin's Letter (bit 15 of the
  # delivery bag owned bits at 0x803C4C98) and it is no longer in the delivery bag (8 bytes at
  # 0x803C4C8E, item 0x9B).
  MAGGIE_DELIVERY = 1
  # (address & 0x03) == 0x03: the letter was sent and read.
  LETTER_HOSKITS_GIRLFRIEND = 2
  LETTER_BAITOS_MOTHER = 3
  LETTER_GRANDMA = 4
  # (0x803C523E & 0x40) and (0x803C5249 & 0x0F) == 0x0F: all five Tingle statues rewarded.
  ANKLE_ALL_STATUES = 5

SPECIAL_CHECKS = {
  "Windfall Island - Lenzo's House - Become Lenzo's Assistant": (SpecialCheck.LENZO_ASSISTANT, 0x06),
  "Windfall Island - Maggie - Delivery Reward": (SpecialCheck.MAGGIE_DELIVERY, 0),
  "Mailbox - Letter from Hoskit's Girlfriend": (SpecialCheck.LETTER_HOSKITS_GIRLFRIEND, 0x03),
  "Mailbox - Letter from Baito's Mother": (SpecialCheck.LETTER_BAITOS_MOTHER, 0x03),
  "Mailbox - Letter from Grandma": (SpecialCheck.LETTER_GRANDMA, 0x03),
  "Tingle Island - Ankle - Reward for All Tingle Statues": (SpecialCheck.ANKLE_ALL_STATUES, 0),
}


class GroupKind(Enum):
  SQUARE = 0
  DUNGEON = 1
  ZONE = 2
  CAVE = 3


@dataclass(frozen=True)
class TrackerGroup:
  id: int
  kind: GroupKind
  name: str


@dataclass(frozen=True)
class CheckDescriptor:
  type: LocationType
  # The byte to test, and the bits in it that must all be set. For CHEST/SWTCH/PCKUP this is the
  # stage's saved copy. While the player is in that stage, the live copy (live_address) is
  # authoritative, so the runtime must test both.
  address: int | None
  mask: int
  stage_id: int | None = None
  special: SpecialCheck | None = None

  @property
  def live_address(self) -> int | None:
    if self.stage_id is None:
      return None
    return self.address - (SAVED_STAGE_INFO_ADDR + STAGE_INFO_SIZE*self.stage_id) + LIVE_STAGE_INFO_ADDR


@dataclass(frozen=True)
class TrackerLocation:
  index: int
  name: str
  display_name: str
  group: TrackerGroup
  check: CheckDescriptor
  # For Sunken Treasure: the chart that leads here in this seed.
  chart_name: str | None = None
  # For locations behind a randomizable entrance: the zone exit (dungeon, arena, cave or
  # fountain) that contains it.
  zone_exit: str | None = None


@dataclass(frozen=True)
class TrackerLocationSet:
  locations: list[TrackerLocation]

  def groups(self) -> list[TrackerGroup]:
    seen = {}
    for loc in self.locations:
      seen.setdefault(loc.group.id, loc.group)
    return list(seen.values())

  def locations_in_group(self, group: TrackerGroup) -> list[TrackerLocation]:
    return [loc for loc in self.locations if loc.group == group]


def _load_island_names() -> dict[int, str]:
  island_number_to_name = {}
  with open(os.path.join(DATA_PATH, "island_names.txt"), "r") as f:
    for room_arc_name, island_name in zip(f, f):
      island_number = int(re.search(r"Room(\d+)", room_arc_name).group(1))
      if 1 <= island_number <= 49:
        island_number_to_name[island_number] = island_name.strip()
  return island_number_to_name

ISLAND_NUMBER_TO_NAME = _load_island_names()
ISLAND_NAME_TO_NUMBER = {name: number for number, name in ISLAND_NUMBER_TO_NAME.items()}

# Vanilla chart for each island, from randomizers/charts.py.
VANILLA_ISLAND_NUMBER_TO_CHART_NAME = {
  1 : "Treasure Chart 25", 2 : "Treasure Chart 7",  3 : "Treasure Chart 24", 4 : "Triforce Chart 2",
  5 : "Treasure Chart 11", 6 : "Triforce Chart 7",  7 : "Treasure Chart 13", 8 : "Treasure Chart 41",
  9 : "Treasure Chart 29", 10: "Treasure Chart 22", 11: "Treasure Chart 18", 12: "Treasure Chart 30",
  13: "Treasure Chart 39", 14: "Treasure Chart 19", 15: "Treasure Chart 8",  16: "Treasure Chart 2",
  17: "Treasure Chart 10", 18: "Treasure Chart 26", 19: "Treasure Chart 3",  20: "Treasure Chart 37",
  21: "Treasure Chart 27", 22: "Treasure Chart 38", 23: "Triforce Chart 1",  24: "Treasure Chart 21",
  25: "Treasure Chart 6",  26: "Treasure Chart 14", 27: "Treasure Chart 34", 28: "Treasure Chart 5",
  29: "Treasure Chart 28", 30: "Treasure Chart 35", 31: "Triforce Chart 3",  32: "Triforce Chart 6",
  33: "Treasure Chart 1",  34: "Treasure Chart 20", 35: "Treasure Chart 36", 36: "Treasure Chart 23",
  37: "Treasure Chart 12", 38: "Treasure Chart 16", 39: "Treasure Chart 4",  40: "Treasure Chart 17",
  41: "Treasure Chart 31", 42: "Triforce Chart 5",  43: "Treasure Chart 9",  44: "Triforce Chart 4",
  45: "Treasure Chart 40", 46: "Triforce Chart 8",  47: "Treasure Chart 15", 48: "Treasure Chart 32",
  49: "Treasure Chart 33",
}

DUNGEON_ZONE_NAMES = list(Logic.DUNGEON_NAMES.values())
OTHER_ZONE_NAMES = ["Hyrule", "Ganon's Tower", "Mailbox", "The Great Sea"]
CAVE_EXITS = entrances.SECRET_CAVE_EXITS + entrances.SECRET_CAVE_INNER_EXITS + entrances.FAIRY_FOUNTAIN_EXITS

# Group IDs: 1-49 are sea squares, list-page groups follow.
SQUARE_GROUPS = [TrackerGroup(n, GroupKind.SQUARE, ISLAND_NUMBER_TO_NAME[n]) for n in range(1, 49+1)]
LIST_GROUPS = (
  [TrackerGroup(0, GroupKind.DUNGEON, name) for name in DUNGEON_ZONE_NAMES]
  + [TrackerGroup(0, GroupKind.ZONE, name) for name in OTHER_ZONE_NAMES]
  + [TrackerGroup(0, GroupKind.CAVE, ex.unique_name) for ex in CAVE_EXITS]
)
LIST_GROUPS = [TrackerGroup(50 + i, g.kind, g.name) for i, g in enumerate(LIST_GROUPS)]
ALL_GROUPS = SQUARE_GROUPS + LIST_GROUPS
GROUPS_BY_NAME = {(g.kind, g.name): g for g in ALL_GROUPS}

# Each entrance list in randomizers/entrances.py lines up with its exit list in vanilla.
ENTRANCE_CATEGORIES = {
  "randomize_dungeon_entrances": (entrances.DUNGEON_ENTRANCES, entrances.DUNGEON_EXITS),
  "randomize_miniboss_entrances": (entrances.MINIBOSS_ENTRANCES, entrances.MINIBOSS_EXITS),
  "randomize_boss_entrances": (entrances.BOSS_ENTRANCES, entrances.BOSS_EXITS),
  "randomize_secret_cave_entrances": (entrances.SECRET_CAVE_ENTRANCES, entrances.SECRET_CAVE_EXITS),
  "randomize_secret_cave_inner_entrances": (entrances.SECRET_CAVE_INNER_ENTRANCES, entrances.SECRET_CAVE_INNER_EXITS),
  "randomize_fairy_fountain_entrances": (entrances.FAIRY_FOUNTAIN_ENTRANCES, entrances.FAIRY_FOUNTAIN_EXITS),
}
VANILLA_EXIT_TO_ENTRANCE: dict[ZoneExit, ZoneEntrance] = {}
EXIT_TO_OPTION_NAME: dict[ZoneExit, str] = {}
for _option_name, (_entrances, _exits) in ENTRANCE_CATEGORIES.items():
  assert len(_entrances) == len(_exits)
  for _entrance, _exit in zip(_entrances, _exits):
    VANILLA_EXIT_TO_ENTRANCE[_exit] = _entrance
    EXIT_TO_OPTION_NAME[_exit] = _option_name


def get_zone_exit_for_location(location_name: str, types: list[str]) -> ZoneExit | None:
  # Mirrors EntranceRandomizer.get_zone_exit_for_item_location (and
  # is_item_location_behind_randomizable_entrance), which need a randomizer instance.
  zone_name, _ = Logic.split_location_name_by_zone(location_name)
  if zone_name in ["Ganon's Tower", "Mailbox"]:
    return None
  if zone_name == "Forsaken Fortress" and "Boss" not in types:
    return None
  if "Big Octo" in types:
    return None
  if not any(t in entrances.ENTRANCE_RANDOMIZABLE_ITEM_LOCATION_TYPES for t in types):
    return None

  zone_exit = entrances.ITEM_LOCATION_NAME_TO_EXIT_OVERRIDES.get(location_name)
  if zone_exit is not None:
    return zone_exit
  possible_exits = [ex for ex in ZoneExit.all.values() if ex.zone_name == zone_name]
  assert len(possible_exits) <= 1, f"Multiple zone exits share the zone name {zone_name!r}"
  return possible_exits[0] if possible_exits else None


@dataclass(frozen=True)
class _StaticLocation:
  name: str
  zone: str
  data: LocationData
  zone_exit: ZoneExit | None

def _load_static_locations() -> dict[str, _StaticLocation]:
  item_locations = Logic.load_and_parse_item_locations()
  assert list(item_locations) == list(LOCATION_DATA), "tracker/location_data.py is out of sync with logic/item_locations.txt"
  static_locations = {}
  for name, data in LOCATION_DATA.items():
    zone, _ = Logic.split_location_name_by_zone(name)
    zone_exit = get_zone_exit_for_location(name, item_locations[name]["Types"])
    static_locations[name] = _StaticLocation(name, zone, data, zone_exit)
  return static_locations

STATIC_LOCATIONS = _load_static_locations()


def resolve_check(location_name: str, data: LocationData, salvage_bit: int | None = None) -> CheckDescriptor:
  bit = data.bit
  match data.type:
    case LocationType.CHEST:
      stage_base = SAVED_STAGE_INFO_ADDR + STAGE_INFO_SIZE*data.stage_id
      return CheckDescriptor(data.type, stage_base + 0x00 + 3 - bit//8, 1 << (bit % 8), stage_id=data.stage_id)
    case LocationType.SWTCH:
      # Archipelago reads 10 bytes from +0x04 as one big-endian integer.
      stage_base = SAVED_STAGE_INFO_ADDR + STAGE_INFO_SIZE*data.stage_id
      return CheckDescriptor(data.type, stage_base + 0x04 + 9 - bit//8, 1 << (bit % 8), stage_id=data.stage_id)
    case LocationType.PCKUP:
      stage_base = SAVED_STAGE_INFO_ADDR + STAGE_INFO_SIZE*data.stage_id
      return CheckDescriptor(data.type, stage_base + 0x14 + 3 - bit//8, 1 << (bit % 8), stage_id=data.stage_id)
    case LocationType.CHART:
      # Archipelago reads 8 bytes from 0x803C4CFC as one big-endian integer.
      if salvage_bit is not None:
        bit = salvage_bit
      return CheckDescriptor(data.type, CHARTS_BITFIELD_ADDR + 7 - bit//8, 1 << (bit % 8))
    case LocationType.BOCTO:
      return CheckDescriptor(data.type, data.address + 1 - bit//8, 1 << (bit % 8))
    case LocationType.EVENT:
      return CheckDescriptor(data.type, data.address, 1 << bit)
    case LocationType.SPECL:
      special, mask = SPECIAL_CHECKS[location_name]
      return CheckDescriptor(data.type, data.address, mask, special=special)
    case LocationType.NONE:
      return CheckDescriptor(data.type, None, 0)
  raise NotImplementedError(f"Unknown location type: {data.type}")


def get_randomized_exits(entrance_options: Mapping[str, Any] | None) -> set[ZoneExit]:
  """Exits whose entrance category is randomized by the given options (AP option names)."""
  randomized = set()
  if entrance_options is None:
    return randomized
  for option_name, (_, exits) in ENTRANCE_CATEGORIES.items():
    if entrance_options.get(option_name):
      randomized.update(exits)
  return randomized


def _is_cave_location_known(zone_exit: ZoneExit, randomized_exits: set[ZoneExit]) -> bool:
  # Walk out from the exit to the island entrance through any nesting (inner caves).
  while True:
    if zone_exit in randomized_exits:
      return False
    zone_entrance = VANILLA_EXIT_TO_ENTRANCE[zone_exit]
    if not zone_entrance.is_nested:
      return True
    zone_exit = zone_entrance.nested_in

def _outermost_island_name(zone_exit: ZoneExit) -> str:
  zone_entrance = VANILLA_EXIT_TO_ENTRANCE[zone_exit]
  while zone_entrance.is_nested:
    zone_entrance = VANILLA_EXIT_TO_ENTRANCE[zone_entrance.nested_in]
  return zone_entrance.island_name


def get_cave_group(zone_exit: ZoneExit, randomized_exits: set[ZoneExit]) -> TrackerGroup:
  """The group of a cave's or fairy fountain's locations: its own group if it's behind a randomized entrance, else
  its island's square."""
  if not _is_cave_location_known(zone_exit, randomized_exits):
    return GROUPS_BY_NAME[(GroupKind.CAVE, zone_exit.unique_name)]
  island_name = _outermost_island_name(zone_exit)
  return SQUARE_GROUPS[ISLAND_NAME_TO_NUMBER[island_name] - 1]


def get_group(location_name: str, randomized_exits: set[ZoneExit]) -> TrackerGroup:
  loc = STATIC_LOCATIONS[location_name]
  if loc.zone in DUNGEON_ZONE_NAMES:
    return GROUPS_BY_NAME[(GroupKind.DUNGEON, loc.zone)]
  if loc.zone in OTHER_ZONE_NAMES:
    return GROUPS_BY_NAME[(GroupKind.ZONE, loc.zone)]
  if loc.zone_exit is not None and loc.zone_exit in CAVE_EXITS:
    return get_cave_group(loc.zone_exit, randomized_exits)
  return SQUARE_GROUPS[ISLAND_NAME_TO_NUMBER[loc.zone] - 1]


def get_chart_destinations(chart_mapping: Sequence[int] | None) -> dict[int, int]:
  """
  Maps each destination island number to the island number whose vanilla chart now leads there.
  chart_mapping is the plando's Charts list: entry i-1 is where island i's vanilla chart leads.
  """
  if chart_mapping is None:
    return {n: n for n in range(1, 49+1)}
  assert sorted(chart_mapping) == list(range(1, 49+1)), "Chart mapping must be a permutation of 1-49"
  return {destination: i + 1 for i, destination in enumerate(chart_mapping)}


def build_tracker_location_set(
  active_location_names: Iterable[str],
  chart_mapping: Sequence[int] | None = None,
  entrance_options: Mapping[str, Any] | None = None,
  required_bosses: Iterable[str] | None = None,
) -> TrackerLocationSet:
  """
  Builds the ordered table of tracked locations for one seed.

  active_location_names: the seed's progress locations (AP mode: the plando's Locations keys).
  chart_mapping: the plando's Charts list, or None for vanilla charts.
  entrance_options: the randomize_*_entrances options (AP names), or None if nothing is randomized.
  required_bosses: None when Required Bosses mode is off. Otherwise the required bosses, given as
    boss location names (the plando's Required Bosses) or dungeon names. Locations in the other
    dungeons are hidden.
  """
  active = set(active_location_names) - IGNORED_LOCATION_NAMES
  unknown = active - set(STATIC_LOCATIONS)
  if unknown:
    raise KeyError(f"Unknown location names: {sorted(unknown)}")

  if required_bosses is not None:
    required_dungeons = {Logic.split_location_name_by_zone(name)[0] for name in required_bosses}
    hidden_dungeons = set(DUNGEON_ZONE_NAMES) - required_dungeons
    active = {name for name in active if STATIC_LOCATIONS[name].zone not in hidden_dungeons}

  randomized_exits = get_randomized_exits(entrance_options)
  chart_destinations = get_chart_destinations(chart_mapping)

  unordered = []
  for name, loc in STATIC_LOCATIONS.items():
    if name not in active:
      continue
    salvage_bit = None
    chart_name = None
    if loc.data.type == LocationType.CHART:
      island_number = ISLAND_NAME_TO_NUMBER[loc.zone]
      source_island_number = chart_destinations[island_number]
      source_location_name = f"{ISLAND_NUMBER_TO_NAME[source_island_number]} - Sunken Treasure"
      salvage_bit = LOCATION_DATA[source_location_name].bit
      chart_name = VANILLA_ISLAND_NUMBER_TO_CHART_NAME[source_island_number]
    group = get_group(name, randomized_exits)
    check = resolve_check(name, loc.data, salvage_bit)
    zone_exit = loc.zone_exit.unique_name if loc.zone_exit else None
    unordered.append((group, name, loc.data.display_name, check, chart_name, zone_exit))

  # Order by group, keeping logic order within a group.
  unordered.sort(key=lambda entry: entry[0].id)
  locations = [
    TrackerLocation(i, name, display_name, group, check, chart_name, zone_exit)
    for i, (group, name, display_name, check, chart_name, zone_exit) in enumerate(unordered)
  ]
  return TrackerLocationSet(locations)
