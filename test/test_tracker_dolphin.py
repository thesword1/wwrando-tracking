# In-game test of the tracker runtime: builds an AP-mode ISO with the tracker (entrance_rando
# fixture) that boots straight into gameplay on Outset (--test sea,44,0), runs it in Dolphin, writes
# game flags and inventory into RAM and checks that the tracker's save data and runtime state
# (asm/tracker/tracker_state.h) follow.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin.
# Set WW_TRACKER_DOLPHIN_CACHE to a directory to keep the built ISO and an in-game savestate there;
# later runs with the same tracker code, tables and randomizer reuse them.

import hashlib
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "gclib"))

from tracker.location_data import LocationType
from tracker.serialize import parse_tracker_tables
from test_aptww_fixtures import FIXTURES_DIR, load_plando
from test_tracker_serialize import tables_from_plando

pytestmark = [
  pytest.mark.dolphin,
  pytest.mark.skipif(shutil.which("flatpak") is None, reason="flatpak Dolphin is not installed"),
  pytest.mark.skipif(not os.environ.get("WW_ISO_PATH"), reason="WW_ISO_PATH is not set"),
]

FIXTURE = FIXTURES_DIR / "entrance_rando.aptww"
TEST_SPAWN = "sea,44,0"

TRACKER_STATE_FORMAT = ">IIHHHHBbh8sBB2x"
TRK_STATE_MAGIC = 0x54524B53
GROUP_CHECKED_OFFSET = 0x20

SAVE_ADDR = 0x803C532C
SAVE_KEYS_ADDR = SAVE_ADDR + 0x04
SAVE_VISITED_ADDR = SAVE_ADDR + 0x40
CURRENT_STAGE_ID_ADDR = 0x803C53A4
CURRENT_SPAWN_ADDR = 0x803C9D44
CURRENT_ROOM_ADDR = 0x803C9D46
DRC_SAVED_KEY_COUNT_ADDR = 0x803C5014
DRC_SMALL_KEY = 0x13

CUSTOM_SYMBOLS = YAML(typ="safe").load((REPO_ROOT / "asm" / "custom_symbols.txt").read_text())["sys/main.dol"]


def read_state(memory) -> dict:
  data = memory.read_bytes(CUSTOM_SYMBOLS["tracker_state"], GROUP_CHECKED_OFFSET + 128)
  fields = struct.unpack_from(TRACKER_STATE_FORMAT, data)
  names = [
    "magic", "frame_count", "num_locations", "num_checked", "num_auto_checked", "save_resets", "in_game", "room",
    "spawn", "stage_name", "last_visited_entrance", "num_groups",
  ]
  state = dict(zip(names, fields))
  state["group_checked"] = list(data[GROUP_CHECKED_OFFSET:])
  return state


def build_key(fixture: Path = FIXTURE, spawn: str = TEST_SPAWN) -> str:
  # Everything that changes the built ISO.
  digest = hashlib.sha256()
  paths = sorted((REPO_ROOT / "asm" / "patch_diffs").glob("*.txt")) + [
    REPO_ROOT / "asm" / "custom_symbols.txt", fixture, REPO_ROOT / "tweaks.py", REPO_ROOT / "randomizer.py",
  ] + sorted((REPO_ROOT / "tracker").glob("*.py"))
  for path in paths:
    digest.update(path.read_bytes())
  digest.update(spawn.encode())
  return digest.hexdigest()[:16]

def make_cache_dir(tmp_path_factory, fixture: Path = FIXTURE, spawn: str = TEST_SPAWN) -> Path:
  """A directory for the built ISO and savestates, kept between runs if WW_TRACKER_DOLPHIN_CACHE is set."""
  root = os.environ.get("WW_TRACKER_DOLPHIN_CACHE")
  root = Path(root) if root else tmp_path_factory.mktemp("tracker_dolphin")
  path = root / build_key(fixture, spawn)
  path.mkdir(parents=True, exist_ok=True)
  return path

