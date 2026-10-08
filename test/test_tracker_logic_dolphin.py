# In-game test of the tracker's logic runtime (asm/tracker/tracker_logic.c): boots an AP-mode ISO with the tracker
# (progression_all fixture, the most locations and the largest logic), and checks that the logic is evaluated after
# loading, after item gets (given through the Archipelago give-item array, so through execItemGet) and when the sea
# chart opens, with the same results as the Python reference evaluator for the state in RAM. Prints how long an
# evaluation takes in the game.
#
# Needs flatpak Dolphin and WW_ISO_PATH. Only runs with -m dolphin. WW_TRACKER_DOLPHIN_CACHE works as for
# test_tracker_dolphin.py.

import shutil
import struct
import time
from pathlib import Path

import pytest

# Sets up sys.path for the randomizer's modules, so it comes first.
from test_tracker_dolphin import (
  CUSTOM_SYMBOLS, TRK_STATE_MAGIC, build_tracker_iso, make_cache_dir, pytestmark, read_state,  # noqa: F401
)
from tracker.items import get_item_read, read_item_count
from tracker.logic_compiler import LogicState, evaluate_bytecode
from tracker.serialize import Section, parse_tracker_tables
from test_aptww_fixtures import FIXTURES_DIR

FIXTURE = FIXTURES_DIR / "progression_all.aptww"
TEST_SPAWN = "sea,44,0"

# TrkState logic fields (asm/tracker/tracker_state.h).
LOGIC_STATE_OFFSET = 0xA0
LOGIC_STATE_FORMAT = ">IIIHBBHH8s48s"
LOGIC_OK = 1
TIME_BASE_HZ = 40_500_000

SAVE_ADDR = 0x803C532C
SAVE_VISITED_ADDR = SAVE_ADDR + 0x40

GIVEN_ITEMS = [0x22, 0x6D, 0x6E, 0x34, 0x31, 0x2F, 0x28, 0x2D, 0x29, 0x33] # Wind Waker, songs, Deku Leaf, Bombs, ...

def read_logic_state(memory) -> dict:
  data = memory.read_bytes(CUSTOM_SYMBOLS["tracker_state"] + LOGIC_STATE_OFFSET, struct.calcsize(LOGIC_STATE_FORMAT))
  names = [
    "evals", "ticks", "max_ticks", "num_in_logic", "status", "delay", "seen_checked", "seen_resets", "seen_visited",
    "in_logic",
  ]
  return dict(zip(names, struct.unpack(LOGIC_STATE_FORMAT, data)))

def in_logic_bits(memory, num_locations: int) -> list[bool]:
  bits = read_logic_state(memory)["in_logic"]
  return [bool(bits[i >> 3] >> (i & 7) & 1) for i in range(num_locations)]

def reference_results(memory, blob: bytes, parsed: dict, item_names: list[str]) -> list[bool]:
  counts = {name: read_item_count(get_item_read(name), memory.read_u8) for name in item_names}
  visited_bits = int.from_bytes(memory.read_bytes(SAVE_VISITED_ADDR, 8), "little")
  visited = {i for i in range(64) if visited_bits >> i & 1}
  assert read_state(memory)["num_checked"] == 0
  return evaluate_bytecode(parsed["logic"], item_names, LogicState(counts, visited, set()))

def item_names_from_tables(blob: bytes, parsed: dict) -> list[str]:
  # Match each ITEMS entry back to its name.
  from tracker.items import ITEM_READS
  by_entry = {}
  for name, read in ITEM_READS.items():
    by_entry.setdefault(read.pack(), name)
  offset, count, size = parsed["directory"][Section.ITEMS]
  return [by_entry[blob[offset + size*i:offset + size*(i+1)]] for i in range(count)]


@pytest.fixture(scope="module")
def logic_cache_dir(tmp_path_factory) -> Path:
  return make_cache_dir(tmp_path_factory, FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def logic_iso(logic_cache_dir: Path) -> Path:
  return build_tracker_iso(logic_cache_dir, FIXTURE, TEST_SPAWN)


def test_logic_in_game(logic_iso: Path, logic_cache_dir: Path, tmp_path: Path):
  from tools.dolphin.harness import Dolphin

  savestate = logic_cache_dir / "ingame.sav"
  with Dolphin(logic_iso, tmp_path / "dolphin-user", initial_save_state=savestate if savestate.exists() else None) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    dolphin.wait_for(
      lambda memory: (state := read_state(memory))["magic"] == TRK_STATE_MAGIC and state["in_game"],
      timeout=90, message="Gameplay was not reached",
    )
    time.sleep(1)
    if not savestate.exists():
      shutil.copyfile(dolphin.save_state(1), savestate)
    memory = dolphin.memory

    blob = memory.read_bytes(CUSTOM_SYMBOLS["tracker_data"], 0x6000)
    parsed = parse_tracker_tables(blob)
    item_names = item_names_from_tables(blob, parsed)
    num_locations = len(parsed["locations"])

    # Evaluated after loading.
    dolphin.wait_for(lambda memory: read_logic_state(memory)["status"] == LOGIC_OK, timeout=5, message="Logic was not evaluated")
    time.sleep(0.5)
    before = in_logic_bits(memory, num_locations)
    assert before == reference_results(memory, blob, parsed, item_names)
    evals = read_logic_state(memory)["evals"]

    # Item gets re-evaluate (half a second later).
    give_array = CUSTOM_SYMBOLS["give_archipelago_item_array"]
    for i, item_id in enumerate(GIVEN_ITEMS):
      memory.write_u8(give_array + i, item_id)
    dolphin.wait_for(lambda memory: read_logic_state(memory)["evals"] > evals, timeout=5, message="Item gets didn't re-evaluate")
    time.sleep(1)
    after = in_logic_bits(memory, num_locations)
    assert after == reference_results(memory, blob, parsed, item_names)
    assert sum(after) > sum(before)
    print(f"In logic: {sum(before)} -> {sum(after)} of {num_locations}")

    # Opening the sea chart evaluates right away.
    evals = read_logic_state(memory)["evals"]
    dolphin.pad.press("D_UP")
    dolphin.wait_for(lambda memory: read_logic_state(memory)["evals"] > evals, timeout=10, message="Opening the chart didn't re-evaluate")
    time.sleep(1.5)
    print("Screenshot:", dolphin.screenshot())

    logic = read_logic_state(memory)
    print(
      f"Logic evaluation: last {logic['ticks']} ticks ({logic['ticks'] / TIME_BASE_HZ * 1e6:.0f} us), "
      f"max {logic['max_ticks']} ticks ({logic['max_ticks'] / TIME_BASE_HZ * 1e6:.0f} us), {logic['evals']} evaluations, "
      f"{len(parsed['logic'])} bytes of bytecode"
    )
    # Well within a frame (16.7 ms).
    assert 0 < logic["max_ticks"] < TIME_BASE_HZ // 60 // 4
