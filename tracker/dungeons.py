# Patch-time dungeon key table for the in-game tracker: the header of a dungeon's location list shows the small keys
# obtained out of the dungeon's total (`Keys 2/4`) and whether its big key is owned (`BK`), like the website's dungeon
# tiles (WWRando-APTracker src/ui/extra-location.jsx).
#
# The totals come from logic/item_locations.txt: a dungeon has as many small keys (and big keys) as it has locations
# whose "Original item" is one. Every placement mode keeps them in the item pool, so that's the seed's count too.
# Obtained small keys are the tracker's own counters (D12); the big key is the dungeon's mDungeonItem bit, read like the
# logic's big key items (tracker/items.py).

from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntFlag

from logic.logic import Logic
from options.wwrando_options import KeyLunacyMode, Options
from tracker.items import DUNGEON_KEY_COUNTERS, DUNGEON_STAGE_IDS
from tracker.locations import GROUPS_BY_NAME, GroupKind, TrackerGroup


class DungeonFlag(IntFlag):
  HAS_BIG_KEY = 0x01
  # Start With modes: the keys are given with the new game, so they're shown as all obtained / owned.
  START_WITH_SMALL_KEYS = 0x02
  START_WITH_BIG_KEY = 0x04


@dataclass(frozen=True)
class TrackerDungeon:
  group: TrackerGroup
  short_name: str
  small_keys: int
  flags: DungeonFlag

  @property
  def counter_index(self) -> int:
    """Index of the dungeon's small-keys-obtained counter in the save data (enum TrkDungeon)."""
    return DUNGEON_KEY_COUNTERS[self.short_name]

  @property
  def stage_id(self) -> int:
    return DUNGEON_STAGE_IDS[self.short_name]


def dungeon_key_totals() -> dict[str, tuple[int, int]]:
  """Short dungeon name -> (small keys, big keys) in the vanilla item locations."""
  totals = {short_name: [0, 0] for short_name in Logic.DUNGEON_NAMES}
  for location_name, location_data in Logic.load_and_parse_item_locations().items():
    original_item = location_data.get("Original item")
    if original_item not in ("Small Key", "Big Key"):
      continue
    zone_name, _ = Logic.split_location_name_by_zone(location_name)
    short_name = Logic.DUNGEON_NAME_TO_SHORT_DUNGEON_NAME[zone_name]
    totals[short_name][original_item == "Big Key"] += 1
  return {short_name: (small, big) for short_name, (small, big) in totals.items()}


def build_tracker_dungeons(groups: Iterable[TrackerGroup], options: Options | None) -> list[TrackerDungeon]:
  """The dungeons among groups (the tables' groups) that have small keys or a big key. options gives the key
  placement modes; without it neither is Start With."""
  group_ids = {group.id for group in groups}
  dungeons = []
  for short_name, (small_keys, big_keys) in dungeon_key_totals().items():
    group = GROUPS_BY_NAME[(GroupKind.DUNGEON, Logic.DUNGEON_NAMES[short_name])]
    if group.id not in group_ids or (small_keys == 0 and big_keys == 0):
      continue
    assert short_name in DUNGEON_KEY_COUNTERS, short_name
    flags = DungeonFlag(0)
    if big_keys:
      flags |= DungeonFlag.HAS_BIG_KEY
    if options is not None and options.randomize_smallkeys == KeyLunacyMode.START_WITH:
      flags |= DungeonFlag.START_WITH_SMALL_KEYS
    if options is not None and options.randomize_bigkeys == KeyLunacyMode.START_WITH:
      flags |= DungeonFlag.START_WITH_BIG_KEY
    dungeons.append(TrackerDungeon(group, short_name, small_keys, flags))
  return sorted(dungeons, key=lambda dungeon: dungeon.group.id)
