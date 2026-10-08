import dataclasses
import os
import random
from pathlib import Path

import pytest

from wwrando import make_argparser # Must be imported first, it adds gclib to the path.
from randomizer import WWRandomizer, Plando
from aptww import read_ap_plando_file
from logic.logic import Logic
from options.wwrando_options import EntranceMixMode, KeyLunacyMode, Options, SwordMode, TrickDifficulty
from tracker.locations import ENTRANCE_CATEGORIES, get_randomized_exits
from tracker.logic_compiler import (
  GOAL_REQUIREMENT, LOGIC_HEADER_SIZE, MAX_STACK_DEPTH, LogicState, TrackerLogicInput, _Compiler, _LogicRandoStub,
  checked, or_, evaluate_bytecode, evaluate_bytecode_with_goal, evaluate_node,
)
from tracker.serialize import (
  TRACKER_DATA_RESERVE_SIZE, Section, TrackerTables, build_tracker_tables, parse_tracker_tables,
  serialize_tracker_tables,
)
from test_aptww_fixtures import FIXTURE_PATHS
from test_helpers import enable_all_progression_location_options

ALL_ENTRANCE_OPTIONS = list(ENTRANCE_CATEGORIES)

def dry_rando(options: Options, seed: str, plando: Plando | None = None) -> WWRandomizer:
  args = make_argparser().parse_args(args=["--dry"])
  rando = WWRandomizer(seed, None, os.environ["WW_RANDO_OUTPUT_DIR"], options, plando, cmd_line_args=args)
  rando.randomize_all()
  return rando

def tracker_tables(options: Options, plando: Plando, starting_items) -> TrackerTables:
  required_bosses = plando.required_bosses if options.required_bosses else None
  logic_input = TrackerLogicInput(options, plando.entrances, plando.charts, required_bosses, starting_items)
  entrance_options = {name: options[name] for name in ENTRANCE_CATEGORIES}
  return build_tracker_tables(plando.locations, plando.charts, plando.entrances, entrance_options, required_bosses, logic_input)

def logic_for_plando(options: Options, plando: Plando) -> Logic:
  """A Logic set up with an .aptww plando's entrances, charts and required bosses, the way an offline seed's is."""
  from tracker.locations import VANILLA_ISLAND_NUMBER_TO_CHART_NAME
  logic = Logic(_LogicRandoStub(options))
  for entrance_name, exit_name in plando.entrances.items():
    logic.set_macro("Can Access " + exit_name, "Can Access " + entrance_name)
  for island_number in range(1, 49+1):
    chart_name = VANILLA_ISLAND_NUMBER_TO_CHART_NAME[island_number]
    destination = plando.charts[island_number-1]
    req = f"{chart_name} & Any Wallet Upgrade" if "Triforce Chart" in chart_name else chart_name
    logic.set_macro(f"Chart for Island {destination}", req)
  if options.required_bosses:
    logic.set_macro("Can Defeat All Required Bosses", " & ".join(
      f"Can Access Item Location \"{loc}\"" for loc in plando.required_bosses
    ))
  return logic

def item_counts(owned_items: list[str]) -> dict[str, int]:
  counts = {}
  for item_name in owned_items:
    counts[item_name] = counts.get(item_name, 0) + 1
  return counts

def compare_with_logic(logic: Logic, tables: TrackerTables, starting_items: list[str], num_inventories: int, rng_seed: int):
  """For random inventories, with every entrance visited and nothing checked, the tracker's logic must say exactly
  what the randomizer's Logic says, for every location and for the goal (GO MODE)."""
  rng = random.Random(rng_seed)
  blob = tables.logic.serialize()
  location_names = [loc.name for loc in tables.location_set.locations]
  all_visited = set(range(len(tables.entrance_set.entrances)))
  pool = list(logic.all_progress_items)
  mismatches = []
  num_in_logic = 0
  goal_outcomes = set()
  # Random inventories, plus nothing and everything so that the goal is seen both ways.
  inventories = [[], pool] + [rng.sample(pool, rng.randint(0, len(pool))) for _ in range(num_inventories)]
  for inventory in inventories:
    owned = list(starting_items) + inventory
    logic.currently_owned_items = [logic.clean_item_name(item_name) for item_name in owned]
    logic.clear_req_caches()
    state = LogicState(item_counts(logic.currently_owned_items), all_visited, set())
    results, goal = evaluate_bytecode_with_goal(blob, tables.logic.items, state)
    for name, result in zip(location_names, results):
      expected = logic.check_location_accessible(name)
      num_in_logic += expected
      if result != expected:
        mismatches.append((name, expected, sorted(owned)))
    expected_goal = logic.check_requirement_met(GOAL_REQUIREMENT)
    goal_outcomes.add(expected_goal)
    if goal != expected_goal:
      mismatches.append((GOAL_REQUIREMENT, expected_goal, sorted(owned)))
  assert not mismatches, mismatches[:3]
  # Make sure the inventories exercised both outcomes.
  assert 0 < num_in_logic < len(inventories) * len(location_names)
  assert goal_outcomes == {False, True}


