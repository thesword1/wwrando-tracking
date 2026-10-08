# Widgets for the options that are only chosen in the randomizer UI for offline seeds (seeds generated without an
# Archipelago .aptww file). For Archipelago seeds these options come from the .aptww file instead, so the widgets are
# disabled while an .aptww file is selected.
#
# The widgets are built in code rather than in randomizer_window.ui. Each option widget's object name is the option's
# name (and its label's is "label_for_" + the option's name), which is how the randomizer window finds them.

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
  from wwr_ui.randomizer_window import WWRandomizerWindow

import typing
from enum import StrEnum

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
  QWidget, QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout, QCheckBox, QComboBox, QSpinBox, QLabel, QLineEdit,
  QPushButton, QListView, QAbstractItemView, QSizePolicy, QSpacerItem,
)

from options.wwrando_options import Options

OPTION_LABELS = {
  "progression_dungeons": "Dungeons",
  "progression_tingle_chests": "Tingle Chests",
  "progression_dungeon_secrets": "Dungeon Secrets",
  "progression_puzzle_secret_caves": "Puzzle Secret Caves",
  "progression_combat_secret_caves": "Combat Secret Caves",
  "progression_savage_labyrinth": "Savage Labyrinth",
  "progression_great_fairies": "Great Fairies",
  "progression_short_sidequests": "Short Sidequests",
  "progression_long_sidequests": "Long Sidequests",
  "progression_spoils_trading": "Spoils Trading",
  "progression_minigames": "Minigames",
  "progression_battlesquid": "Battlesquid Minigame",
  "progression_free_gifts": "Free Gifts",
  "progression_mail": "Mail",
  "progression_platforms_rafts": "Lookout Platforms and Rafts",
  "progression_submarines": "Submarines",
  "progression_eye_reef_chests": "Eye Reef Chests",
  "progression_big_octos_gunboats": "Big Octos and Gunboats",
  "progression_triforce_charts": "Sunken Treasure (From Triforce Charts)",
  "progression_treasure_charts": "Sunken Treasure (From Treasure Charts)",
  "progression_expensive_purchases": "Expensive Purchases",
  "progression_island_puzzles": "Island Puzzles",
  "progression_misc": "Miscellaneous",

  "sword_mode": "Sword Mode",
  "randomize_smallkeys": "Small Keys",
  "randomize_bigkeys": "Big Keys",
  "randomize_mapcompass": "Maps and Compasses",
  "num_starting_triforce_shards": "Triforce Shards to Start With",
  "chest_type_matches_contents": "Chest Type Matches Contents",
  "trap_chests": "Enable Trap Chests",

  "randomize_dungeon_entrances": "Dungeons",
  "randomize_secret_cave_entrances": "Secret Caves",
  "randomize_miniboss_entrances": "Nested Minibosses",
  "randomize_boss_entrances": "Nested Bosses",
  "randomize_secret_cave_inner_entrances": "Inner Secret Caves",
  "randomize_fairy_fountain_entrances": "Fairy Fountains",
  "mix_entrances": "Mixing",

  "randomize_enemies": "Randomize Enemy Locations",
  "randomize_charts": "Randomize Charts",
  "randomize_starting_island": "Randomize Starting Island",

  "swift_sail": "Swift Sail",
  "instant_text_boxes": "Instant Text Boxes",
  "reveal_full_sea_chart": "Reveal Full Sea Chart",
  "add_shortcut_warps_between_dungeons": "Add Inter-Dungeon Shortcuts",
  "skip_rematch_bosses": "Skip Boss Rematches",
  "remove_music": "Remove Music",

  "required_bosses": "Required Bosses Mode",
  "num_required_bosses": "Number of Required Bosses",
  "included_dungeons": "Always Required",
  "excluded_dungeons": "Never Required",

  "hero_mode": "Hero Mode",
  "logic_obscurity": "Obscure Tricks Required",
  "logic_precision": "Precise Tricks Required",
  "enable_tuner_logic": "Enable Tuner Logic",

  "do_not_generate_spoiler_log": "Do Not Generate Spoiler Log",

  "randomized_gear": "Randomized Gear",
  "starting_gear": "Starting Gear",
  "starting_hcs": "Heart Containers",
  "starting_pohs": "Heart Pieces",
  "num_extra_starting_items": "Extra Random Starting Items",
}

