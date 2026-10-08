import os
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer, InvalidOptionsError
from randomizers.boss_reqs import RequiredBossesRandomizer
from options.wwrando_options import Options, REQUIRED_BOSSES_DUNGEONS
from test_helpers import *

def dry_rando(options, seed="reqbosses") -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

def required_bosses_options(num, included=(), excluded=()) -> Options:
  options = Options()
  # Leave enough progress locations when only a few dungeons are required.
  enable_all_progression_location_options(options)
  options.required_bosses = True
  options.num_required_bosses = num
  options.included_dungeons = list(included)
  options.excluded_dungeons = list(excluded)
  return options

@pytest.mark.parametrize("num, included, excluded", [
  (4, ["Earth Temple"], ["Wind Temple", "Forsaken Fortress"]),
  (2, ["Dragon Roost Cavern", "Tower of the Gods"], []),
  (3, [], ["Dragon Roost Cavern", "Forbidden Woods", "Tower of the Gods"]),
  (1, [], ["Forsaken Fortress"]),
])
def test_included_and_excluded_dungeons_over_200_seeds(num, included, excluded):
  rando = dry_rando(required_bosses_options(num, included, excluded))
  seen_required = set()
  for i in range(200):
    # Only rerun the required bosses selection for each seed, the item placement isn't needed here.
    rando.integer_seed = i
    rando.boss_reqs = RequiredBossesRandomizer(rando)
    rando.boss_reqs.randomize()
    required = set(rando.boss_reqs.required_dungeons)
    assert len(required) == num
    assert set(included) <= required
    assert not (set(excluded) & required)
    assert set(rando.boss_reqs.banned_dungeons) == set(REQUIRED_BOSSES_DUNGEONS) - required
    seen_required |= required
  # Every dungeon that isn't excluded gets picked sometimes (unless the included ones are all the required ones).
  if len(included) < num:
    assert seen_required == set(REQUIRED_BOSSES_DUNGEONS) - set(excluded)
  else:
    assert seen_required == set(included)

@pytest.mark.parametrize("seed", ["reqboss1", "reqboss2", "reqboss3"])
def test_required_bosses_filters_full_seed(seed):
  options = required_bosses_options(3, ["Wind Temple"], ["Dragon Roost Cavern", "Forbidden Woods"])
  rando = dry_rando(options, seed)
  rando.randomize_all()
  assert "Wind Temple" in rando.boss_reqs.required_dungeons
  assert not {"Dragon Roost Cavern", "Forbidden Woods"} & set(rando.boss_reqs.required_dungeons)
  # Nothing in the excluded dungeons is needed to beat the seed.
  for location_name in rando.logic.item_locations:
    if rando.logic.is_dungeon_location(location_name):
      zone_name, _ = rando.logic.split_location_name_by_zone(location_name)
      if zone_name in ["Dragon Roost Cavern", "Forbidden Woods"]:
        assert location_name in rando.boss_reqs.banned_locations
  spheres = rando.items.calculate_playthrough_progression_spheres()
  for sphere in spheres:
    for location_name in sphere:
      assert location_name not in rando.boss_reqs.banned_locations

@pytest.mark.parametrize("num, included, excluded, message", [
  (2, ["Earth Temple"], ["Earth Temple"], "conflict"),
  (1, ["Earth Temple", "Wind Temple"], [], "more dungeons are always required"),
  (4, [], ["Earth Temple", "Wind Temple", "Forbidden Woods"], "not enough left"),
])
def test_invalid_required_bosses_filters(num, included, excluded, message):
  with pytest.raises(InvalidOptionsError, match=message):
    dry_rando(required_bosses_options(num, included, excluded))

def test_required_bosses_needs_progression_dungeons():
  options = required_bosses_options(4)
  options.progression_dungeons = False
  with pytest.raises(InvalidOptionsError, match="progression dungeons"):
    dry_rando(options)

def test_permalink_with_dungeon_lists():
  options = required_bosses_options(3, ["Earth Temple"], ["Forsaken Fortress", "Wind Temple"])
  permalink = WWRandomizer.encode_permalink("bosses", options)
  seed, decoded = WWRandomizer.decode_permalink(permalink)
  assert seed == "bosses"
  assert decoded.included_dungeons == ["Earth Temple"]
  assert decoded.excluded_dungeons == ["Forsaken Fortress", "Wind Temple"]
  assert decoded == options
