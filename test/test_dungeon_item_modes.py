import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer
from options.wwrando_options import Options, KeyLunacyMode
from logic.item_types import DUNGEON_PROGRESS_ITEMS, DUNGEON_NONPROGRESS_ITEMS
from test_helpers import *

ALL_DUNGEON_ITEMS = DUNGEON_PROGRESS_ITEMS + DUNGEON_NONPROGRESS_ITEMS

def dry_rando(options, seed) -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

def mode_for(options: Options, item_name: str) -> KeyLunacyMode:
  if item_name.endswith(" Small Key"):
    return options.randomize_smallkeys
  elif item_name.endswith(" Big Key"):
    return options.randomize_bigkeys
  else:
    return options.randomize_mapcompass

def check_dungeon_item_placement(rando: WWRandomizer):
  logic = rando.logic
  options = rando.options
  banned_dungeons = rando.boss_reqs.banned_dungeons

  placed_locations: dict[str, list[str]] = {}
  for location_name, item_name in logic.done_item_locations.items():
    if item_name in ALL_DUNGEON_ITEMS:
      placed_locations.setdefault(item_name, []).append(location_name)

  for item_name in set(ALL_DUNGEON_ITEMS):
    mode = mode_for(options, item_name)
    num_items = ALL_DUNGEON_ITEMS.count(item_name)
    locations = placed_locations.get(item_name, [])
    dungeon_name = logic.DUNGEON_NAMES[item_name.split(" ")[0]]

    if mode == KeyLunacyMode.START_WITH:
      assert locations == [], item_name
      assert rando.starting_items.count(item_name) == num_items, item_name
      assert rando.get_starting_gear().count(item_name) == num_items, item_name
      continue

    assert len(locations) == num_items, item_name
    for location_name in locations:
      zone_name, _ = logic.split_location_name_by_zone(location_name)
      if mode == KeyLunacyMode.VANILLA:
        assert location_name in logic.vanilla_dungeon_item_locations[item_name], (item_name, location_name)
      elif mode == KeyLunacyMode.DUNGEON or (mode == KeyLunacyMode.ANY_DUNGEON and dungeon_name in banned_dungeons):
        assert logic.is_dungeon_location(location_name, dungeon_name_to_match=dungeon_name), (item_name, location_name)
      elif mode == KeyLunacyMode.ANY_DUNGEON:
        assert logic.is_dungeon_location(location_name), (item_name, location_name)
        assert zone_name not in banned_dungeons, (item_name, location_name)
      if mode in (KeyLunacyMode.DUNGEON, KeyLunacyMode.ANY_DUNGEON):
        assert "Boss" not in logic.item_locations[location_name]["Types"], (item_name, location_name)

MODES = list(KeyLunacyMode)

@pytest.mark.parametrize("mode", MODES, ids=[m.name for m in MODES])
@pytest.mark.parametrize("seed", ["keys1", "keys2"])
def test_all_dungeon_items_in_mode(mode, seed):
  options = Options()
  options.randomize_smallkeys = mode
  options.randomize_bigkeys = mode
  options.randomize_mapcompass = mode
  rando = dry_rando(options, seed)
  rando.randomize_all()
  check_dungeon_item_placement(rando)

MIXED_MODES = [
  (KeyLunacyMode.KEYLUNACY, KeyLunacyMode.DUNGEON, KeyLunacyMode.START_WITH),
  (KeyLunacyMode.ANY_DUNGEON, KeyLunacyMode.VANILLA, KeyLunacyMode.KEYLUNACY),
  (KeyLunacyMode.VANILLA, KeyLunacyMode.ANY_DUNGEON, KeyLunacyMode.DUNGEON),
  (KeyLunacyMode.START_WITH, KeyLunacyMode.LOCAL, KeyLunacyMode.ANY_DUNGEON),
  (KeyLunacyMode.DUNGEON, KeyLunacyMode.START_WITH, KeyLunacyMode.VANILLA),
]

@pytest.mark.parametrize("small_keys, big_keys, map_compass", MIXED_MODES)
@pytest.mark.parametrize("seed", ["mixed1", "mixed2", "mixed3"])
def test_mixed_dungeon_item_modes(small_keys, big_keys, map_compass, seed):
  options = Options()
  options.randomize_smallkeys = small_keys
  options.randomize_bigkeys = big_keys
  options.randomize_mapcompass = map_compass
  rando = dry_rando(options, seed)
  rando.randomize_all()
  check_dungeon_item_placement(rando)

@pytest.mark.parametrize("mode", [KeyLunacyMode.ANY_DUNGEON, KeyLunacyMode.DUNGEON, KeyLunacyMode.VANILLA])
@pytest.mark.parametrize("seed", ["reqboss1", "reqboss2", "reqboss3"])
def test_dungeon_item_modes_with_required_bosses(mode, seed):
  options = Options()
  options.required_bosses = True
  options.num_required_bosses = 3
  options.randomize_smallkeys = mode
  options.randomize_bigkeys = mode
  options.randomize_mapcompass = mode
  rando = dry_rando(options, seed)
  rando.randomize_all()
  check_dungeon_item_placement(rando)

@pytest.mark.parametrize("mode", [KeyLunacyMode.ANY_DUNGEON, KeyLunacyMode.START_WITH, KeyLunacyMode.KEYLUNACY])
def test_dungeon_item_modes_with_nested_entrances(mode):
  options = Options()
  options.randomize_dungeon_entrances = True
  options.randomize_boss_entrances = True
  options.randomize_miniboss_entrances = True
  options.randomize_smallkeys = mode
  options.randomize_bigkeys = mode
  options.randomize_mapcompass = mode
  rando = dry_rando(options, "nested")
  rando.randomize_all()
  check_dungeon_item_placement(rando)

@pytest.mark.parametrize("mode", [KeyLunacyMode.ANY_DUNGEON, KeyLunacyMode.VANILLA, KeyLunacyMode.START_WITH])
def test_dungeon_item_modes_without_progression_dungeons(mode):
  options = Options()
  options.progression_dungeons = False
  options.randomize_smallkeys = mode
  options.randomize_bigkeys = mode
  options.randomize_mapcompass = mode
  rando = dry_rando(options, "nodungeons")
  rando.randomize_all()
  check_dungeon_item_placement(rando)

def test_starting_map_in_starting_gear_is_not_duplicated():
  options = Options()
  options.randomize_mapcompass = KeyLunacyMode.START_WITH
  options.starting_gear = ["DRC Dungeon Map"]
  options.randomized_gear.remove("DRC Dungeon Map")
  rando = dry_rando(options, "startmap")
  assert rando.get_starting_gear().count("DRC Dungeon Map") == 1
  assert rando.starting_items.count("DRC Dungeon Map") == 1