# (group box title, number of columns, option names) for each group on the main settings tab.
MAIN_TAB_GROUPS = [
  ("Progression Locations: Where Should Progress Items Be Placed?", 4, [
    "progression_dungeons",
    "progression_great_fairies",
    "progression_puzzle_secret_caves",
    "progression_combat_secret_caves",
    "progression_short_sidequests",
    "progression_long_sidequests",
    "progression_spoils_trading",
    "progression_minigames",
    "progression_free_gifts",
    "progression_mail",
    "progression_platforms_rafts",
    "progression_submarines",
    "progression_eye_reef_chests",
    "progression_big_octos_gunboats",
    "progression_triforce_charts",
    "progression_treasure_charts",
    "progression_expensive_purchases",
    "progression_misc",
    "progression_tingle_chests",
    "progression_battlesquid",
    "progression_savage_labyrinth",
    "progression_island_puzzles",
    "progression_dungeon_secrets",
  ]),
  ("Item Randomizer Modes", 2, [
    "sword_mode",
    "randomize_smallkeys",
    "randomize_bigkeys",
    "randomize_mapcompass",
    "num_starting_triforce_shards",
    "chest_type_matches_contents",
    "trap_chests",
  ]),
  ("Entrance Randomizer Options", 3, [
    "randomize_dungeon_entrances",
    "randomize_secret_cave_entrances",
    "randomize_miniboss_entrances",
    "randomize_boss_entrances",
    "randomize_secret_cave_inner_entrances",
    "randomize_fairy_fountain_entrances",
    "mix_entrances",
  ]),
  ("Other Randomizers", 3, [
    "randomize_charts",
    "randomize_starting_island",
    "randomize_enemies",
  ]),
  ("Gameplay Tweaks", 3, [
    "swift_sail",
    "instant_text_boxes",
    "reveal_full_sea_chart",
    "add_shortcut_warps_between_dungeons",
    "skip_rematch_bosses",
    "remove_music",
  ]),
]

ADVANCED_TAB_GROUPS = [
  ("Required Bosses", 2, [
    "required_bosses",
    "num_required_bosses",
    "included_dungeons",
    "excluded_dungeons",
  ]),
  ("Difficulty Options", 2, [
    "hero_mode",
    "logic_obscurity",
    "logic_precision",
  ]),
  ("Additional Advanced Options", 2, [
    "do_not_generate_spoiler_log",
  ]),
]

# Groups on the advanced tab that stay enabled for Archipelago seeds (see AP_MODE_LOCAL_OPTIONS in aptww.py).
ADVANCED_TAB_LOCAL_GROUPS = [
  ("Logic Options (Offline and Archipelago)", 2, [
    "enable_tuner_logic",
  ]),
]

