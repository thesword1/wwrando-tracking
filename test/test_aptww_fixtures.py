import zipfile
from base64 import b64decode
from pathlib import Path

import pytest
from ruamel.yaml import YAML

yaml = YAML(typ="safe")

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aptww"
FIXTURE_PATHS = sorted(FIXTURES_DIR.glob("*.aptww"))

EXPECTED_KEYS = ["Version", "Seed", "Slot", "Name", "Options", "Required Bosses", "Locations", "Entrances", "Charts"]

# Options each fixture's YAML sets to a non-default value, as they appear in the plando's integer-valued Options.
EXPECTED_OPTIONS = {
  "defaults": {
    "randomize_smallkeys": 2,
    "randomize_bigkeys": 2,
    "randomize_mapcompass": 2,
    "sword_mode": 0,
    "required_bosses": 0,
    "randomize_charts": 0,
  },
  "progression_all": {
    "progression_tingle_chests": 1,
    "progression_dungeon_secrets": 1,
    "progression_combat_secret_caves": 1,
    "progression_savage_labyrinth": 1,
    "progression_long_sidequests": 1,
    "progression_mail": 1,
    "progression_triforce_charts": 1,
    "progression_treasure_charts": 1,
    "progression_misc": 1,
  },
  "entrance_rando": {
    "randomize_dungeon_entrances": 1,
    "randomize_secret_cave_entrances": 1,
    "randomize_miniboss_entrances": 1,
    "randomize_boss_entrances": 1,
    "randomize_secret_cave_inner_entrances": 1,
    "randomize_fairy_fountain_entrances": 1,
    "mix_entrances": 1,
    "randomize_starting_island": 1,
  },
  "charts_required_bosses": {
    "progression_treasure_charts": 1,
    "randomize_charts": 1,
    "required_bosses": 1,
    "num_required_bosses": 3,
  },
  "keys_swords_tuner": {
    "randomize_smallkeys": 5,
    "randomize_bigkeys": 4,
    "randomize_mapcompass": 3,
    "sword_mode": 2,
    "logic_obscurity": 1,
    "logic_precision": 1,
  },
}

def load_plando(path: Path) -> dict:
  with zipfile.ZipFile(path) as z:
    # Fixtures must only hold the AP metadata and plando YAML, never game data.
    assert sorted(z.namelist()) == ["archipelago.json", "plando"]
    return yaml.load(b64decode(z.read("plando")))

def test_all_fixtures_present():
  assert sorted(p.stem for p in FIXTURE_PATHS) == sorted(EXPECTED_OPTIONS)

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_fixture_structure(path: Path):
  plando = load_plando(path)

  assert list(plando) == EXPECTED_KEYS
  assert len(plando["Version"]) == 3
  assert plando["Slot"] == 1
  assert plando["Name"] == "Player"
  assert isinstance(plando["Required Bosses"], list)
  assert plando["Locations"]
  for location_name, item_info in plando["Locations"].items():
    assert {"name", "game", "classification"} <= set(item_info), location_name
  assert isinstance(plando["Entrances"], dict)

  charts = plando["Charts"]
  assert len(charts) == 49
  assert sorted(charts) == list(range(1, 49 + 1))

  for option_name, value in EXPECTED_OPTIONS[path.stem].items():
    assert plando["Options"][option_name] == value, option_name

def test_fixture_specific_contents():
  plandos = {p.stem: load_plando(p) for p in FIXTURE_PATHS}

  assert plandos["defaults"]["Charts"] == list(range(1, 49 + 1))
  assert plandos["charts_required_bosses"]["Charts"] != list(range(1, 49 + 1))

  required_bosses = plandos["charts_required_bosses"]["Required Bosses"]
  assert len(required_bosses) == 3
  assert any(loc.startswith("Dragon Roost Cavern - ") for loc in required_bosses)
  assert not any(loc.startswith("Wind Temple - ") for loc in required_bosses)

  # Every zone entrance maps to its vanilla exit unless entrances are randomized.
  defaults_entrances = plandos["defaults"]["Entrances"]
  er_entrances = plandos["entrance_rando"]["Entrances"]
  assert set(er_entrances) == set(defaults_entrances)
  assert er_entrances != defaults_entrances

  assert len(plandos["progression_all"]["Locations"]) > len(plandos["defaults"]["Locations"])
