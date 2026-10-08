import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer
from options.wwrando_options import Options
from aptww import read_ap_plando_file
from test_helpers import *

TINGLE_CHEST = "Dragon Roost Cavern - Tingle Chest in Hub Room"

def dry_rando(options, seed="tuner") -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

@pytest.mark.parametrize("enable_tuner_logic", [False, True])
def test_tingle_bombs_macro(enable_tuner_logic):
  options = Options()
  options.enable_tuner_logic = enable_tuner_logic
  logic = dry_rando(options).logic
  assert not logic.check_requirement_met("Tingle Bombs")
  with logic.add_temporary_items(["Tingle Tuner"]):
    assert logic.check_requirement_met("Tingle Bombs") == enable_tuner_logic
  with logic.add_temporary_items(["Bombs"]):
    assert logic.check_requirement_met("Tingle Bombs")

def test_tuner_is_only_progress_with_tuner_logic():
  options = Options()
  options.progression_tingle_chests = True
  assert "Tingle Tuner" not in dry_rando(options).logic.all_progress_items
  options.enable_tuner_logic = True
  assert "Tingle Tuner" in dry_rando(options).logic.all_progress_items

@pytest.mark.parametrize("seed", ["tuner1", "tuner2", "tuner3"])
def test_tuner_logic_seeds(seed):
  options = Options()
  options.progression_tingle_chests = True
  options.enable_tuner_logic = True
  rando = dry_rando(options, seed)
  rando.randomize_all()

def test_tuner_logic_is_a_local_setting_for_archipelago(tmp_path):
  # .aptww files don't contain enable_tuner_logic, so the local setting is kept.
  fixture = os.path.join(os.path.dirname(__file__), "fixtures", "aptww", "keys_swords_tuner.aptww")
  options = Options()
  options.enable_tuner_logic = True
  options.trap_chests = True
  read_ap_plando_file(fixture, options)
  assert options.enable_tuner_logic
  # Other gameplay options missing from the file are reset.
  assert not options.trap_chests
