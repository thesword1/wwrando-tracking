# Parity between offline seeds and the Archipelago TWW world (APWorld 3.0.0).
#
# - The progress locations of offline seeds must be the APWorld's progress locations for the same options. This is
#   checked exhaustively for the progression location categories against the APWorld's location flags
#   (fixtures/apworld_location_flags.json, dumped by tools/parity/dump_apworld_location_flags.py), and for whole option
#   sets against the Locations of the .aptww fixtures (with the fixture's chart mapping and required bosses).
# - Offline seeds generated with each fixture's options must be beatable.
#
# Known differences that don't affect the progress locations (see PROJECT_PLAN.md / CHANGELOG.md):
# - Dungeon items are never placed on bosses offline (the APWorld allows it when boss entrances aren't randomized).
# - Offline seeds give every non-progress location a random item; the APWorld only has its progress locations.
# - The APWorld forces dungeons with priority locations to be required bosses; there are no priority locations offline.

import json
import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer
from aptww import read_ap_plando_file
from logic.logic import Logic
from options.wwrando_options import Options
from test_helpers import *

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
APTWW_FIXTURES = sorted(name.removesuffix(".aptww") for name in os.listdir(os.path.join(FIXTURES_DIR, "aptww")))

# Which option makes the locations with each APWorld flag progress locations (APWorld __init__.py,
# _determine_progress_and_nonprogress_locations).
FLAG_OPTIONS = {
  "ALWAYS": None,
  "DUNGEON": "progression_dungeons",
  "BOSS": "progression_dungeons",
  "TNGL_CT": "progression_tingle_chests",
  "DG_SCRT": "progression_dungeon_secrets",
  "PZL_CVE": "progression_puzzle_secret_caves",
  "CBT_CVE": "progression_combat_secret_caves",
  "SAVAGE": "progression_savage_labyrinth",
  "GRT_FRY": "progression_great_fairies",
  "SHRT_SQ": "progression_short_sidequests",
  "LONG_SQ": "progression_long_sidequests",
  "SPOILS": "progression_spoils_trading",
  "MINIGME": "progression_minigames",
  "SPLOOSH": "progression_battlesquid",
  "FREE_GF": "progression_free_gifts",
  "MAILBOX": "progression_mail",
  "PLTFRMS": "progression_platforms_rafts",
  "SUBMRIN": "progression_submarines",
  "EYE_RFS": "progression_eye_reef_chests",
  "BG_OCTO": "progression_big_octos_gunboats",
  "XPENSVE": "progression_expensive_purchases",
  "ISLND_P": "progression_island_puzzles",
  "MISCELL": "progression_misc",
}
# Sunken treasure flags depend on which chart leads to the island, see test_progress_locations_match_aptww_fixture.
CHART_FLAGS = {"TRI_CHT", "TRE_CHT"}

# The enable_tuner_logic option isn't in .aptww files, so it's taken from the fixtures' YAMLs.
FIXTURE_LOCAL_OPTIONS = {
  "keys_swords_tuner": {"enable_tuner_logic": True},
}

def load_apworld_location_flags() -> dict[str, list[str]]:
  with open(os.path.join(FIXTURES_DIR, "apworld_location_flags.json")) as f:
    return json.load(f)["locations"]

def all_progression_options() -> Options:
  options = Options()
  enable_all_progression_location_options(options)
  return options

def test_location_names_match_apworld():
  apworld_locations = set(load_apworld_location_flags())
  item_locations = Logic.load_and_parse_item_locations()
  # Every APWorld location exists offline. The offline-only ones can never have progress items.
  assert apworld_locations <= set(item_locations)
  progress_locations = Logic.filter_locations_for_progression_static(
    list(item_locations), item_locations, all_progression_options(),
  )
  assert set(progress_locations) == apworld_locations

def test_progression_categories_match_apworld_flags():
  # A location is a progress location if all of its categories are enabled, offline and in the APWorld. So comparing
  # the categories each location needs covers every combination of the progression location options.
  location_flags = load_apworld_location_flags()
  item_locations = Logic.load_and_parse_item_locations()
  locations = [name for name, flags in location_flags.items() if not CHART_FLAGS & set(flags)]
  
  offline_options_needed = {name: set() for name in locations}
  for option_name in set(FLAG_OPTIONS.values()) - {None}:
    options = all_progression_options()
    options[option_name] = False
    progress_locations = set(Logic.filter_locations_for_progression_static(
      locations, item_locations, options, filter_sunken_treasure=True,
    ))
    for location_name in locations:
      if location_name not in progress_locations:
        offline_options_needed[location_name].add(option_name)
  
  mismatches = {}
  for location_name in locations:
    apworld_options_needed = {FLAG_OPTIONS[flag] for flag in location_flags[location_name]} - {None}
    if offline_options_needed[location_name] != apworld_options_needed:
      mismatches[location_name] = (sorted(offline_options_needed[location_name]), sorted(apworld_options_needed))
  assert mismatches == {}

@pytest.mark.parametrize("fixture", APTWW_FIXTURES)
def test_progress_locations_match_aptww_fixture(fixture):
  options = Options()
  plando = read_ap_plando_file(os.path.join(FIXTURES_DIR, "aptww", fixture + ".aptww"), options)
  args = make_argparser().parse_args(args=["--dry"])
  rando = WWRandomizer(plando.seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, plando, cmd_line_args=args)
  # Apply the fixture's chart mapping and required bosses, then compute the progress locations the offline way.
  for randomizer in [rando.charts, rando.boss_reqs]:
    if randomizer.is_enabled():
      randomizer.randomize()
  rando.logic.update_chart_macros()
  
  assert set(rando.compute_progress_locations()) == set(plando.locations)

def fixture_options(fixture: str) -> Options:
  options = Options()
  read_ap_plando_file(os.path.join(FIXTURES_DIR, "aptww", fixture + ".aptww"), options)
  for option_name, value in FIXTURE_LOCAL_OPTIONS.get(fixture, {}).items():
    options[option_name] = value
  return options

def check_offline_seed(options: Options, seed: str):
  args = make_argparser().parse_args(args=["--dry", "--nologs"])
  rando = WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)
  # Raises if the seed isn't beatable (item placement checks Ganondorf is reachable, and calculating the spheres fails
  # if not every progress item can be collected).
  rando.randomize_all()
  spheres = rando.items.calculate_playthrough_progression_spheres()
  assert any(sphere.get("Ganon's Tower - Rooftop") == "Defeat Ganondorf" for sphere in spheres)
  # Everything the playthrough needs is in a progress location.
  progress_locations = set(rando.compute_progress_locations())
  for sphere in spheres:
    for location_name, item_name in sphere.items():
      if not item_name.startswith("Defeat "):
        assert location_name in progress_locations

@pytest.mark.parametrize("seed_index", range(3))
@pytest.mark.parametrize("fixture", APTWW_FIXTURES)
def test_offline_seeds_with_fixture_options_are_beatable(fixture, seed_index):
  check_offline_seed(fixture_options(fixture), f"parity_{fixture}_{seed_index}")

@pytest.mark.slow
@pytest.mark.parametrize("seed_index", range(3, 43))
@pytest.mark.parametrize("fixture", APTWW_FIXTURES)
def test_offline_seeds_with_fixture_options_are_beatable_many(fixture, seed_index):
  check_offline_seed(fixture_options(fixture), f"parity_{fixture}_{seed_index}")
