#!/usr/bin/env python3
"""
Smoke test for the Dolphin harness: boots a Wind Waker ISO, checks the game ID in RAM,
presses START to get past the title screen, takes a screenshot and a savestate, and quits.

Usage:
  python tools/dolphin/smoke_test.py <path to GZLE01 ISO> [--user-dir DIR] [--keep-user-dir]
The ISO path can also be given with the WW_ISO_PATH environment variable.
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dolphin.harness import Dolphin

# Name of the stage currently loaded (dComIfG_gameInfo.play.mStartStage.mName).
CURRENT_STAGE_NAME_ADDR = 0x803C9D3C
TITLE_STAGE = "sea_T"
FILE_SELECT_STAGE = "Name"


def run(iso_path: Path, user_dir: Path) -> Path:
  with Dolphin(iso_path, user_dir) as dolphin:
    dolphin.wait_for_game_id("GZLE01", timeout=60)
    game_id = dolphin.memory.read_bytes(0x80000000, 6).decode("ascii")
    print(f"Game ID in RAM: {game_id}")

    # Round-trip a write in the low memory area that the game leaves unused.
    original = dolphin.memory.read_u32(0x80001800)
    dolphin.memory.write_u32(0x80001800, 0x12345678)
    assert dolphin.memory.read_u32(0xC0001800) == 0x12345678
    dolphin.memory.write_u32(0x80001800, original)

    stage = lambda mem: mem.read_cstring(CURRENT_STAGE_NAME_ADDR, 8)
    dolphin.wait_for(lambda mem: stage(mem) == TITLE_STAGE, timeout=60, message="Title screen was not reached")
    print(f"Reached title screen (stage {TITLE_STAGE!r})")

    # The title screen ignores input while its intro plays, so keep pressing START.
    def press_start(mem):
      if stage(mem) == FILE_SELECT_STAGE:
        return True
      dolphin.pad.press("START", duration=0.1, after=0.4)
      return False
    dolphin.wait_for(press_start, timeout=60, message="File select screen was not reached")
    print(f"Reached file select (stage {FILE_SELECT_STAGE!r})")
    time.sleep(2) # Let the file select screen fade in.

    screenshot = dolphin.screenshot()
    print(f"Screenshot: {screenshot}")

    state = dolphin.save_state(1)
    print(f"Savestate: {state}")
    dolphin.load_state(1)
    assert stage(dolphin.memory) == FILE_SELECT_STAGE
  print("Dolphin stopped")
  return screenshot


def main():
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("iso", nargs="?", default=os.environ.get("WW_ISO_PATH"))
  parser.add_argument("--user-dir", type=Path, help="Isolated Dolphin user directory (default: a new temp dir)")
  parser.add_argument("--keep-user-dir", action="store_true", help="Don't delete the temporary user directory")
  args = parser.parse_args()
  if not args.iso:
    parser.error("No ISO given (argument or WW_ISO_PATH)")

  user_dir = args.user_dir or Path(tempfile.mkdtemp(prefix="dolphin-smoke-"))
  try:
    run(Path(args.iso), user_dir)
  finally:
    if args.user_dir is None and not args.keep_user_dir:
      shutil.rmtree(user_dir, ignore_errors=True)
  print("Smoke test passed")


if __name__ == "__main__":
  main()
