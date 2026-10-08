# In-game spot check of the tracker's item reads (tracker/items.py): gives items through the Archipelago give-item
# array, which calls execItemGet like any other item get, and checks that each item's read descriptor then gives the
# expected count from the game's RAM. Uses the same ISO and savestate as test_tracker_dolphin.py.
#
# Needs flatpak Dolphin and WW_ISO_PATH. Only runs with -m dolphin.

import time
from pathlib import Path

from tracker.items import get_item_read, read_item_count
from test_tracker_dolphin import CUSTOM_SYMBOLS, TRK_STATE_MAGIC, cache_dir, pytestmark, read_state, tracker_iso, wait_for

__all__ = ["cache_dir", "tracker_iso", "pytestmark"]

# (item ID given, logic item name, expected count once every item below has been given)
GIVEN_ITEMS = [
  (0x27, "Progressive Bow", 2),
  (0x27, "Progressive Bow", 2),
  (0x38, "Progressive Sword", 2),
  (0x38, "Progressive Sword", 2),
  (0x3B, "Progressive Shield", 1),
  (0xAB, "Wallet Capacity Upgrade", 1),
  (0xAD, "Bomb Bag Capacity Upgrade", 1),
  (0xAF, "Quiver Capacity Upgrade", 1),
  (0xAF, "Quiver Capacity Upgrade", 2),
  (0xB1, "Progressive Magic Meter", 1),
  (0x25, "Grappling Hook", 1),
  (0x50, "Empty Bottle", 1),
  (0x61, "Triforce Shard 1", 1),
  (0x69, "Nayru's Pearl", 1),
  (0x72, "Song of Passing", 1),
  (0xAA, "Hurricane Spin", 1),
  (0x30, "Delivery Bag", 1),
  (0x9B, "Moblin's Letter", 1),
  (0xA3, "Dragon Tingle Statue", 1),
  (0x14, "DRC Big Key", 1),
  (0x13, "DRC Small Key", 2),
  (0x13, "DRC Small Key", 2),
  (0xE2, "Treasure Chart 28", 1),
]
NOT_GIVEN = ["Hookshot", "Triforce Shard 2", "Din's Pearl", "FW Big Key", "WT Small Key", "Treasure Chart 27", "Cabana Deed"]


def test_item_reads_in_game(tracker_iso: Path, cache_dir: Path, tmp_path: Path):
  from tools.dolphin.harness import Dolphin

  savestate = cache_dir / "ingame.sav"
  with Dolphin(tracker_iso, tmp_path / "dolphin-user", initial_save_state=savestate if savestate.exists() else None) as dolphin:
    dolphin.wait_for_game_id("GZLE99", timeout=60)
    wait_for(dolphin, lambda state, _: state["magic"] == TRK_STATE_MAGIC and state["in_game"], 90, "Gameplay was not reached")
    memory = dolphin.memory

    def count(item_name: str) -> int:
      return read_item_count(get_item_read(item_name), memory.read_u8)

    for item_name in {name for _, name, _ in GIVEN_ITEMS} | set(NOT_GIVEN):
      assert count(item_name) == 0, item_name

    give_array = CUSTOM_SYMBOLS["give_archipelago_item_array"]
    for item_id, item_name, _ in GIVEN_ITEMS:
      memory.write_u8(give_array, item_id)
      dolphin.wait_for(lambda memory: memory.read_u8(give_array) == 0xFF, timeout=10, message=f"Item 0x{item_id:02X} was not given")
    # The magic meter fills up gradually.
    time.sleep(3)

    counts = {name: count(name) for _, name, _ in GIVEN_ITEMS}
    assert counts == {name: expected for _, name, expected in GIVEN_ITEMS}
    for item_name in NOT_GIVEN:
      assert count(item_name) == 0, item_name
    print("Item counts:", counts)
    assert read_state(memory)["in_game"]