OFFLINE_OPTION_SETS = {
  "defaults": {},
  "all_progression_er_charts": {
    "all_progression": True,
    "randomize_dungeon_entrances": True, "randomize_secret_cave_entrances": True,
    "randomize_miniboss_entrances": True, "randomize_boss_entrances": True,
    "randomize_secret_cave_inner_entrances": True, "randomize_fairy_fountain_entrances": True,
    "mix_entrances": EntranceMixMode.MIX_DUNGEONS, "randomize_charts": True,
  },
  "swordless_tuner_keylunacy": {
    "all_progression": True, "sword_mode": SwordMode.SWORDLESS, "enable_tuner_logic": True,
    "randomize_smallkeys": KeyLunacyMode.KEYLUNACY, "randomize_bigkeys": KeyLunacyMode.ANY_DUNGEON,
  },
  "swords_optional_start_with_keys_tricks_bosses": {
    "all_progression": True, "sword_mode": SwordMode.SWORDS_OPTIONAL,
    "randomize_smallkeys": KeyLunacyMode.START_WITH, "randomize_bigkeys": KeyLunacyMode.START_WITH,
    "logic_obscurity": TrickDifficulty.VERY_HARD, "logic_precision": TrickDifficulty.VERY_HARD,
    "required_bosses": True, "num_required_bosses": 3,
    "randomize_dungeon_entrances": True, "randomize_boss_entrances": True,
    "starting_gear": ["Treasure Chart 3", "Grappling Hook", "Progressive Bow"],
    "num_starting_triforce_shards": 3,
  },
}

def offline_options(option_set: str) -> Options:
  options = Options()
  for name, value in OFFLINE_OPTION_SETS[option_set].items():
    if name == "all_progression":
      enable_all_progression_location_options(options)
    else:
      options[name] = value
  if options.starting_gear:
    options.randomized_gear = [item for item in options.randomized_gear if item not in options.starting_gear]
  return options

@pytest.fixture(scope="module", params=list(OFFLINE_OPTION_SETS))
def offline_seed(request):
  rando = dry_rando(offline_options(request.param), "trackerlogic")
  plando = rando.get_seed_plando()
  tables = tracker_tables(rando.options, plando, rando.starting_items)
  return rando, tables

def test_offline_logic_matches_randomizer_logic(offline_seed):
  rando, tables = offline_seed
  compare_with_logic(rando.logic, tables, rando.starting_items, 60, 1)

@pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda p: p.stem)
def test_archipelago_logic_matches_randomizer_logic(path: Path):
  options = Options()
  plando = read_ap_plando_file(str(path), options)
  tables = tracker_tables(options, plando, ["Boat's Sail"])
  compare_with_logic(logic_for_plando(options, plando), tables, ["Boat's Sail"], 60, 2)


def random_state(rng: random.Random, tables: TrackerTables) -> LogicState:
  counts = {item_name: rng.choice([0, 0, 1, 2, 3, 4]) for item_name in tables.logic.items}
  num_entrances = len(tables.entrance_set.entrances)
  num_locations = len(tables.location_set.locations)
  visited = {i for i in range(num_entrances) if rng.random() < 0.5}
  checked_locations = {i for i in range(num_locations) if rng.random() < 0.3}
  return LogicState(counts, visited, checked_locations)

def fixture_tables() -> list[TrackerTables]:
  tables = []
  for path in FIXTURE_PATHS:
    options = Options()
    plando = read_ap_plando_file(str(path), options)
    tables.append(tracker_tables(options, plando, ["Boat's Sail"]))
  return tables