class OptionChoicesWidget(QWidget):
  """A checkbox for each possible value of a list option that is a set of values from a fixed list."""
  
  value_changed = Signal()
  
  def __init__(self, option_name: str, choices: list[str]):
    super().__init__()
    self.choices = choices
    self.checkboxes: list[QCheckBox] = []
    layout = QGridLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    for i, choice in enumerate(choices):
      checkbox = QCheckBox(choice)
      # Give the checkboxes names that don't collide with option names, which the window looks widgets up by.
      checkbox.setObjectName(f"{option_name}_choice_{i}")
      checkbox.clicked.connect(self.value_changed)
      layout.addWidget(checkbox, i // 3, i % 3)
      self.checkboxes.append(checkbox)
  
  def get_value(self) -> list[str]:
    return [choice for choice, checkbox in zip(self.choices, self.checkboxes) if checkbox.isChecked()]
  
  def set_value(self, value: list[str]):
    for choice, checkbox in zip(self.choices, self.checkboxes):
      checkbox.setChecked(choice in value)

class OfflineOptionWidgets:
  def __init__(self, window: WWRandomizerWindow):
    self.window = window
    ui = window.ui

    # Containers holding options that are only used for offline seeds. These get disabled in Archipelago mode.
    self.offline_only_containers: list[QWidget] = []

    # The groups from randomizer_window.ui hold the settings that are also used for Archipelago seeds.
    ui.groupBox.setTitle("Convenience Tweaks (Offline and Archipelago)")
    ui.groupBox_2.setTitle("Cosmetic Randomizers (Offline and Archipelago)")
    
    # Mode indicator, seed and progression location groups on the main settings tab.
    main_layout: QVBoxLayout = ui.tab_randomizer_settings.layout()
    insert_index = 1 # Right after the paths.

    ui.mode_label = QLabel()
    ui.mode_label.setObjectName("mode_label")
    ui.mode_label.setTextFormat(Qt.TextFormat.RichText)
    ui.mode_label.setWordWrap(True)
    main_layout.insertWidget(insert_index, ui.mode_label)
    insert_index += 1

    seed_row = QWidget()
    seed_layout = QHBoxLayout(seed_row)
    seed_layout.setContentsMargins(0, 0, 0, 0)
    ui.label_for_seed = QLabel("Random Seed (optional)")
    ui.label_for_seed.setObjectName("label_for_seed")
    ui.seed = QLineEdit()
    ui.seed.setObjectName("seed")
    ui.generate_seed_button = QPushButton("New seed")
    ui.generate_seed_button.setObjectName("generate_seed_button")
    seed_layout.addWidget(ui.label_for_seed)
    seed_layout.addWidget(ui.seed)
    seed_layout.addWidget(ui.generate_seed_button)
    main_layout.insertWidget(insert_index, seed_row)
    insert_index += 1
    self.offline_only_containers.append(seed_row)

    for title, num_columns, option_names in MAIN_TAB_GROUPS:
      group_box = self.make_option_group(title, num_columns, option_names)
      main_layout.insertWidget(insert_index, group_box)
      insert_index += 1
      self.offline_only_containers.append(group_box)
      if option_names[0] == "progression_dungeons":
        group_box.setObjectName("progression_locations_groupbox")
        ui.progression_locations_groupbox = group_box

    # Starting items tab.
    ui.tab_starting_items = self.make_starting_items_tab()
    ui.tabWidget.insertTab(1, ui.tab_starting_items, "Starting Items")
    self.offline_only_containers.append(ui.tab_starting_items)

    # Advanced options tab. Dry run is also available for Archipelago seeds, so it's kept outside the offline-only groups.
    ui.tab_advanced = QWidget()
    ui.tab_advanced.setObjectName("tab_advanced")
    advanced_layout = QVBoxLayout(ui.tab_advanced)
    for title, num_columns, option_names in ADVANCED_TAB_GROUPS:
      group_box = self.make_option_group(title, num_columns, option_names)
      advanced_layout.addWidget(group_box)
      self.offline_only_containers.append(group_box)
    for title, num_columns, option_names in ADVANCED_TAB_LOCAL_GROUPS:
      group_box = self.make_option_group(title, num_columns, option_names)
      advanced_layout.addWidget(group_box)
    dry_run_group = QGroupBox("Dry Run")
    dry_run_layout = QGridLayout(dry_run_group)
    ui.dry_run = QCheckBox("Dry Run")
    ui.dry_run.setObjectName("dry_run")
    dry_run_layout.addWidget(ui.dry_run, 0, 0)
    advanced_layout.addWidget(dry_run_group)
    advanced_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
    ui.tabWidget.insertTab(2, ui.tab_advanced, "Advanced Options")

    # Permalink, shown below the tabs.
    permalink_row = QWidget()
    permalink_layout = QHBoxLayout(permalink_row)
    permalink_layout.setContentsMargins(0, 0, 0, 0)
    ui.label_for_permalink = QLabel("Permalink (copy paste to share your settings):")
    ui.label_for_permalink.setObjectName("label_for_permalink")
    ui.permalink = QLineEdit()
    ui.permalink.setObjectName("permalink")
    permalink_layout.addWidget(ui.label_for_permalink)
    permalink_layout.addWidget(ui.permalink)
    central_layout: QVBoxLayout = ui.centralwidget.layout()
    central_layout.insertWidget(1, permalink_row)
    self.offline_only_containers.append(permalink_row)

    ui.reset_settings_to_default = QPushButton("Reset All Settings to Default")
    ui.reset_settings_to_default.setObjectName("reset_settings_to_default")
    ui.horizontalLayout.insertWidget(2, ui.reset_settings_to_default)

  def make_option_group(self, title: str, num_columns: int, option_names: list[str]) -> QGroupBox:
    group_box = QGroupBox(title)
    layout = QGridLayout(group_box)

    row = 0
    column = 0
    for option_name in option_names:
      option = Options.by_name()[option_name]
      option_type = typing.get_origin(option.type) or option.type
      label_text = OPTION_LABELS[option_name]

      if issubclass(option_type, bool):
        widget = QCheckBox(label_text)
        cell = widget
      else:
        if issubclass(option_type, StrEnum):
          widget = QComboBox()
          for enum_value in option.type:
            widget.addItem(enum_value.value)
        elif issubclass(option_type, int):
          widget = QSpinBox()
        elif option.choices is not None:
          widget = OptionChoicesWidget(option_name, option.choices)
        else:
          raise Exception(f"Unsupported option type for option {option_name}: {option.type}")
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setObjectName("label_for_" + option_name)
        cell_layout.addWidget(label)
        cell_layout.addWidget(widget)
        setattr(self.window.ui, "label_for_" + option_name, label)

      widget.setObjectName(option_name)
      setattr(self.window.ui, option_name, widget)
      if option.hidden:
        # Hidden options are still accessible via settings.txt and permalinks, and are shown when enabled that way.
        widget.hide()

      layout.addWidget(cell, row, column)
      column += 1
      if column >= num_columns:
        column = 0
        row += 1

    return group_box

  def make_starting_items_tab(self) -> QWidget:
    ui = self.window.ui
    tab = QWidget()
    tab.setObjectName("tab_starting_items")
    tab_layout = QVBoxLayout(tab)

    gear_layout = QGridLayout()
    ui.label_for_randomized_gear = QLabel(OPTION_LABELS["randomized_gear"])
    ui.label_for_randomized_gear.setObjectName("label_for_randomized_gear")
    ui.label_for_starting_gear = QLabel(OPTION_LABELS["starting_gear"])
    ui.label_for_starting_gear.setObjectName("label_for_starting_gear")
    ui.randomized_gear = QListView()
    ui.randomized_gear.setObjectName("randomized_gear")
    ui.starting_gear = QListView()
    ui.starting_gear.setObjectName("starting_gear")
    for list_view in [ui.randomized_gear, ui.starting_gear]:
      list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
      list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    buttons_layout = QVBoxLayout()
    ui.add_gear = QPushButton("->")
    ui.add_gear.setObjectName("add_gear")
    ui.remove_gear = QPushButton("<-")
    ui.remove_gear.setObjectName("remove_gear")
    buttons_layout.addStretch()
    buttons_layout.addWidget(ui.add_gear)
    buttons_layout.addWidget(ui.remove_gear)
    buttons_layout.addStretch()
    gear_layout.addWidget(ui.label_for_randomized_gear, 0, 0)
    gear_layout.addWidget(ui.label_for_starting_gear, 0, 2)
    gear_layout.addWidget(ui.randomized_gear, 1, 0)
    gear_layout.addLayout(buttons_layout, 1, 1)
    gear_layout.addWidget(ui.starting_gear, 1, 2)
    tab_layout.addLayout(gear_layout)

    health_group = self.make_option_group("Starting Health and Items", 3, [
      "starting_hcs",
      "starting_pohs",
      "num_extra_starting_items",
    ])
    ui.current_health = QLabel()
    ui.current_health.setObjectName("current_health")
    health_group.layout().addWidget(ui.current_health, 1, 0, 1, 3)
    tab_layout.addWidget(health_group)

    return tab

  def update_for_mode(self, archipelago_mode: bool):
    for container in self.offline_only_containers:
      container.setEnabled(not archipelago_mode)

    if archipelago_mode:
      self.window.ui.mode_label.setText(
        "<b>Archipelago mode:</b> the selected .aptww file decides the seed, item placement and gameplay options. "
        "Clear the APTWW File field to generate an offline seed instead."
      )
    else:
      self.window.ui.mode_label.setText(
        "<b>Offline mode:</b> no .aptww file is selected, so a solo seed is generated locally with the options below."
      )
