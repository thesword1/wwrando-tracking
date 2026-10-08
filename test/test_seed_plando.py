import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer, Plando
from aptww import read_ap_plando_file
from options.wwrando_options import Options
from tracker.locations import build_tracker_location_set
from test_helpers import *

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "aptww")
ENTRANCE_OPTION_NAMES = [
  "randomize_dungeon_entrances",
  "randomize_secret_cave_entrances",
  "randomize_miniboss_entrances",
  "randomize_boss_entrances",
  "randomize_secret_cave_inner_entrances",
  "randomize_fairy_fountain_entrances",
]

def dry_rando(options, seed="plando", plando=None) -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, plando, cmd_line_args=args)

def offline_options() -> Options:
  options = Options()
  options.progression_triforce_charts = True
  options.progression_treasure_charts = True
  options.randomize_charts = True
  options.required_bosses = True
  options.num_required_bosses = 3
  options.randomize_dungeon_entrances = True
  options.randomize_secret_cave_entrances = True
  return options

def test_offline_seed_plando():
  rando = dry_rando(offline_options(), "offlineplando")
  rando.randomize_all()
  plando = rando.get_seed_plando()
  assert isinstance(plando, Plando)
  assert plando.seed == "offlineplando"
  
  # Locations are the seed's progress locations, and every progress item placed in the playthrough is in one of them.
  assert set(plando.locations) == set(rando.compute_progress_locations())
  spheres = rando.items.calculate_playthrough_progression_spheres()
  for sphere in spheres:
    for location_name, item_name in sphere.items():
      if not item_name.startswith("Defeat "):
        assert location_name in plando.locations
        assert plando.locations[location_name]["name"] == item_name
        assert plando.locations[location_name]["classification"] == "progression"
  # Nothing in the dungeons of bosses that aren't required.
  assert not set(plando.locations) & set(rando.boss_reqs.banned_locations)
  
  assert sorted(plando.required_bosses) == sorted(rando.boss_reqs.required_boss_item_locations)
  assert len(plando.required_bosses) == 3
  assert len(plando.entrances) == len(rando.entrances.done_entrances_to_exits)
  assert sorted(plando.charts) == list(range(1, 49+1))

def test_offline_plando_round_trips_through_archipelago_mode():
  # Feeding an offline seed's plando to Archipelago mode reproduces its charts, entrances and required bosses.
  options = offline_options()
  rando = dry_rando(options, "roundtrip")
  rando.randomize_all()
  plando = rando.get_seed_plando()
  
  ap_rando = dry_rando(offline_options(), plando.seed, plando=plando)
  for randomizer in [ap_rando.charts, ap_rando.boss_reqs, ap_rando.entrances]:
    randomizer.randomize()
  assert ap_rando.charts.island_number_to_chart_name == rando.charts.island_number_to_chart_name
  assert ap_rando.boss_reqs.required_bosses == rando.boss_reqs.required_bosses
  assert ap_rando.entrances.done_entrances_to_exits == rando.entrances.done_entrances_to_exits

@pytest.mark.parametrize("fixture", ["defaults", "charts_required_bosses", "entrance_rando"])
def test_archipelago_seed_plando_is_the_aptww_plando(fixture):
  options = Options()
  plando = read_ap_plando_file(os.path.join(FIXTURES_DIR, fixture + ".aptww"), options)
  rando = dry_rando(options, plando.seed, plando=plando)
  rando.randomize_all()
  assert rando.get_seed_plando() is plando

def test_tracker_can_use_offline_seed_plando():
  # The tracker builds its location table the same way from an offline seed as from an .aptww.
  options = offline_options()
  rando = dry_rando(options, "tracker")
  rando.randomize_all()
  plando = rando.get_seed_plando()
  location_set = build_tracker_location_set(
    plando.locations,
    plando.charts,
    {name: options[name] for name in ENTRANCE_OPTION_NAMES},
    plando.required_bosses,
  )
  assert len(location_set.locations) > 0