def test_bytecode_matches_expressions():
  # The emitted code (shared slots, operand order, AND/OR chunking) computes the same thing as the expression trees.
  rng = random.Random(3)
  for tables in fixture_tables():
    blob = tables.logic.serialize()
    for _ in range(200):
      state = random_state(rng, tables)
      results, goal = evaluate_bytecode_with_goal(blob, tables.logic.items, state)
      cache = {}
      assert results == [evaluate_node(expr, state, cache) for expr in tables.logic.location_exprs]
      assert goal == evaluate_node(tables.logic.goal_expr, state, cache)

def test_offline_bytecode_matches_expressions(offline_seed):
  _, tables = offline_seed
  rng = random.Random(4)
  blob = tables.logic.serialize()
  for _ in range(100):
    state = random_state(rng, tables)
    cache = {}
    results, goal = evaluate_bytecode_with_goal(blob, tables.logic.items, state)
    assert results == [evaluate_node(expr, state, cache) for expr in tables.logic.location_exprs]
    assert goal == evaluate_node(tables.logic.goal_expr, state, cache)


def all_items_state(tables: TrackerTables, visited, checked_locations=()) -> LogicState:
  return LogicState({item_name: 99 for item_name in tables.logic.items}, set(visited), set(checked_locations))

def test_unvisited_entrances_are_out_of_logic(offline_seed):
  # Like the website: what's behind a randomized entrance is only in logic once that entrance has been visited.
  rando, tables = offline_seed
  blob = tables.logic.serialize()
  entrance_options = {name: rando.options[name] for name in ENTRANCE_CATEGORIES}
  randomized_exits = {zone_exit.unique_name for zone_exit in get_randomized_exits(entrance_options)}
  everything = evaluate_bytecode(blob, tables.logic.items, all_items_state(tables, range(64)))
  nothing_visited = evaluate_bytecode(blob, tables.logic.items, all_items_state(tables, []))
  behind_entrances = 0
  for loc, in_logic, in_logic_unvisited in zip(tables.location_set.locations, everything, nothing_visited):
    assert in_logic, loc.name
    if loc.zone_exit in randomized_exits:
      behind_entrances += 1
      assert not in_logic_unvisited, loc.name
  assert (behind_entrances > 0) == bool(randomized_exits)

def test_has_accessed_other_location():
  # Mail letters count the boss they depend on as defeated once its location is checked (website behaviour).
  options = Options()
  plando = read_ap_plando_file(str(FIXTURE_PATHS[0]), options)
  locations = {**plando.locations, "Mailbox - Letter from Orca": {}, "Forbidden Woods - Kalle Demos Heart Container": {}}
  tables = tracker_tables(options, dataclasses.replace(plando, locations=locations), ["Boat's Sail"])
  names = [loc.name for loc in tables.location_set.locations]
  orca = names.index("Mailbox - Letter from Orca")
  kalle_demos = names.index("Forbidden Woods - Kalle Demos Heart Container")
  blob = tables.logic.serialize()
  nothing = LogicState({}, set(), set())
  assert not evaluate_bytecode(blob, tables.logic.items, nothing)[orca]
  boss_checked = LogicState({}, set(), {kalle_demos})
  assert evaluate_bytecode(blob, tables.logic.items, boss_checked)[orca]

def test_required_bosses_count_once_checked():
  # Only Defeat Ganondorf (not a tracked location) depends on the required bosses, so check the macro itself: each boss
  # counts as defeated once its location is checked, or if it's in logic.
  path = next(p for p in FIXTURE_PATHS if p.stem == "charts_required_bosses")
  options = Options()
  plando = read_ap_plando_file(str(path), options)
  assert options.required_bosses
  tables = tracker_tables(options, plando, ["Boat's Sail"])
  names = [loc.name for loc in tables.location_set.locations]
  logic_input = TrackerLogicInput(options, plando.entrances, plando.charts, plando.required_bosses, ["Boat's Sail"])
  compiler = _Compiler(logic_input, names, {e.entrance.name: e.index for e in tables.entrance_set.entrances})
  macro = compiler.req("Can Defeat All Required Bosses")
  assert macro.kind == "and" and len(macro.children) == len(plando.required_bosses)
  for boss_location, term in zip(plando.required_bosses, macro.children):
    assert term is or_(checked(names.index(boss_location)), compiler.location_need(boss_location))
  
  state = LogicState({}, set(), set())
  assert not evaluate_node(macro, state)
  state.checked = {names.index(loc) for loc in plando.required_bosses}
  assert evaluate_node(macro, state)

