import os
from collections import Counter
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer, InvalidOptionsError
from options.wwrando_options import Options
from logic.item_types import CONSUMABLE_ITEMS
from wwr_ui.inventory import INVENTORY_ITEMS
from test_helpers import *

def dry_rando(options, seed="pool") -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

# Item counts from the Archipelago TWW world's ITEM_TABLE (Items.py) for items that are placed as consumables.
APWORLD_CONSUMABLE_COUNTS = {
  "Green Rupee": 1, "Blue Rupee": 2, "Yellow Rupee": 3, "Red Rupee": 8, "Purple Rupee": 10,
  "Orange Rupee": 15, "Silver Rupee": 20, "Rainbow Rupee": 1,
  "Joy Pendant": 20, "Skull Necklace": 9, "Boko Baba Seed": 1, "Golden Feather": 9, "Knight's Crest": 3,
  "Red Chu Jelly": 1, "Green Chu Jelly": 1, "All-Purpose Bait": 1, "Hyoi Pear": 4,
}

def test_consumable_counts_match_apworld():
  assert Counter(CONSUMABLE_ITEMS) == APWORLD_CONSUMABLE_COUNTS

def test_capacity_upgrade_names():
  for item_name in ["Wallet Capacity Upgrade", "Bomb Bag Capacity Upgrade", "Quiver Capacity Upgrade"]:
    assert INVENTORY_ITEMS.count(item_name) == 2
  assert not any(item_name.startswith(("Progressive Wallet", "Progressive Bomb Bag", "Progressive Quiver")) for item_name in INVENTORY_ITEMS)

def test_inner_cave_entrances_need_both_secret_cave_types():
  options = Options()
  options.randomize_secret_cave_inner_entrances = True
  options.progression_puzzle_secret_caves = True
  options.progression_combat_secret_caves = False
  rando = dry_rando(options)
  assert not rando.options.randomize_secret_cave_inner_entrances
  
  options = Options()
  options.randomize_secret_cave_inner_entrances = True
  options.progression_puzzle_secret_caves = True
  options.progression_combat_secret_caves = True
  rando = dry_rando(options)
  assert rando.options.randomize_secret_cave_inner_entrances

@pytest.mark.parametrize("seed", ["charts1", "charts2"])
def test_start_with_charts(seed):
  options = Options()
  options.progression_triforce_charts = True
  options.progression_treasure_charts = True
  start_items = ["Triforce Chart 1", "Triforce Chart 5", "Treasure Chart 7"]
  options.starting_gear = start_items
  options.randomized_gear = [item for item in options.randomized_gear if item not in start_items]
  rando = dry_rando(options, seed)
  rando.randomize_all()
  placed_items = list(rando.logic.done_item_locations.values())
  for item_name in start_items:
    assert item_name in rando.starting_items
    assert item_name not in placed_items

def test_too_many_starting_items():
  options = Options()
  options.starting_gear = options.randomized_gear
  options.randomized_gear = []
  with pytest.raises(InvalidOptionsError, match="Too many starting items"):
    dry_rando(options)
