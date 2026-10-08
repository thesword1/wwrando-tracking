import base64
import io
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from wwrando import make_argparser # Must be imported first, it adds gclib to the path.
from aptww import APTWWFileError, load_and_validate_ap_plando_file, read_ap_plando_file
from options.wwrando_options import Options, SwordMode, KeyLunacyMode, EntranceMixMode, TrickDifficulty

RANDO_ROOT = Path(__file__).resolve().parent.parent

def make_plando_dict(**overrides) -> dict:
  plando = {
    "Version": [3, 0, 0],
    "Seed": "12345678901234567890",
    "Slot": 2,
    "Name": "Player2",
    "Options": {
      "progression_dungeons": 1,
      "progression_mail": 0,
      "sword_mode": 1,
      "randomize_smallkeys": 5,
      "mix_entrances": 1,
      "logic_obscurity": 3,
      "num_required_bosses": 2,
    },
    "Required Bosses": ["Dragon Roost Cavern - Gohma Heart Container"],
    "Locations": {
      "Outset Island - Underneath Link's House": {
        "name": "Telescope", "game": "The Wind Waker", "player": 2, "classification": "progression",
      },
      "Windfall Island - 5 Rupee Auction": {
        "name": "Bob’s Sword", "game": "Other Game", "player": 1, "classification": "useful",
      },
    },
    "Entrances": {"Dungeon Entrance on Dragon Roost Island": "Dragon Roost Cavern"},
    "Charts": list(range(1, 50)),
  }
  plando.update(overrides)
  return plando

def yaml_bytes(data) -> bytes:
  out = io.StringIO()
  YAML(typ="safe").dump(data, out)
  return out.getvalue().encode("utf-8")

def write_aptww(path: Path, plando_dict: dict) -> Path:
  with zipfile.ZipFile(path, "w") as z:
    z.writestr("plando", base64.b64encode(yaml_bytes(plando_dict)))
  return path

def test_read_valid_aptww(tmp_path):
  aptww = write_aptww(tmp_path / "AP_test_P2_Player2.aptww", make_plando_dict())
  options = Options()
  plando = read_ap_plando_file(str(aptww), options)

  assert plando.seed == "AP_12345678901234567890_P2"
  assert plando.slot == 2
  assert plando.name == "Player2"
  assert plando.required_bosses == ["Dragon Roost Cavern - Gohma Heart Container"]
  assert plando.entrances == {"Dungeon Entrance on Dragon Roost Island": "Dragon Roost Cavern"}
  assert plando.charts == list(range(1, 50))
  assert plando.locations["Outset Island - Underneath Link's House"]["name"] == "Telescope"
  # Characters the game's font can't encode are replaced for items from other games.
  assert plando.locations["Windfall Island - 5 Rupee Auction"]["name"] == "Bob\x92s Sword"

def test_options_are_mapped(tmp_path):
  aptww = write_aptww(tmp_path / "test.aptww", make_plando_dict())
  options = Options()
  read_ap_plando_file(str(aptww), options)

  assert options.progression_dungeons is True
  assert options.progression_mail is False
  assert options.sword_mode == SwordMode.NO_STARTING_SWORD
  assert options.randomize_smallkeys == KeyLunacyMode.KEYLUNACY
  assert options.mix_entrances == EntranceMixMode.MIX_DUNGEONS
  assert options.logic_obscurity == TrickDifficulty.VERY_HARD
  assert options.num_required_bosses == 2
  # Options not in the file keep their values.
  assert options.randomize_bigkeys == KeyLunacyMode.DUNGEON

def test_plain_yaml_fallback(tmp_path):
  path = tmp_path / "test.aptww"
  path.write_bytes(yaml_bytes(make_plando_dict()))
  plando_dict = load_and_validate_ap_plando_file(str(path))
  assert plando_dict["Slot"] == 2