def test_goal_needs_required_bosses():
  # GO MODE needs the required bosses: with every item but nothing visited, the bosses behind randomized dungeon
  # entrances are out of logic, so the goal is too, until their locations are checked (or the entrances visited).
  options = offline_options("swords_optional_start_with_keys_tricks_bosses")
  rando = dry_rando(options, "goalbosses")
  plando = rando.get_seed_plando()
  tables = tracker_tables(rando.options, plando, rando.starting_items)
  blob = tables.logic.serialize()
  names = [loc.name for loc in tables.location_set.locations]
  bosses = {names.index(loc) for loc in plando.required_bosses}
  assert bosses
  assert not evaluate_bytecode_with_goal(blob, tables.logic.items, all_items_state(tables, []))[1]
  assert evaluate_bytecode_with_goal(blob, tables.logic.items, all_items_state(tables, [], bosses))[1]
  assert evaluate_bytecode_with_goal(blob, tables.logic.items, all_items_state(tables, range(64)))[1]
  # All bosses but one isn't enough.
  assert not evaluate_bytecode_with_goal(blob, tables.logic.items, all_items_state(tables, [], sorted(bosses)[1:]))[1]
  # Nor is having the bosses without the items Ganondorf needs.
  no_items = LogicState({}, set(range(64)), bosses)
  assert not evaluate_bytecode_with_goal(blob, tables.logic.items, no_items)[1]

def test_goal_swordless():
  # In Swordless mode Ganondorf doesn't need a sword (Can Defeat Ganondorf: Hero's Sword | In Swordless Mode).
  options = offline_options("swordless_tuner_keylunacy")
  rando = dry_rando(options, "goalswordless")
  tables = tracker_tables(rando.options, rando.get_seed_plando(), rando.starting_items)
  assert "Progressive Sword" not in tables.logic.items
  blob = tables.logic.serialize()
  assert evaluate_bytecode_with_goal(blob, tables.logic.items, all_items_state(tables, range(64)))[1]

def test_start_with_keys_need_no_reads():
  options = offline_options("swords_optional_start_with_keys_tricks_bosses")
  rando = dry_rando(options, "startwithkeys")
  tables = tracker_tables(rando.options, rando.get_seed_plando(), rando.starting_items)
  assert not any(item_name.endswith(" Small Key") or item_name.endswith(" Big Key") for item_name in tables.logic.items)
  # Swords Optional never expects a sword; starting items are resolved at compile time.
  assert "Progressive Sword" not in tables.logic.items
  assert "Grappling Hook" not in tables.logic.items
  assert "Boat's Sail" not in tables.logic.items


def test_serialized_logic_section():
  for tables in fixture_tables():
    blob = serialize_tracker_tables(tables, 1)
    parsed = parse_tracker_tables(blob)
    logic_blob = parsed["logic"]
    assert logic_blob == tables.logic.serialize()
    offset, count, entry_size = parsed["directory"][Section.LOGIC]
    assert count == len(logic_blob) and entry_size == 1
    num_slots, num_locations = int.from_bytes(logic_blob[0:2], "big"), int.from_bytes(logic_blob[2:4], "big")
    assert num_locations == len(parsed["locations"])
    assert logic_blob[4] <= MAX_STACK_DEPTH
    assert logic_blob[5] == len(tables.logic.items)
    assert int.from_bytes(logic_blob[6:8], "big") == len(logic_blob) - LOGIC_HEADER_SIZE
    assert logic_blob[8] == 1 and tables.logic.goal_expr is not None

# Bytecode size budget. The rest of the tables take at most ~14.1 KB of the 24 KB reserve (all locations and
# entrances tracked).
LOGIC_SIZE_BUDGET = 0x2000

def test_logic_size_budget(offline_seed):
  rando, tables = offline_seed
  logic_size = len(tables.logic.serialize())
  assert logic_size <= LOGIC_SIZE_BUDGET
  assert len(serialize_tracker_tables(tables, 1)) <= TRACKER_DATA_RESERVE_SIZE

def test_fixture_logic_size_budget():
  for tables in fixture_tables():
    assert len(tables.logic.serialize()) <= LOGIC_SIZE_BUDGET
    assert len(serialize_tracker_tables(tables, 1)) <= TRACKER_DATA_RESERVE_SIZE
