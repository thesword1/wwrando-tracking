# Patch-time entrance table for the in-game tracker.
#
# The randomizable entrances and exits come from randomizers/entrances.py. For each exit, the
# tracker needs the stage names whose visit means the player went through the entrance leading
# to it. That mapping follows the WWRando-APTracker website (src/data/stage-to-exit-mapping.json,
# src/services/entrance-auto-tracker.js) and Archipelago's TWWClient.py:
# - Every exit's own stage (ZoneExit.stage_name), plus the deeper Savage Labyrinth stages.
# - Cliff Plateau Isles Inner Cave exits onto the sea stage, so it's matched by stage "sea", room
#   0x2A, spawn 1 instead (TWWClient.py's "CliPlaH" dummy stage name).
# The website also maps "Abesso" (the Private Oasis cabana) to Cabana Labyrinth. That's left out:
# Abesso is where the Private Oasis cave entrance is, not where its exit leads (TF_04), so visiting
# it says nothing about where that entrance goes.
#
# Only entrances whose category is randomized are tracked, like the website. Each gets a
# "visited" bit index for the save data (docs/dev/memory-map.md).

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from logic.logic import Logic
from randomizers import entrances
from randomizers.entrances import ZoneEntrance, ZoneExit
from tracker.locations import (
  ENTRANCE_CATEGORIES, EXIT_TO_OPTION_NAME, GROUPS_BY_NAME, ISLAND_NAME_TO_NUMBER, VANILLA_EXIT_TO_ENTRANCE,
  GroupKind, TrackerGroup,
)

MAX_TRACKED_ENTRANCES = 64

SHORT_DUNGEON_NAMES = Logic.DUNGEON_NAME_TO_SHORT_DUNGEON_NAME

# Extra stages that also mean the exit was reached.
EXTRA_EXIT_STAGE_NAMES = {
  "Savage Labyrinth": ["Cave10", "Cave11"],
}
# Exits that lead onto a shared stage, matched by (stage, room, spawn) instead of the stage name.
EXIT_SPAWN_TRIGGERS = {
  "Cliff Plateau Isles Inner Cave": ("sea", 0x2A, 1),
}

ENTRANCE_DISPLAY_NAME_OVERRIDES = {
  "Dungeon Entrance in Tower of the Gods Sector": "TotG Sector Dungeon",
  "Miniboss Entrance in Hyrule Castle": "Hyrule Castle Miniboss Door",
  "Inner Entrance in Ice Ring Isle Secret Cave": "Ice Ring Inner Entrance",
  "Inner Entrance in Cliff Plateau Isles Secret Cave": "Cliff Plateau Inner Entrance",
}
EXIT_DISPLAY_NAME_OVERRIDES = {
  "Diamond Steppe Island Warp Maze Cave": "Diamond Steppe Warp Maze",
  "Cliff Plateau Isles Inner Cave": "Cliff Plateau Inner Cave",
}


def get_entrance_display_name(zone_entrance: ZoneEntrance) -> str:
  name = zone_entrance.entrance_name
  if name in ENTRANCE_DISPLAY_NAME_OVERRIDES:
    return ENTRANCE_DISPLAY_NAME_OVERRIDES[name]
  for prefix, suffix in [("Dungeon Entrance on ", " Dungeon"), ("Dungeon Entrance in ", " Dungeon"), ("Secret Cave Entrance on ", " Cave")]:
    if name.startswith(prefix):
      return name.removeprefix(prefix) + suffix
  for prefix, suffix in [("Miniboss Entrance in ", " Miniboss Door"), ("Boss Entrance in ", " Boss Door")]:
    if name.startswith(prefix):
      return SHORT_DUNGEON_NAMES[name.removeprefix(prefix)] + suffix
  if name.startswith("Fairy Fountain Entrance on "):
    # Same as the vanilla fountain's name, e.g. "Outset Fairy Fountain".
    return VANILLA_ENTRANCE_TO_EXIT[zone_entrance].unique_name
  raise NotImplementedError(f"No display name for entrance {name!r}")

def get_exit_display_name(zone_exit: ZoneExit) -> str:
  name = zone_exit.unique_name
  if name in EXIT_DISPLAY_NAME_OVERRIDES:
    return EXIT_DISPLAY_NAME_OVERRIDES[name]
  return name.replace(" Secret Cave", " Cave").replace(" Miniboss Arena", " Miniboss")


