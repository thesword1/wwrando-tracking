# In-game test of the tracker's sea chart UI (asm/tracker/tracker_ui.c): builds an AP-mode ISO with the
# tracker (progression_all fixture, so most sea squares have locations) that boots straight into
# gameplay on Outset, opens the sea chart with D-pad Up and checks through the UI state in RAM that the
# tracker draws on the chart's world view, and only there. Screenshots are printed (run with -s) for a
# human to look at; set WW_TRACKER_SCREENSHOT_DIR to also copy them there.
#
# Needs flatpak Dolphin and WW_ISO_PATH (a vanilla ISO). Only runs with -m dolphin. Like
# test_tracker_dolphin.py, WW_TRACKER_DOLPHIN_CACHE keeps the built ISO and an in-game savestate.

import os
import shutil
import struct
import time
from pathlib import Path

import pytest

from test_aptww_fixtures import FIXTURES_DIR
from test_tracker_dolphin import (
  CUSTOM_SYMBOLS, TRK_STATE_MAGIC, build_tracker_iso, make_cache_dir, pytestmark, read_state,  # noqa: F401
)

FIXTURE = FIXTURES_DIR / "progression_all.aptww"
TEST_SPAWN = "sea,44,0"

UI_STATE_FORMAT = ">IIB"
VIEW_NONE, VIEW_WORLD = 0, 1

SAVE_MANUAL_ADDR = 0x803C532C + 0x10


def read_ui_state(memory) -> dict:
  data = memory.read_bytes(CUSTOM_SYMBOLS["tracker_ui_state"], struct.calcsize(UI_STATE_FORMAT))
  return dict(zip(["proc_frame", "draw_frame", "view"], struct.unpack(UI_STATE_FORMAT, data)))

def is_drawing(memory) -> bool:
  frame = read_state(memory)["frame_count"]
  return frame - read_ui_state(memory)["draw_frame"] <= 2

def keep_screenshot(path: Path, name: str) -> Path:
  print(f"Screenshot ({name}):", path)
  target_dir = os.environ.get("WW_TRACKER_SCREENSHOT_DIR")
  if target_dir:
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, Path(target_dir) / f"{name}.png")
  return path


@pytest.fixture(scope="module")
def ui_cache_dir(tmp_path_factory) -> Path:
  return make_cache_dir(tmp_path_factory, FIXTURE, TEST_SPAWN)

@pytest.fixture(scope="module")
def ui_iso(ui_cache_dir: Path) -> Path:
  return build_tracker_iso(ui_cache_dir, FIXTURE, TEST_SPAWN)

@pytest.fixture
def dolphin(ui_iso: Path, ui_cache_dir: Path, tmp_path: Path):
  from tools.dolphin.harness import Dolphin

  savestate = ui_cache_dir / "ingame.sav"
  with Dolphin(ui_iso, tmp_path / "dolphin-user", initial_save_state=savestate if savestate.exists() else None) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    dolphin.wait_for(
      lambda memory: (state := read_state(memory))["magic"] == TRK_STATE_MAGIC and state["in_game"],
      timeout=90, message="Gameplay was not reached",
    )
    time.sleep(1)
    if not savestate.exists():
      shutil.copyfile(dolphin.save_state(1), savestate)
    yield dolphin


def test_chart_overview(dolphin):
  memory = dolphin.memory
  assert not is_drawing(memory)

  dolphin.pad.press("D_UP")
  dolphin.wait_for(is_drawing, timeout=10, message="The tracker doesn't draw on the sea chart")
  assert read_ui_state(memory)["view"] == VIEW_WORLD
  keep_screenshot(dolphin.screenshot(), "chart-overview")

  # Counters follow manual marks.
  num_checked = read_state(memory)["num_checked"]
  memory.write_u8(SAVE_MANUAL_ADDR, 0xFF)
  dolphin.wait_for(lambda memory: read_state(memory)["num_checked"] == num_checked + 8, timeout=5, message="Marks not counted")
  keep_screenshot(dolphin.screenshot(), "chart-overview-marked")

  # The square view isn't drawn on (yet), and the chart's own controls still work.
  dolphin.pad.press("A")
  dolphin.wait_for(lambda memory: read_ui_state(memory)["view"] == VIEW_NONE, timeout=5, message="A didn't zoom in")
  time.sleep(1)
  assert not is_drawing(memory)
  dolphin.pad.press("B")
  dolphin.wait_for(is_drawing, timeout=5, message="B didn't zoom back out")

  # Closing the chart stops the drawing.
  dolphin.pad.press("D_DOWN")
  time.sleep(1.5)
  assert not is_drawing(memory)
