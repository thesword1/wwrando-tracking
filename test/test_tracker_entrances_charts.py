import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from randomizers.entrances import ZoneEntrance, ZoneExit
from tracker.charts import (
  CHART_NAME_TO_ITEM_ID, GET_MAP_ADDR, build_tracker_chart_table, chart_mapping_from_island_chart_names,
  get_chart_table_bit,
)
from tracker.entrances import ENTRANCES, EXITS, StageTrigger, build_tracker_entrance_set, entrance_pairings_from_randomizer
from tracker.location_data import LOCATION_DATA
from tracker.locations import (
  ISLAND_NUMBER_TO_NAME, STATIC_LOCATIONS, VANILLA_ISLAND_NUMBER_TO_CHART_NAME, GroupKind,
  build_tracker_location_set,
)
from test_aptww_fixtures import FIXTURES_DIR, load_plando

# The website tracker is only a reference, so this comparison is skipped when it isn't checked out
# next to this repository (or at APTRACKER_DATA_PATH).
APTRACKER_DATA_PATH = Path(os.environ.get(
  "APTRACKER_DATA_PATH", REPO_ROOT.parent / "WWRando-APTracker-main" / "src" / "data"
))


def test_every_entrance_and_exit_is_covered():
  assert set(ENTRANCES) == set(ZoneEntrance.all)
  assert set(EXITS) == set(ZoneExit.all)
  assert len(ENTRANCES) == len(EXITS) == 44

def test_display_names():
  for table in [ENTRANCES, EXITS]:
    display_names = [entry.display_name for entry in table.values()]
    assert len(display_names) == len(set(display_names))
    for display_name in display_names:
      assert 0 < len(display_name) <= 28 and display_name.isascii(), display_name

def test_entrance_positions():
  for entrance in ENTRANCES.values():
    assert (entrance.island_number is None) != (entrance.nested_in is None), entrance.name
  assert ENTRANCES["Secret Cave Entrance on Outset Island"].island_number == 44
  assert ENTRANCES["Boss Entrance in Forsaken Fortress"].island_number == 1
  assert ENTRANCES["Miniboss Entrance in Hyrule Castle"].island_number == 26
  assert ENTRANCES["Boss Entrance in Wind Temple"].nested_in == "Wind Temple"
  assert ENTRANCES["Inner Entrance in Ice Ring Isle Secret Cave"].nested_in == "Ice Ring Isle Secret Cave"

def test_exit_groups():
  def group_of(exit_name):
    group = EXITS[exit_name].group
    return group.kind, group.name
  assert group_of("Dragon Roost Cavern") == (GroupKind.DUNGEON, "Dragon Roost Cavern")
  assert group_of("Gohma Boss Arena") == (GroupKind.DUNGEON, "Dragon Roost Cavern")
  assert group_of("Helmaroc King Boss Arena") == (GroupKind.DUNGEON, "Forsaken Fortress")
  assert group_of("Earth Temple Miniboss Arena") == (GroupKind.DUNGEON, "Earth Temple")
  assert group_of("Master Sword Chamber") == (GroupKind.ZONE, "Hyrule")
  assert group_of("Savage Labyrinth") == (GroupKind.CAVE, "Savage Labyrinth")
  assert group_of("Cliff Plateau Isles Inner Cave") == (GroupKind.CAVE, "Cliff Plateau Isles Inner Cave")

  # Locations behind an exit are listed in that exit's group when its entrances are randomized.
  all_randomized = {name: 1 for name in {e.option_name for e in ENTRANCES.values()}}
  for loc in build_tracker_location_set(STATIC_LOCATIONS, entrance_options=all_randomized).locations:
    if loc.zone_exit is not None:
      assert loc.group == EXITS[loc.zone_exit].group, loc.name

def test_stage_triggers():
  triggers = {}
  for tracker_exit in EXITS.values():
    for trigger in tracker_exit.triggers:
      assert trigger not in triggers, trigger
      triggers[trigger] = tracker_exit.name
  assert triggers[StageTrigger("M_NewD2")] == "Dragon Roost Cavern"
  assert triggers[StageTrigger("TF_04")] == "Cabana Labyrinth"
  assert triggers[StageTrigger("Cave11")] == "Savage Labyrinth"
  # TWWClient.py's CliPlaH special case.
  assert EXITS["Cliff Plateau Isles Inner Cave"].triggers == (StageTrigger("sea", 0x2A, 1),)
  # The sea stage is never a trigger on its own.
  assert StageTrigger("sea") not in triggers

@pytest.mark.skipif(not (APTRACKER_DATA_PATH / "stage-to-exit-mapping.json").is_file(), reason="WWRando-APTracker not found")
def test_stage_triggers_match_website_tracker():
  website = json.loads((APTRACKER_DATA_PATH / "stage-to-exit-mapping.json").read_text())
  ours = {}
  for tracker_exit in EXITS.values():
    for trigger in tracker_exit.triggers:
      stage_name = "CliPlaH" if trigger.room_num is not None else trigger.stage_name
      ours[stage_name] = tracker_exit.name
  # Deliberate differences: Abesso is where the Private Oasis entrance is, not its exit, and the
  # website has no entry for the Cabana Labyrinth's own stage.
  assert website.pop("Abesso") == "Cabana Labyrinth"
  assert ours.pop("TF_04") == "Cabana Labyrinth"
  assert ours == website

  nested = json.loads((APTRACKER_DATA_PATH / "nested-entrances.json").read_text())
  # Forsaken Fortress itself isn't randomizable, so the randomizer treats its boss door as an
  # entrance on the Forsaken Fortress Sector island.
  assert nested.pop("Forsaken Fortress") == ["Helmaroc King Boss Arena"]
  assert ENTRANCES["Boss Entrance in Forsaken Fortress"].island_number == 1
  for parent_exit, child_exits in nested.items():
    for child_exit in child_exits:
      child_entrance = next(e for e in ENTRANCES.values() if e.vanilla_exit == child_exit)
      assert child_entrance.nested_in == parent_exit