def test_corrupt_file(tmp_path):
  path = tmp_path / "test.aptww"
  path.write_bytes(b"\x00\x01garbage: [")
  with pytest.raises(APTWWFileError, match="error trying to read"):
    load_and_validate_ap_plando_file(str(path))

def test_unreadable_file(tmp_path):
  with pytest.raises(APTWWFileError, match="could not be opened"):
    load_and_validate_ap_plando_file(str(tmp_path / "missing.aptww"))

@pytest.mark.parametrize("overrides, expected", [
  ({"Version": [2, 5, 1]}, "ap_2.3.0"),
  ({"Version": [2, 6, 0]}, "ap_2.4.0"),
])
def test_old_versions_rejected(tmp_path, overrides, expected):
  aptww = write_aptww(tmp_path / "test.aptww", make_plando_dict(**overrides))
  with pytest.raises(APTWWFileError, match=expected):
    load_and_validate_ap_plando_file(str(aptww))

def test_pre_versioned_file_rejected(tmp_path):
  plando_dict = make_plando_dict()
  del plando_dict["Version"]
  aptww = write_aptww(tmp_path / "test.aptww", plando_dict)
  with pytest.raises(APTWWFileError, match="v2.4.0 of the APWorld") as excinfo:
    load_and_validate_ap_plando_file(str(aptww))

  plain = excinfo.value.plain_text()
  assert "<" not in plain
  assert "https://github.com/tanjo3/wwrando/releases/tag/ap_2.2.0" in plain

def test_argparser_paths():
  args = make_argparser().parse_args(["--aptww", "a.aptww", "--clean-iso", "b.iso", "--output-folder", "out"])
  assert args.aptww == "a.aptww"
  assert args.clean_iso == "b.iso"
  assert args.output_folder == "out"

def run_cli(*cli_args):
  return subprocess.run(
    [sys.executable, str(RANDO_ROOT / "wwrando.py"), *cli_args],
    capture_output=True, text=True, cwd=RANDO_ROOT, timeout=120,
  )

def test_cli_requires_clean_iso(tmp_path):
  result = run_cli("--noui", "--clean-iso", str(tmp_path / "missing.iso"), "--output-folder", str(tmp_path))
  assert result.returncode != 0
  assert "--clean-iso" in result.stderr

def test_cli_offline_dry_randomize(tmp_path):
  result = run_cli("--noui", "--dry", "--seed", "clitest", "--output-folder", str(tmp_path))
  assert result.returncode == 0, result.stderr
  assert "Done (dry)" in result.stdout
  assert (tmp_path / "WW Random clitest - Spoiler Log.txt").is_file()
  assert (tmp_path / "WW Random clitest - Non-Spoiler Log.txt").is_file()

def test_cli_reports_bad_aptww(tmp_path):
  aptww = write_aptww(tmp_path / "test.aptww", make_plando_dict(Version=[2, 5, 0]))
  result = run_cli("--dry", "--aptww", str(aptww), "--output-folder", str(tmp_path))
  assert result.returncode != 0
  assert "v2.5.0 of the APWorld" in result.stderr
  assert "<br>" not in result.stderr

FIXTURE_PATHS = sorted((RANDO_ROOT / "test" / "fixtures" / "aptww").glob("*.aptww"))

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_dry_randomize_fixture(path, tmp_path):
  from randomizer import WWRandomizer
  options = Options()
  plando = read_ap_plando_file(str(path), options)
  args = make_argparser().parse_args(["--dry", "--aptww", str(path)])
  rando = WWRandomizer(plando.seed, None, str(tmp_path), options, plando, cmd_line_args=args)
  rando.randomize_all()

def test_cli_dry_randomize_fixture(tmp_path):
  aptww = RANDO_ROOT / "test" / "fixtures" / "aptww" / "defaults.aptww"
  result = run_cli("--dry", "--aptww", str(aptww), "--output-folder", str(tmp_path))
  assert result.returncode == 0, result.stderr
  assert "Done (dry)" in result.stdout
