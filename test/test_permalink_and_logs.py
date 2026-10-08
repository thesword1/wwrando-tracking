import os
from pathlib import Path
import pytest

from wwrando import make_argparser
from randomizer import WWRandomizer
from options.wwrando_options import Options, SwordMode, KeyLunacyMode, EntranceMixMode, TrickDifficulty
from test_helpers import *

def dry_rando(options, seed, output_folder=None) -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  return WWRandomizer(seed, None, output_folder or os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)

def options_with_new_offline_options() -> Options:
  options = Options()
  enable_all_progression_location_options(options)
  options.randomize_smallkeys = KeyLunacyMode.ANY_DUNGEON
  options.randomize_bigkeys = KeyLunacyMode.VANILLA
  options.randomize_mapcompass = KeyLunacyMode.START_WITH
  options.sword_mode = SwordMode.SWORDS_OPTIONAL
  options.enable_tuner_logic = True
  options.required_bosses = True
  options.num_required_bosses = 3
  options.included_dungeons = ["Earth Temple"]
  options.excluded_dungeons = ["Dragon Roost Cavern", "Forsaken Fortress"]
  options.randomize_secret_cave_inner_entrances = True
  options.randomize_dungeon_entrances = True
  options.mix_entrances = EntranceMixMode.MIX_DUNGEONS
  options.randomize_charts = True
  options.logic_obscurity = TrickDifficulty.HARD
  options.starting_gear = ["Treasure Chart 3", "Wind Waker", "Wind's Requiem"]
  options.randomized_gear = [item for item in options.randomized_gear if item not in options.starting_gear]
  options.num_starting_triforce_shards = 2
  return options

def test_permalink_round_trip_with_new_options():
  options = options_with_new_offline_options()
  permalink = WWRandomizer.encode_permalink("permalinktest", options)
  seed, decoded = WWRandomizer.decode_permalink(permalink)
  assert seed == "permalinktest"
  for option in Options.all():
    if option.permalink:
      assert decoded[option.name] == options[option.name], option.name

@pytest.mark.parametrize("mode", list(KeyLunacyMode))
def test_permalink_round_trip_dungeon_item_modes(mode):
  options = Options(randomize_smallkeys=mode, randomize_bigkeys=mode, randomize_mapcompass=mode)
  _, decoded = WWRandomizer.decode_permalink(WWRandomizer.encode_permalink("modes", options))
  assert (decoded.randomize_smallkeys, decoded.randomize_bigkeys, decoded.randomize_mapcompass) == (mode, mode, mode)

def test_permalink_reproduces_seed():
  options = options_with_new_offline_options()
  rando = dry_rando(options, "reproduce")
  rando.randomize_all()
  
  seed, decoded = WWRandomizer.decode_permalink(rando.permalink)
  rando_from_permalink = dry_rando(decoded, seed)
  rando_from_permalink.randomize_all()
  
  assert rando_from_permalink.permalink == rando.permalink
  assert rando_from_permalink.seed_hash == rando.seed_hash
  assert rando_from_permalink.logic.done_item_locations == rando.logic.done_item_locations
  assert rando_from_permalink.entrances.entrance_connections == rando.entrances.entrance_connections
  assert rando_from_permalink.charts.island_number_to_chart_name == rando.charts.island_number_to_chart_name
  assert rando_from_permalink.boss_reqs.required_bosses == rando.boss_reqs.required_bosses

def test_local_options_dont_change_permalink_or_seed():
  # Options with permalink=False (cosmetics, controls, and later the in-game tracker) must not change the seed.
  options = Options()
  rando = dry_rando(options, "local")
  rando.randomize_all()
  
  local_options = Options()
  for option in Options.all():
    if not option.permalink and isinstance(local_options[option.name], bool):
      local_options[option.name] = not local_options[option.name]
  rando_local = dry_rando(local_options, "local")
  rando_local.randomize_all()
  
  assert rando_local.permalink == rando.permalink
  assert rando_local.logic.done_item_locations == rando.logic.done_item_locations

def test_spoiler_log_contents(tmp_path):
  options = options_with_new_offline_options()
  rando = dry_rando(options, "spoilertest", output_folder=str(tmp_path))
  rando.randomize_all()
  spoiler_log = (tmp_path / "WW Random spoilertest - Spoiler Log.txt").read_text()
  non_spoiler_log = (tmp_path / "WW Random spoilertest - Non-Spoiler Log.txt").read_text()
  
  for log in [spoiler_log, non_spoiler_log]:
    assert f"Permalink: {rando.permalink}" in log
    assert "Offline seed" in log
    assert "randomize_smallkeys: Any Dungeon" in log
    assert "enable_tuner_logic" in log
    assert "included_dungeons: ['Earth Temple']" in log
    assert "sword_mode: Swords Optional" in log
    # Offline seeds have no hints, so their options aren't listed.
    assert "fishmen_hints" not in log
  
  assert "Starting items:\n" in spoiler_log
  assert "  Treasure Chart 3\n" in spoiler_log
  assert "  DRC Dungeon Map\n" in spoiler_log # Maps and compasses in the Start With mode.
  assert "Required dungeons:" in spoiler_log
  assert "Entrances:" in spoiler_log
  assert "Charts:" in spoiler_log
  assert "Playthrough progression spheres:" in spoiler_log
  assert "All item locations:" in spoiler_log

def test_cli_permalink(tmp_path):
  import subprocess, sys
  repo_root = Path(__file__).resolve().parents[1]
  options = options_with_new_offline_options()
  permalink = WWRandomizer.encode_permalink("clipermalink", options)
  result = subprocess.run(
    [sys.executable, str(repo_root / "wwrando.py"), "--noui", "--dry", "--permalink", permalink, "--output-folder", str(tmp_path)],
    capture_output=True, text=True, cwd=repo_root, timeout=120,
  )
  assert result.returncode == 0, result.stderr
  spoiler_log = (tmp_path / "WW Random clipermalink - Spoiler Log.txt").read_text()
  assert f"Permalink: {permalink}" in spoiler_log
