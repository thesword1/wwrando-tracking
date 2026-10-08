# Patch-time stage-to-group table for the in-game tracker.
#
# In a dungeon the sea chart can't be opened, so the tracker's location list is also shown from the dungeon map and
# the Quest Status screen (asm/tracker/tracker_ui_menu.c). Both open the list of the group the player is in, found
# by the current stage's name:
# - Every stage of a dungeon, including its miniboss and boss arenas (even when those entrances are randomized: an
#   arena's locations belong to its dungeon), and of Hyrule and Ganon's Tower.
# - Secret caves, inner caves and fairy fountains: the group their locations are in in this seed, which is the cave's
#   own group when an entrance on the way there is randomized and its island's square otherwise.
# - Any other stage whose tracked locations are all in one group, from the location paths in
#   logic/item_locations.txt (for example Lenzo's House, on Windfall Island's square). Stages with locations in
#   several groups (the submarines, "sea") are left out.
# The stage identifies the dungeon or cave itself, not the entrance the player came through, so this doesn't spoil
# randomized entrances.

from collections.abc import Mapping
import os

from logic.logic import Logic
from randomizers.entrances import ZoneExit
from tracker.entrances import EXIT_SPAWN_TRIGGERS, EXTRA_EXIT_STAGE_NAMES
from tracker.locations import (
  CAVE_EXITS, GROUPS_BY_NAME, STATIC_LOCATIONS, GroupKind, TrackerGroup, get_cave_group, get_group,
)
from wwrando_paths import DATA_PATH

ZONE_STAGE_NAMES = {
  (GroupKind.DUNGEON, "Dragon Roost Cavern"): ["M_NewD2", "M_Dra09", "M_DragB"],
  (GroupKind.DUNGEON, "Forbidden Woods"): ["kindan", "kinMB", "kinBOSS"],
  (GroupKind.DUNGEON, "Tower of the Gods"): ["Siren", "SirenMB", "SirenB"],
  (GroupKind.DUNGEON, "Forsaken Fortress"): ["MajyuE", "majroom", "ma2room", "ma3room", "Mjtower", "M2tower", "M2ganon"],
  (GroupKind.DUNGEON, "Earth Temple"): ["M_Dai", "M_DaiMB", "M_DaiB"],
  (GroupKind.DUNGEON, "Wind Temple"): ["kaze", "kazeMB", "kazeB"],
  (GroupKind.ZONE, "Hyrule"): ["Hyrule", "Hyroom", "kenroom"],
  (GroupKind.ZONE, "Ganon's Tower"): [
    "GanonA", "GanonB", "GanonC", "GanonD", "GanonE", "GanonJ", "GanonK", "GanonL", "GanonM", "GanonN", "GTower",
    "Xboss0", "Xboss1", "Xboss2", "Xboss3",
  ],
}

# Stages that are never a single group.
SHARED_STAGE_NAMES = {"sea"}


def _load_stage_names() -> set[str]:
  with open(os.path.join(DATA_PATH, "stage_names.txt"), "r") as f:
    return {stage_name.strip() for stage_name, _ in zip(f, f)}

STAGE_NAMES = _load_stage_names()


def _location_stage_names() -> dict[str, set[str]]:
  """Location name -> the stages its item is placed in (from its paths)."""
  item_locations = Logic.load_and_parse_item_locations()
  result = {}
  for location_name in STATIC_LOCATIONS:
    stages = set()
    for path in item_locations[location_name]["Paths"]:
      stage_name = path.split("/")[0]
      if stage_name in STAGE_NAMES and stage_name not in SHARED_STAGE_NAMES:
        stages.add(stage_name)
    result[location_name] = stages
  return result

LOCATION_STAGE_NAMES = _location_stage_names()


def build_stage_groups(randomized_exits: set[ZoneExit]) -> dict[str, TrackerGroup]:
  """Stage name -> the group whose list the dungeon map and Quest Status screens open there."""
  from_locations: dict[str, set[TrackerGroup]] = {}
  for location_name, stage_names in LOCATION_STAGE_NAMES.items():
    group = get_group(location_name, randomized_exits)
    for stage_name in stage_names:
      from_locations.setdefault(stage_name, set()).add(group)
  stage_groups = {stage_name: next(iter(groups)) for stage_name, groups in from_locations.items() if len(groups) == 1}

  for zone_exit in CAVE_EXITS:
    if zone_exit.unique_name in EXIT_SPAWN_TRIGGERS:
      continue # Exits onto a shared stage
    group = get_cave_group(zone_exit, randomized_exits)
    for stage_name in [zone_exit.stage_name] + EXTRA_EXIT_STAGE_NAMES.get(zone_exit.unique_name, []):
      stage_groups[stage_name] = group

  for key, stage_names in ZONE_STAGE_NAMES.items():
    for stage_name in stage_names:
      stage_groups[stage_name] = GROUPS_BY_NAME[key]
  return stage_groups


def stage_group_entries(stage_groups: Mapping[str, TrackerGroup], group_ids: set[int]) -> list[tuple[str, int]]:
  """The (stage name, group ID) entries of the STAGES section: only groups in the tables, sorted by stage name."""
  return sorted((stage_name, group.id) for stage_name, group in stage_groups.items() if group.id in group_ids)