def build_tracker_iso(cache_dir: Path, fixture: Path = FIXTURE, spawn: str = TEST_SPAWN) -> Path:
  """Builds an AP-mode ISO with the tracker that boots straight into gameplay at the given spawn."""
  isos = list(cache_dir.glob("*.iso"))
  if not isos:
    output = cache_dir / "build"
    output.mkdir(exist_ok=True)
    subprocess.run(
      [
        sys.executable, "wwrando.py", "--aptww", str(fixture), "--clean-iso", os.environ["WW_ISO_PATH"],
        "--output-folder", str(output), "--tracker", "--test", spawn,
      ],
      cwd=REPO_ROOT, check=True, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    built = list(output.glob("*.iso"))
    assert len(built) == 1
    built[0].rename(cache_dir / "tracker.iso")
    isos = [cache_dir / "tracker.iso"]
  return isos[0]

@pytest.fixture(scope="module")
def cache_dir(tmp_path_factory) -> Path:
  return make_cache_dir(tmp_path_factory)

@pytest.fixture(scope="module")
def tracker_iso(cache_dir: Path) -> Path:
  return build_tracker_iso(cache_dir)


def wait_for(dolphin, predicate, timeout: float, message: str):
  dolphin.wait_for(lambda memory: predicate(read_state(memory), memory), timeout=timeout, message=message)


def test_tracker_in_game(tracker_iso: Path, cache_dir: Path, tmp_path: Path):
  from tools.dolphin.harness import Dolphin

  tables = tables_from_plando(load_plando(FIXTURE))
  locations = tables.location_set.locations
  groups = tables.groups()
  savestate = cache_dir / "ingame.sav"

  with Dolphin(tracker_iso, tmp_path / "dolphin-user", initial_save_state=savestate if savestate.exists() else None) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    wait_for(dolphin, lambda state, _: state["magic"] == TRK_STATE_MAGIC and state["in_game"], 90, "Gameplay was not reached")
    time.sleep(1)
    if not savestate.exists():
      shutil.copyfile(dolphin.save_state(1), savestate)
    memory = dolphin.memory

    # The tables in RAM are the ones the randomizer wrote, and a new game stamped the save data with
    # their seed tag.
    blob = memory.read_bytes(CUSTOM_SYMBOLS["tracker_data"], 0x6000)
    parsed = parse_tracker_tables(blob)
    assert len(parsed["locations"]) == len(locations)
    save = memory.read_bytes(SAVE_ADDR, 0x50)
    assert save[0] == 1
    assert int.from_bytes(save[2:4], "big") == parsed["seed_tag"]
    assert save[4:] == bytes(0x4C)

    state = read_state(memory)
    assert state["num_locations"] == len(locations)
    assert state["num_groups"] == len(groups)
    assert state["num_checked"] == 0
    assert state["save_resets"] >= 1
    assert state["stage_name"].rstrip(b"\0") == b"sea"
    assert (state["room"], state["spawn"]) == (44, 0)

    # Auto-detection: set one location's flag of each kind present in the seed.
    current_stage = memory.read_u8(CURRENT_STAGE_ID_ADDR)
    tested = []
    for location_type in [LocationType.CHEST, LocationType.SWTCH, LocationType.PCKUP, LocationType.EVENT, LocationType.CHART, LocationType.BOCTO]:
      candidates = [loc for loc in locations if loc.check.type == location_type]
      if not candidates:
        continue
      # Prefer one in the current stage, to exercise the live copy.
      in_current_stage = [loc for loc in candidates if loc.check.stage_id == current_stage]
      loc = (in_current_stage or candidates)[0]
      address = loc.check.live_address if in_current_stage else loc.check.address
      memory.write_u8(address, memory.read_u8(address) | loc.check.mask)
      tested.append(loc)
      group_index = groups.index(loc.group)
      expected_in_group = sum(1 for other in tested if other.group == loc.group)
      wait_for(
        dolphin, lambda state, _: state["num_auto_checked"] == len(tested) and state["group_checked"][group_index] == expected_in_group,
        10, f"{loc.name} was not detected",
      )
    assert len(tested) >= 4
    print("Detected:", [(loc.check.type.name, loc.name) for loc in tested])

    # Small keys obtained: deliver a DRC small key through the Archipelago give-item array, which
    # goes through execItemGet like any other item get.
    give_array = CUSTOM_SYMBOLS["give_archipelago_item_array"]
    drc_keys_before = memory.read_u8(DRC_SAVED_KEY_COUNT_ADDR)
    memory.write_u8(give_array, DRC_SMALL_KEY)
    dolphin.wait_for(lambda memory: memory.read_u8(SAVE_KEYS_ADDR) == 1, timeout=10, message="DRC small key was not counted")
    assert memory.read_u8(DRC_SAVED_KEY_COUNT_ADDR) == drc_keys_before + 1
    assert memory.read_bytes(SAVE_KEYS_ADDR + 1, 4) == bytes(4)

    # Visited entrances: in this seed, the Secret Cave Entrance on Overlook Island leads to Cliff
    # Plateau Isles Inner Cave, whose exit is spawn 1 of sea room 0x2A.
    entrance = next(e for e in tables.entrance_set.entrances if e.entrance.name == "Secret Cave Entrance on Overlook Island")
    memory.write_u8(CURRENT_ROOM_ADDR, 0x2A)
    memory.write_u16(CURRENT_SPAWN_ADDR, 1)
    try:
      wait_for(dolphin, lambda state, _: state["last_visited_entrance"] == entrance.index, 10, "Entrance visit was not recorded")
    finally:
      memory.write_u8(CURRENT_ROOM_ADDR, 44)
      memory.write_u16(CURRENT_SPAWN_ADDR, 0)
    visited = memory.read_bytes(SAVE_VISITED_ADDR, 8)
    assert int.from_bytes(visited, "little") == 1 << entrance.index

    shot = dolphin.screenshot()
    print("Screenshot:", shot)

    # A save from another seed is reset.
    resets = read_state(memory)["save_resets"]
    memory.write_u16(SAVE_ADDR + 2, parsed["seed_tag"] ^ 0xFFFF)
    wait_for(dolphin, lambda state, _: state["save_resets"] == resets + 1, 10, "Save data from another seed was not reset")
    save = memory.read_bytes(SAVE_ADDR, 0x50)
    assert int.from_bytes(save[2:4], "big") == parsed["seed_tag"]
    assert save[4:0x40] == bytes(0x3C)

  assert shot.read_bytes().startswith(b"\x89PNG")
