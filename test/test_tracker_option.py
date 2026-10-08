import os
from pathlib import Path

from wwrando import make_argparser # Must be imported first, it adds gclib to the path.
from randomizer import WWRandomizer
from aptww import AP_MODE_LOCAL_OPTIONS, read_ap_plando_file
from options.wwrando_options import Options

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "aptww"

def make_rando(options: Options, *args: str) -> WWRandomizer:
  cmd_line_args = make_argparser().parse_args(args=["--dry", *args])
  return WWRandomizer("trackeroption", None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=cmd_line_args)

def test_tracker_option_is_on_by_default_and_local():
  option = Options.by_name()["in_game_tracker"]
  assert Options().in_game_tracker
  assert not option.permalink
  assert "in_game_tracker" in AP_MODE_LOCAL_OPTIONS

def test_tracker_option_doesnt_change_permalink():
  assert WWRandomizer.encode_permalink("x", Options(in_game_tracker=True)) == WWRandomizer.encode_permalink("x", Options(in_game_tracker=False))

def test_tracker_command_line_flags():
  parser = make_argparser()
  assert parser.parse_args(args=[]).tracker is None
  assert parser.parse_args(args=["--tracker"]).tracker is True
  assert parser.parse_args(args=["--no-tracker"]).tracker is False

  # Without a flag the option decides; the flags override it.
  assert make_rando(Options()).in_game_tracker
  assert not make_rando(Options(in_game_tracker=False)).in_game_tracker
  assert make_rando(Options(in_game_tracker=False), "--tracker").in_game_tracker
  assert not make_rando(Options(), "--no-tracker").in_game_tracker

def test_archipelago_mode_keeps_local_tracker_options():
  # Neither option is in .aptww files, so loading one keeps the local settings.
  for in_game_tracker in [False, True]:
    for enable_tuner_logic in [False, True]:
      options = Options(in_game_tracker=in_game_tracker, enable_tuner_logic=enable_tuner_logic)
      read_ap_plando_file(str(FIXTURES_DIR / "defaults.aptww"), options)
      assert options.in_game_tracker == in_game_tracker
      assert options.enable_tuner_logic == enable_tuner_logic

def test_gui_tracker_option(qtbot):
  from wwr_ui.randomizer_window import WWRandomizerWindow
  window = WWRandomizerWindow(cmd_line_args=make_argparser().parse_args(args=[]))
  window.ui.plando_file.setText("")
  window.update_settings()
  assert window.ui.in_game_tracker.isChecked()
  assert window.get_all_options_from_widget_values().in_game_tracker

  # Both stay editable for Archipelago seeds.
  window.ui.plando_file.setText("some.aptww")
  window.update_settings()
  assert window.ui.in_game_tracker.isEnabled()
  assert window.ui.enable_tuner_logic.isEnabled()
  window.ui.in_game_tracker.setChecked(False)
  window.update_settings()
  assert window.settings["in_game_tracker"] is False

  window.ui.plando_file.setText("")
  window.ui.in_game_tracker.setChecked(True)
  window.update_settings()
