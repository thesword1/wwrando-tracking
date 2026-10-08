
from wwrando import make_argparser
from wwr_ui.randomizer_window import WWRandomizerWindow
from randomizer import WWRandomizer
from options.wwrando_options import Options

def make_rando_window() -> WWRandomizerWindow:
  args = make_argparser().parse_args(args=[])
  window = WWRandomizerWindow(cmd_line_args=args)
  return window

def test_gui_launches(qtbot):
  window = make_rando_window()
  window.save_settings()

def test_cosmetic_tab(qtbot):
  window = make_rando_window()
  cosmetic_tab = window.ui.tab_player_customization
  cosmetic_tab.ui.custom_player_model.setCurrentIndex(cosmetic_tab.ui.custom_player_model.findText("Link"))
  cosmetic_tab.ui.randomize_all_custom_colors_separately.click()
  cosmetic_tab.ui.randomize_all_custom_colors_together.click()
  cosmetic_tab.ui.custom_color_preset.setCurrentIndex(cosmetic_tab.ui.custom_color_preset.findText("Dark Link"))

def test_offline_and_archipelago_modes(qtbot):
  window = make_rando_window()
  window.ui.plando_file.setText("")
  window.ui.seed.setText("guitest")
  window.update_settings()
  assert window.ui.progression_dungeons.isEnabled()
  assert window.ui.progression_locations_groupbox.isEnabled()
  
  # Offline seeds get a permalink that round-trips through the randomizer.
  permalink = window.ui.permalink.text()
  assert permalink
  seed, options = WWRandomizer.decode_permalink(permalink)
  assert seed == "guitest"
  window_options = window.get_all_options_from_widget_values()
  for option in Options.all():
    if option.permalink:
      assert options[option.name] == window_options[option.name], option.name
  
  # Selecting an .aptww file switches to Archipelago mode, which greys out the offline-only options without changing them.
  window.ui.progression_dungeons.setChecked(False)
  window.update_settings()
  window.ui.plando_file.setText("some.aptww")
  window.update_settings()
  assert not window.ui.progression_locations_groupbox.isEnabled()
  assert not window.ui.progression_dungeons.isChecked()
  assert window.ui.invert_camera_x_axis.isEnabled()
  
  window.ui.plando_file.setText("")
  window.ui.progression_dungeons.setChecked(True)
  window.update_settings()
