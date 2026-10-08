# Tests of the stage-to-group table (tracker/stages.py) that the dungeon map and Quest Status pages use.

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from tracker.locations import ENTRANCE_CATEGORIES, STATIC_LOCATIONS, get_group, get_randomized_exits
from tracker.stages import LOCATION_STAGE_NAMES, STAGE_NAMES, ZONE_STAGE_NAMES, build_stage_groups

NO_ENTRANCES = None
ALL_ENTRANCES = {option_name: True for option_name in ENTRANCE_CATEGORIES}


@pytest.mark.parametrize("entrance_options", [NO_ENTRANCES, ALL_ENTRANCES], ids=["vanilla", "all_randomized"])
def test_stage_groups_match_locations(entrance_options):
  randomized_exits = get_randomized_exits(entrance_options)
  stage_groups = build_stage_groups(randomized_exits)
  assert set(stage_groups) <= STAGE_NAMES
  assert all(len(stage_name) <= 8 for stage_name in stage_groups)
  assert "sea" not in stage_groups
  # The submarines are on several islands.
  assert "Abship" not in stage_groups
  # Every location in a mapped stage is in that stage's group.
  for location_name, stage_names in LOCATION_STAGE_NAMES.items():
    for stage_name in stage_names:
      if stage_name in stage_groups:
        assert stage_groups[stage_name] == get_group(location_name, randomized_exits), (stage_name, location_name)


def test_zone_stages():
  assert set().union(*ZONE_STAGE_NAMES.values()) <= STAGE_NAMES
  for entrance_options in [NO_ENTRANCES, ALL_ENTRANCES]:
    stage_groups = build_stage_groups(get_randomized_exits(entrance_options))
    # Arenas belong to their dungeon even when their entrances are randomized.
    for stage_name in ["kindan", "kinMB", "kinBOSS"]:
      assert stage_groups[stage_name].name == "Forbidden Woods"
    assert stage_groups["M_DragB"].name == "Dragon Roost Cavern"
    assert stage_groups["M2tower"].name == "Forsaken Fortress"
    assert stage_groups["kenroom"].name == "Hyrule"
    assert stage_groups["Xboss2"].name == "Ganon's Tower"


def test_cave_stages():
  vanilla = build_stage_groups(get_randomized_exits(NO_ENTRANCES))
  randomized = build_stage_groups(get_randomized_exits(ALL_ENTRANCES))
  # A cave's locations are on its island's square unless an entrance on the way is randomized.
  assert vanilla["Cave09"].name == "Outset Island"
  assert vanilla["Cave11"].name == "Outset Island"
  assert randomized["Cave09"].name == "Savage Labyrinth"
  assert randomized["Cave11"].name == "Savage Labyrinth"
  assert vanilla["ITest62"].name == "Ice Ring Isle"
  assert randomized["ITest62"].name == "Ice Ring Isle Inner Cave"
  only_inner = build_stage_groups(get_randomized_exits({"randomize_secret_cave_inner_entrances": True}))
  assert only_inner["MiniHyo"].name == "Ice Ring Isle"
  assert only_inner["ITest62"].name == "Ice Ring Isle Inner Cave"
  # Fairy fountains have no location paths, so they come from their exits.
  assert vanilla["Fairy01"].name == "Northern Fairy Island"
  assert randomized["Fairy01"].name == "Northern Fairy Fountain"
  # Interiors on an island.
  assert vanilla["Ocmera"].name == "Windfall Island"
  assert vanilla["LinkUG"].name == "Outset Island"


def test_location_stage_names():
  assert LOCATION_STAGE_NAMES["Forbidden Woods - Kalle Demos Heart Container"] == {"kinBOSS"}
  assert LOCATION_STAGE_NAMES["Outset Island - Underneath Link's House"] == {"LinkUG"}
  assert set(LOCATION_STAGE_NAMES) == set(STATIC_LOCATIONS)