def test_entrance_set_without_entrance_rando():
  plando = load_plando(FIXTURES_DIR / "defaults.aptww")
  assert build_tracker_entrance_set(plando["Entrances"], plando["Options"]).entrances == []

def test_entrance_set_from_fixture():
  plando = load_plando(FIXTURES_DIR / "entrance_rando.aptww")
  entrance_set = build_tracker_entrance_set(plando["Entrances"], plando["Options"])
  assert len(entrance_set.entrances) == 44
  assert [e.index for e in entrance_set.entrances] == list(range(44))
  for seed_entrance in entrance_set.entrances:
    assert plando["Entrances"][seed_entrance.entrance.name] == seed_entrance.exit.name

  triggers = dict(entrance_set.stage_triggers())
  index_by_name = {e.entrance.name: e.index for e in entrance_set.entrances}
  # In this seed, the Secret Cave Entrance on Fire Mountain leads into Savage Labyrinth.
  assert triggers[StageTrigger("Cave09")] == index_by_name["Secret Cave Entrance on Fire Mountain"]
  assert triggers[StageTrigger("sea", 0x2A, 1)] == index_by_name["Secret Cave Entrance on Overlook Island"]

def test_entrance_set_only_tracks_randomized_categories():
  plando = load_plando(FIXTURES_DIR / "entrance_rando.aptww")
  entrance_set = build_tracker_entrance_set(plando["Entrances"], {"randomize_boss_entrances": 1})
  assert {e.entrance.option_name for e in entrance_set.entrances} == {"randomize_boss_entrances"}
  assert len(entrance_set.entrances) == 6

def test_entrance_pairings_from_randomizer():
  fake_randomizer = SimpleNamespace(done_entrances_to_exits={
    ZoneEntrance.all["Dungeon Entrance on Gale Isle"]: ZoneExit.all["Savage Labyrinth"],
  })
  assert entrance_pairings_from_randomizer(fake_randomizer) == {"Dungeon Entrance on Gale Isle": "Savage Labyrinth"}


def test_chart_numbers_match_salvage_bits():
  # Item IDs (data/item_names.txt) and Archipelago's salvage bits (Locations.py) number charts
  # independently. Check that they agree.
  assert len(CHART_NAME_TO_ITEM_ID) == 49
  for chart in build_tracker_chart_table(None):
    salvage_bit = LOCATION_DATA[f"{chart.destination_island_name} - Sunken Treasure"].bit
    assert chart.chart_number == ((salvage_bit + 32) % 64) + 1, chart.name

def test_chart_table_bits():
  assert get_chart_table_bit(GET_MAP_ADDR, 1) == (GET_MAP_ADDR + 3, 0x01)
  assert get_chart_table_bit(GET_MAP_ADDR, 9) == (GET_MAP_ADDR + 2, 0x01)
  assert get_chart_table_bit(GET_MAP_ADDR, 33) == (GET_MAP_ADDR + 7, 0x01)
  assert get_chart_table_bit(GET_MAP_ADDR, 64) == (GET_MAP_ADDR + 4, 0x80)
  # Treasure Chart 25 is item 0xD6, chart number 0x29.
  chart = build_tracker_chart_table(None)[0]
  assert (chart.name, chart.item_id, chart.chart_number) == ("Treasure Chart 25", 0xD6, 0x29)

def test_chart_table_from_fixture():
  plando = load_plando(FIXTURES_DIR / "charts_required_bosses.aptww")
  charts = build_tracker_chart_table(plando["Charts"])
  assert [c.destination_island_number for c in charts] == list(range(1, 49+1))
  for chart in charts:
    assert plando["Charts"][chart.vanilla_island_number - 1] == chart.destination_island_number
    assert chart.name == VANILLA_ISLAND_NUMBER_TO_CHART_NAME[chart.vanilla_island_number]

  # The chart's salvaged bit is the bit that marks the destination's Sunken Treasure checked.
  location_set = build_tracker_location_set(plando["Locations"], plando["Charts"])
  charts_by_destination = {c.destination_island_name: c for c in charts}
  for loc in location_set.locations:
    if loc.chart_name is not None:
      chart = charts_by_destination[loc.group.name]
      assert chart.name == loc.chart_name
      assert (chart.salvaged_address, chart.salvaged_mask) == (loc.check.address, loc.check.mask)

def test_chart_mapping_from_chart_randomizer_form():
  # ChartRandomizer._randomize applies a plando mapping like this.
  rng = random.Random(1)
  chart_mapping = list(range(1, 49+1))
  rng.shuffle(chart_mapping)
  island_number_to_chart_name = {}
  for i in range(1, 49+1):
    island_number_to_chart_name[chart_mapping[i - 1]] = VANILLA_ISLAND_NUMBER_TO_CHART_NAME[i]
  assert chart_mapping_from_island_chart_names(island_number_to_chart_name) == chart_mapping
  assert ISLAND_NUMBER_TO_NAME[1] == "Forsaken Fortress Sector"