def get_exit_group(zone_exit: ZoneExit) -> TrackerGroup:
  """The tracker list-page group whose locations are behind this exit."""
  if zone_exit in entrances.DUNGEON_EXITS:
    return GROUPS_BY_NAME[(GroupKind.DUNGEON, zone_exit.zone_name)]
  if zone_exit.unique_name == "Master Sword Chamber":
    return GROUPS_BY_NAME[(GroupKind.ZONE, "Hyrule")]
  if zone_exit in entrances.MINIBOSS_EXITS or zone_exit in entrances.BOSS_EXITS:
    # Arenas belong to the dungeon their vanilla entrance is in.
    vanilla_entrance = VANILLA_EXIT_TO_ENTRANCE[zone_exit]
    if vanilla_entrance.is_nested:
      return GROUPS_BY_NAME[(GroupKind.DUNGEON, vanilla_entrance.nested_in.zone_name)]
    assert vanilla_entrance.island_name == "Forsaken Fortress Sector"
    return GROUPS_BY_NAME[(GroupKind.DUNGEON, "Forsaken Fortress")]
  return GROUPS_BY_NAME[(GroupKind.CAVE, zone_exit.unique_name)]


@dataclass(frozen=True)
class StageTrigger:
  stage_name: str
  # None matches any room/spawn.
  room_num: int | None = None
  spawn_id: int | None = None


@dataclass(frozen=True)
class TrackerEntrance:
  name: str
  display_name: str
  option_name: str
  # The sea square of an island entrance, or the exit an entrance is nested in.
  island_number: int | None
  nested_in: str | None
  vanilla_exit: str


@dataclass(frozen=True)
class TrackerExit:
  name: str
  display_name: str
  group: TrackerGroup
  triggers: tuple[StageTrigger, ...]


VANILLA_ENTRANCE_TO_EXIT = {entrance: zone_exit for zone_exit, entrance in VANILLA_EXIT_TO_ENTRANCE.items()}

def _build_entrances() -> dict[str, TrackerEntrance]:
  table = {}
  for zone_exit, zone_entrance in VANILLA_EXIT_TO_ENTRANCE.items():
    island_number = None if zone_entrance.is_nested else ISLAND_NAME_TO_NUMBER[zone_entrance.island_name]
    nested_in = zone_entrance.nested_in.unique_name if zone_entrance.is_nested else None
    table[zone_entrance.entrance_name] = TrackerEntrance(
      zone_entrance.entrance_name, get_entrance_display_name(zone_entrance), EXIT_TO_OPTION_NAME[zone_exit],
      island_number, nested_in, zone_exit.unique_name,
    )
  return table

def _build_exits() -> dict[str, TrackerExit]:
  table = {}
  for zone_exit in VANILLA_EXIT_TO_ENTRANCE:
    name = zone_exit.unique_name
    if name in EXIT_SPAWN_TRIGGERS:
      triggers = (StageTrigger(*EXIT_SPAWN_TRIGGERS[name]),)
    else:
      stage_names = [zone_exit.stage_name] + EXTRA_EXIT_STAGE_NAMES.get(name, [])
      triggers = tuple(StageTrigger(stage_name) for stage_name in stage_names)
    table[name] = TrackerExit(name, get_exit_display_name(zone_exit), get_exit_group(zone_exit), triggers)
  return table

ENTRANCES = _build_entrances()
EXITS = _build_exits()


@dataclass(frozen=True)
class SeedEntrance:
  # Index of the entrance's "visited" bit.
  index: int
  entrance: TrackerEntrance
  exit: TrackerExit


@dataclass(frozen=True)
class TrackerEntranceSet:
  entrances: list[SeedEntrance]

  def stage_triggers(self) -> list[tuple[StageTrigger, int]]:
    """Each stage trigger paired with the visited-bit index it sets."""
    return [(trigger, seed_entrance.index) for seed_entrance in self.entrances for trigger in seed_entrance.exit.triggers]


def entrance_pairings_from_randomizer(entrance_randomizer: entrances.EntranceRandomizer) -> dict[str, str]:
  """Entrance name -> exit name, in the same form as an .aptww plando's Entrances."""
  return {
    zone_entrance.entrance_name: zone_exit.unique_name
    for zone_entrance, zone_exit in entrance_randomizer.done_entrances_to_exits.items()
  }


def build_tracker_entrance_set(entrance_pairings: Mapping[str, str], entrance_options: Mapping[str, Any] | None) -> TrackerEntranceSet:
  """
  entrance_pairings: entrance name -> exit name (the plando's Entrances, or
    entrance_pairings_from_randomizer()).
  entrance_options: the randomize_*_entrances options (AP names), or None if nothing is randomized.
  """
  tracked = []
  for option_name, (category_entrances, _) in ENTRANCE_CATEGORIES.items():
    if not entrance_options or not entrance_options.get(option_name):
      continue
    for zone_entrance in category_entrances:
      exit_name = entrance_pairings[zone_entrance.entrance_name]
      tracked.append((ENTRANCES[zone_entrance.entrance_name], EXITS[exit_name]))

  assert len(tracked) <= MAX_TRACKED_ENTRANCES
  exit_names = [tracker_exit.name for _, tracker_exit in tracked]
  assert len(exit_names) == len(set(exit_names)), "Two tracked entrances lead to the same exit"
  return TrackerEntranceSet([
    SeedEntrance(i, tracker_entrance, tracker_exit)
    for i, (tracker_entrance, tracker_exit) in enumerate(tracked)
  ])
