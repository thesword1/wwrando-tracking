import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer
from options.wwrando_options import Options, SwordMode
from test_helpers import *

def dry_rando(options, seed) -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

def test_swords_optional_logic_ignores_swords():
  options = Options()
  options.sword_mode = SwordMode.SWORDS_OPTIONAL
  rando = dry_rando(options, "swordsopt")
  logic = rando.logic
  assert "Progressive Sword" not in rando.starting_items
  assert "Progressive Sword" not in logic.all_progress_items
  assert logic.all_nonprogress_items.count("Progressive Sword") == 4
  assert logic.check_requirement_met("In Swordless Mode")
  assert not logic.check_requirement_met("Outside Swordless Mode")
  # Even owning every sword doesn't satisfy sword requirements, like the APWorld's swords being useful items.
  with logic.add_temporary_items(["Progressive Sword"]*4):
    assert not logic.check_requirement_met("Hero's Sword")
    assert not logic.check_requirement_met("Full Power Master Sword")

@pytest.mark.parametrize("seed", ["swordsopt1", "swordsopt2", "swordsopt3", "swordsopt4"])
def test_swords_optional_seeds(seed):
  options = Options()
  options.sword_mode = SwordMode.SWORDS_OPTIONAL
  rando = dry_rando(options, seed)
  rando.randomize_all()
  placed_items = list(rando.logic.done_item_locations.values())
  assert placed_items.count("Progressive Sword") == 4
  # The swords are never part of the playthrough.
  spheres = rando.items.calculate_playthrough_progression_spheres()
  assert all("Progressive Sword" not in sphere.values() for sphere in spheres)

def test_swords_optional_all_progression_locations():
  options = Options()
  enable_all_progression_location_options(options)
  options.sword_mode = SwordMode.SWORDS_OPTIONAL
  rando = dry_rando(options, "swordsoptall")
  rando.randomize_all()

@pytest.mark.parametrize("sword_mode", [SwordMode.START_WITH_SWORD, SwordMode.NO_STARTING_SWORD])
def test_swords_count_in_other_modes(sword_mode):
  options = Options()
  options.sword_mode = sword_mode
  rando = dry_rando(options, "swords")
  logic = rando.logic
  assert logic.check_requirement_met("Outside Swordless Mode")
  with logic.add_temporary_items(["Progressive Sword"]*(4 - rando.starting_items.count("Progressive Sword"))):
    assert logic.check_requirement_met("Full Power Master Sword")
