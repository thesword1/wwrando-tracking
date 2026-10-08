# Host tests of the tracker's logic runtime (asm/tracker/tracker_logic.c): the C interpreter must give
# the same results as the Python reference evaluator (tracker/logic_compiler.py) for random states,
# and evaluations must run on the events they're meant for.

import dataclasses
import os
import random

import pytest

from wwrando import make_argparser # Must be imported first, it adds gclib to the path.
from randomizer import WWRandomizer
from aptww import read_ap_plando_file
from options.wwrando_options import EntranceMixMode, Options
from tracker.items import ItemReadKind, get_item_read, read_item_count
from tracker.locations import ENTRANCE_CATEGORIES
from tracker.logic_compiler import LogicState, TrackerLogicInput, evaluate_bytecode
from tracker.serialize import TrackerTables, build_tracker_tables, serialize_tracker_tables
from test_aptww_fixtures import FIXTURE_PATHS
from test_helpers import enable_all_progression_location_options
from test_tracker_c_runtime import CURRENT_STAGE_ID_ADDR, SAVE_ADDR, SAVE_MANUAL_ADDR, SAVE_VISITED_ADDR, enter_game
from tracker_c_host import TrackerHost

SEED_TAG = 0x4321
LOGIC_OK, LOGIC_NONE, LOGIC_ERROR = 1, 2, 3
UI_IN_LOGIC, UI_OUT_OF_LOGIC = 2, 3

def tables_for(options: Options, plando, starting_items=("Boat's Sail",)) -> TrackerTables:
  required_bosses = plando.required_bosses if options.required_bosses else None
  logic_input = TrackerLogicInput(options, plando.entrances, plando.charts, required_bosses, list(starting_items))
  entrance_options = {name: options[name] for name in ENTRANCE_CATEGORIES}
  return build_tracker_tables(plando.locations, plando.charts, plando.entrances, entrance_options, required_bosses, logic_input)

def fixture_tables(path) -> TrackerTables:
  options = Options()
  return tables_for(options, read_ap_plando_file(str(path), options))

def offline_tables() -> TrackerTables:
  options = Options()
  enable_all_progression_location_options(options)
  for name in ENTRANCE_CATEGORIES:
    options[name] = True
  options.mix_entrances = EntranceMixMode.MIX_DUNGEONS
  options.randomize_charts = True
  args = make_argparser().parse_args(args=["--dry"])
  rando = WWRandomizer("logicruntime", None, os.environ["WW_RANDO_OUTPUT_DIR"], options, cmd_line_args=args)
  rando.randomize_all()
  return tables_for(rando.options, rando.get_seed_plando(), rando.starting_items)

def load(tracker: TrackerHost, tables: TrackerTables):
  tracker.reset_ram()
  tracker.set_tables(serialize_tracker_tables(tables, SEED_TAG))
  tracker.write_u8(SAVE_ADDR, 1)
  tracker.write_u16(SAVE_ADDR + 2, SEED_TAG)

def item_addresses(tables: TrackerTables) -> list[int]:
  addresses = {CURRENT_STAGE_ID_ADDR, 0x803C5380 + 0x21}
  for item_name in tables.logic.items:
    read = get_item_read(item_name)
    size = read.a if read.kind == ItemReadKind.SLOTS else 1
    addresses.update(range(read.address, read.address + size))
  return sorted(addresses)

def randomize_state(tracker: TrackerHost, tables: TrackerTables, addresses: list[int], rng: random.Random):
  for address in addresses:
    tracker.write_u8(address, rng.choice([0, 0, 0xFF, 1, 2, 3, 16, 32, 60, 99, rng.randrange(256)]))
  tracker.write_u8(CURRENT_STAGE_ID_ADDR, rng.choice([0, 3, 4, 5, 6, 7]))
  density = rng.random()
  tracker.write_bytes(SAVE_MANUAL_ADDR, bytes(
    sum((rng.random() < density * 0.5) << bit for bit in range(8)) for _ in range(48)
  ))
  tracker.write_bytes(SAVE_VISITED_ADDR, bytes(
    sum((rng.random() < density) << bit for bit in range(8)) for _ in range(8)
  ))

def python_results(tracker: TrackerHost, tables: TrackerTables) -> list[bool]:
  lib = tracker.lib
  counts = {name: read_item_count(get_item_read(name), tracker.read_u8) for name in tables.logic.items}
  visited = {i for i in range(len(tables.entrance_set.entrances)) if lib.tracker_is_entrance_visited(i)}
  checked = {loc.index for loc in tables.location_set.locations if lib.tracker_is_checked(loc.index)}
  return evaluate_bytecode(tables.logic.serialize(), tables.logic.items, LogicState(counts, visited, checked))

def c_results(tracker: TrackerHost, tables: TrackerTables) -> list[bool]:
  tracker.lib.tracker_logic_evaluate()
  assert tracker.state.logic_status == LOGIC_OK
  return [tracker.lib.tracker_is_in_logic(loc.index) for loc in tables.location_set.locations]

def check_random_states(tracker: TrackerHost, tables: TrackerTables, num_states: int, seed: int):
  load(tracker, tables)
  addresses = item_addresses(tables)
  rng = random.Random(seed)
  num_in_logic = 0
  for _ in range(num_states):
    randomize_state(tracker, tables, addresses, rng)
    expected = python_results(tracker, tables)
    assert c_results(tracker, tables) == expected
    num_in_logic += sum(expected)
  assert 0 < num_in_logic < num_states * len(tables.location_set.locations)

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_c_interpreter_matches_reference(tracker: TrackerHost, path):
  check_random_states(tracker, fixture_tables(path), 1000, 7)

def test_c_interpreter_matches_reference_offline(tracker: TrackerHost):
  check_random_states(tracker, offline_tables(), 1000, 8)


def entrance_rando_tables() -> TrackerTables:
  return fixture_tables(next(p for p in FIXTURE_PATHS if p.stem == "entrance_rando"))

def test_evaluation_events(tracker: TrackerHost):
  tables = entrance_rando_tables()
  load(tracker, tables)
  lib = tracker.lib
  state = tracker.state
  enter_game(tracker)
  assert not lib.tracker_logic_available()

  # The first gameplay frame evaluates.
  lib.tracker_frame()
  lib.tracker_frame()
  assert state.logic_status == LOGIC_OK and state.logic_evals == 1
  for _ in range(5):
    lib.tracker_frame()
  assert state.logic_evals == 1

  # An item get evaluates TRK_LOGIC_ITEM_GET_DELAY frames later.
  lib.tracker_on_item_get()
  for _ in range(29):
    lib.tracker_frame()
  assert state.logic_evals == 1
  lib.tracker_frame()
  assert state.logic_evals == 2

  # Checking a location or visiting an entrance re-evaluates on the next frames.
  assert lib.tracker_toggle_manual(0)
  lib.tracker_frame()
  lib.tracker_frame()
  assert state.logic_evals == 3
  tracker.write_u8(SAVE_VISITED_ADDR, 0x01)
  lib.tracker_frame()
  lib.tracker_frame()
  assert state.logic_evals == 4
  for _ in range(5):
    lib.tracker_frame()
  assert state.logic_evals == 4

def test_in_logic_counts(tracker: TrackerHost):
  tables = entrance_rando_tables()
  load(tracker, tables)
  lib = tracker.lib
  enter_game(tracker)
  # Every item, every entrance visited: everything is in logic.
  for address in item_addresses(tables):
    tracker.write_u8(address, 0xFF)
  tracker.write_u8(CURRENT_STAGE_ID_ADDR, 0)
  tracker.write_bytes(SAVE_VISITED_ADDR, b"\xFF" * 8)
  for _ in range(3):
    lib.tracker_frame()
  num_locations = len(tables.location_set.locations)
  assert tracker.state.num_in_logic == num_locations
  groups = tables.groups()
  for group_index, group in enumerate(groups):
    in_group = len(tables.location_set.locations_in_group(group))
    assert tracker.state.group_available[group_index] == in_group
    if in_group:
      assert tracker.ui_counter(group_index).status == UI_IN_LOGIC
  # Checked locations aren't counted as available.
  assert lib.tracker_toggle_manual(0)
  for _ in range(3):
    lib.tracker_frame()
  assert tracker.state.num_in_logic == num_locations - 1

  # Nothing: only what needs no items and no entrances.
  load(tracker, tables)
  enter_game(tracker)
  for _ in range(3):
    lib.tracker_frame()
  expected = python_results(tracker, tables)
  assert tracker.state.num_in_logic == sum(expected) < num_locations
  out_of_logic = next(i for i, result in enumerate(expected) if not result)
  assert lib.tracker_ui_location_status(out_of_logic) == UI_OUT_OF_LOGIC

def test_no_logic_or_bad_bytecode(tracker: TrackerHost):
  tables = entrance_rando_tables()
  lib = tracker.lib
  load(tracker, dataclasses.replace(tables, logic=None))
  lib.tracker_logic_evaluate()
  assert tracker.state.logic_status == LOGIC_NONE
  assert not lib.tracker_logic_available() and not lib.tracker_is_in_logic(0)

  blob = bytearray(serialize_tracker_tables(tables, SEED_TAG))
  logic = tables.logic.serialize()
  start = blob.index(logic)
  rng = random.Random(9)
  for _ in range(300):
    corrupted = bytearray(blob)
    for _ in range(rng.randint(1, 4)):
      corrupted[start + rng.randrange(len(logic))] = rng.randrange(256)
    tracker.set_tables(bytes(corrupted))
    lib.tracker_logic_evaluate()
    assert tracker.state.logic_status in (LOGIC_OK, LOGIC_ERROR)
    if tracker.state.logic_status == LOGIC_ERROR:
      assert not any(lib.tracker_is_in_logic(i) for i in range(len(tables.location_set.locations)))
