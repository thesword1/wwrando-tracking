# How the in-game tracker reads how many of each logic item the player has.
#
# The compiled logic (tracker/logic_compiler.py) refers to items by index into the ITEMS section. Each entry is a read
# descriptor that asm/tracker/tracker_items.c evaluates against game memory to get the item's count: 0/1 for most items,
# the level for progressive items and capacity upgrades, and the number obtained for small keys.
#
# Addresses are from docs/dev/memory-map.md (section 3) and were checked against the item get functions: vanilla ones
# in the decomp's src/d/d_item.cpp, and the randomizer's in asm/patches/custom_funcs.asm and offline_mode.asm. Wherever
# the game keeps an "ever obtained" bit, that's what's read, so items that get used up (trading quest letters, the
# Cabana Deed) still count, like they do in the logic.
#
# ITEMS entry (8 bytes, big-endian): +0 u8 ItemReadKind, +1 u8 a, +2 u8 b, +3 pad, +4 u32 address
#   FLAG      1 if (byte & a) != 0
#   POPCOUNT  number of bits set in (byte & a): progressive items whose levels each set the next bit
#   BYTE      the byte's value (the tracker's small-keys-obtained counters, the wallet size 0/1/2)
#   LEVELS    (byte >= a) + (byte >= b): capacities (bombs/arrows 30/60/99) and the magic meter (0/16/32)
#   DUNGEON   1 if (byte & a) != 0, where the byte is dungeon stage b's mDungeonItem: the live copy (0x803C53A1)
#             while the player is in that stage (0x803C53A4 == b), the saved one (address) otherwise
#   SLOTS     number of the a bytes from address that aren't 0xFF (bottles)

from dataclasses import dataclass
from enum import IntEnum
import os
import re
import struct
from collections.abc import Sequence

from wwrando_paths import DATA_PATH

ITEM_FORMAT = ">BBBxI"

class ItemReadKind(IntEnum):
  FLAG = 0
  POPCOUNT = 1
  BYTE = 2
  LEVELS = 3
  DUNGEON = 4
  SLOTS = 5

@dataclass(frozen=True)
class ItemRead:
  kind: ItemReadKind
  address: int
  a: int = 0
  b: int = 0

  def pack(self) -> bytes:
    return struct.pack(ITEM_FORMAT, self.kind.value, self.a, self.b, self.address)


# dSv_player_get_item_c mItemFlags: "ever owned" bits per inventory slot (onGetItem(slot, bit)).
ITEM_FLAGS_ADDR = 0x803C4C59
ITEM_SLOTS_ADDR = 0x803C4C44
SLOT_TELESCOPE = 0
SLOT_SAIL = 1
SLOT_WIND_WAKER = 2
SLOT_GRAPPLING_HOOK = 3
SLOT_SPOILS_BAG = 4
SLOT_BOOMERANG = 5
SLOT_DEKU_LEAF = 6
SLOT_TINGLE_TUNER = 7
SLOT_PICTO_BOX = 8
SLOT_IRON_BOOTS = 9
SLOT_MAGIC_ARMOR = 10
SLOT_BAIT_BAG = 11
SLOT_BOW = 12
SLOT_BOMBS = 13
SLOT_BOTTLE_1 = 14
SLOT_DELIVERY_BAG = 18
SLOT_HOOKSHOT = 19
SLOT_SKULL_HAMMER = 20

WALLET_SIZE_ADDR = 0x803C4C1A
MAX_MAGIC_ADDR = 0x803C4C1B
MAX_ARROWS_ADDR = 0x803C4C77
MAX_BOMBS_ADDR = 0x803C4C78
# u32 of delivery bag items ever owned (onGetItemReserve(i) sets bit i).
DELIVERY_BAG_OWNED_ADDR = 0x803C4C98
SWORDS_ADDR = 0x803C4CBC
SHIELDS_ADDR = 0x803C4CBD
BRACELETS_ADDR = 0x803C4CBE
SONGS_ADDR = 0x803C4CC5
TRIFORCE_ADDR = 0x803C4CC6
PEARLS_ADDR = 0x803C4CC7
GET_MAP_ADDR = 0x803C4CDC
EVENT_FLAGS_ADDR = 0x803C522C
SAVED_STAGE_INFO_ADDR = 0x803C4F88
STAGE_INFO_SIZE = 0x24
DUNGEON_ITEM_OFFSET = 0x21
DUNGEON_ITEM_BIG_KEY = 0x04
# The tracker's small-keys-obtained counters (asm/tracker/tracker_save.h, TRK_SAVE_ADDR + TRK_SAVE_KEYS).
SMALL_KEYS_OBTAINED_ADDR = 0x803C532C + 0x04

DUNGEON_STAGE_IDS = {"DRC": 3, "FW": 4, "TotG": 5, "ET": 6, "WT": 7}
DUNGEON_KEY_COUNTERS = {"DRC": 0, "FW": 1, "TotG": 2, "ET": 3, "WT": 4}


def slot_flag(slot: int, bit: int = 0) -> ItemRead:
  return ItemRead(ItemReadKind.FLAG, ITEM_FLAGS_ADDR + slot, 1 << bit)

def bit_of_be_u32(address: int, bit: int) -> tuple[int, int]:
  """The byte address and mask of bit `bit` of a big-endian u32."""
  return address + 3 - (bit >> 3), 1 << (bit & 7)

def event_flag(event_bit: int) -> ItemRead:
  # Event bit 0xBBMM is byte BB, mask MM.
  return ItemRead(ItemReadKind.FLAG, EVENT_FLAGS_ADDR + (event_bit >> 8), event_bit & 0xFF)

def delivery_bag_item(reserve_bit: int) -> ItemRead:
  address, mask = bit_of_be_u32(DELIVERY_BAG_OWNED_ADDR, reserve_bit)
  return ItemRead(ItemReadKind.FLAG, address, mask)

def chart_owned(chart_number: int) -> ItemRead:
  # Chart number N owns bit N-1 of the u32[4] GetMap table (item_func_collectmapN -> onGetMap). Same as tracker/charts.py.
  index = chart_number - 1
  word, bit = index >> 5, index & 31
  address, mask = bit_of_be_u32(GET_MAP_ADDR + 4*word, bit)
  return ItemRead(ItemReadKind.FLAG, address, mask)


ITEM_READS: dict[str, ItemRead] = {
  # Inventory slots (vanilla item_func_* call onGetItem(slot, 0)).
  "Telescope": slot_flag(SLOT_TELESCOPE),
  "Boat's Sail": slot_flag(SLOT_SAIL),
  "Wind Waker": slot_flag(SLOT_WIND_WAKER),
  "Grappling Hook": slot_flag(SLOT_GRAPPLING_HOOK),
  "Spoils Bag": slot_flag(SLOT_SPOILS_BAG),
  "Boomerang": slot_flag(SLOT_BOOMERANG),
  "Deku Leaf": slot_flag(SLOT_DEKU_LEAF),
  "Tingle Tuner": slot_flag(SLOT_TINGLE_TUNER),
  "Iron Boots": slot_flag(SLOT_IRON_BOOTS),
  "Magic Armor": slot_flag(SLOT_MAGIC_ARMOR), # item_func_drgn_shield
  "Bait Bag": slot_flag(SLOT_BAIT_BAG),
  "Bombs": slot_flag(SLOT_BOMBS),
  "Delivery Bag": slot_flag(SLOT_DELIVERY_BAG),
  "Hookshot": slot_flag(SLOT_HOOKSHOT),
  "Skull Hammer": slot_flag(SLOT_SKULL_HAMMER),
  # Bottles can't be lost; any non-empty bottle slot counts.
  "Empty Bottle": ItemRead(ItemReadKind.SLOTS, ITEM_SLOTS_ADDR + SLOT_BOTTLE_1, 4),

  # Progressive items: each level sets the next bit (progressive_*_item_func in custom_funcs.asm calls the vanilla
  # item_func of the next level).
  "Progressive Sword": ItemRead(ItemReadKind.POPCOUNT, SWORDS_ADDR, 0x0F),
  "Progressive Shield": ItemRead(ItemReadKind.POPCOUNT, SHIELDS_ADDR, 0x03),
  "Progressive Bow": ItemRead(ItemReadKind.POPCOUNT, ITEM_FLAGS_ADDR + SLOT_BOW, 0x07),
  "Progressive Picto Box": ItemRead(ItemReadKind.POPCOUNT, ITEM_FLAGS_ADDR + SLOT_PICTO_BOX, 0x03),
  # 0 = 200, 1 = 1000, 2 = 5000 rupees (progressive_wallet_item_func).
  "Wallet Capacity Upgrade": ItemRead(ItemReadKind.BYTE, WALLET_SIZE_ADDR),
  # Max bombs/arrows start at 30 (init_save_with_tweaks) and go to 60 and 99.
  "Bomb Bag Capacity Upgrade": ItemRead(ItemReadKind.LEVELS, MAX_BOMBS_ADDR, 60, 99),
  "Quiver Capacity Upgrade": ItemRead(ItemReadKind.LEVELS, MAX_ARROWS_ADDR, 60, 99),
  # Max magic 0 / 16 / 32. The magic meter item fills the max meter gradually through the HUD, so this reads the new
  # level a moment after the item get.
  "Progressive Magic Meter": ItemRead(ItemReadKind.LEVELS, MAX_MAGIC_ADDR, 16, 32),

  "Power Bracelets": ItemRead(ItemReadKind.FLAG, BRACELETS_ADDR, 0x01),
  # The randomizer's own event bit (hurricane_spin_item_func), separate from Orca's event.
  "Hurricane Spin": event_flag(0x6901),

  # Songs (item_func_tact_song1-6 -> onTact(0-5)).
  "Wind's Requiem": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x01),
  "Ballad of Gales": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x02),
  "Command Melody": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x04),
  "Earth God's Lyric": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x08),
  "Wind God's Aria": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x10),
  "Song of Passing": ItemRead(ItemReadKind.FLAG, SONGS_ADDR, 0x20),

  # Pearls (dSymbol: Nayru 0, Din 1, Farore 2).
  "Nayru's Pearl": ItemRead(ItemReadKind.FLAG, PEARLS_ADDR, 0x01),
  "Din's Pearl": ItemRead(ItemReadKind.FLAG, PEARLS_ADDR, 0x02),
  "Farore's Pearl": ItemRead(ItemReadKind.FLAG, PEARLS_ADDR, 0x04),

  # Delivery bag items (onGetItemReserve(n): Note to Mom 0xD, Maggie's Letter 0xE, Moblin's Letter 0xF, Cabana Deed
  # 0x10). The bit stays set after the item is handed over.
  "Note to Mom": delivery_bag_item(0xD),
  "Maggie's Letter": delivery_bag_item(0xE),
  "Moblin's Letter": delivery_bag_item(0xF),
  "Cabana Deed": delivery_bag_item(0x10),

  # Tingle statues: the randomizer's event bits (*_tingle_statue_item_get_func).
  "Dragon Tingle Statue": event_flag(0x6A04),
  "Forbidden Tingle Statue": event_flag(0x6A08),
  "Goddess Tingle Statue": event_flag(0x6A10),
  "Earth Tingle Statue": event_flag(0x6A20),
  "Wind Tingle Statue": event_flag(0x6A40),
}

for i in range(8):
  ITEM_READS[f"Triforce Shard {i+1}"] = ItemRead(ItemReadKind.FLAG, TRIFORCE_ADDR, 1 << i)

for short_name, stage_id in DUNGEON_STAGE_IDS.items():
  # Big keys set the dungeon's big key bit wherever they're picked up (generic_on_dungeon_bit).
  saved_address = SAVED_STAGE_INFO_ADDR + STAGE_INFO_SIZE*stage_id + DUNGEON_ITEM_OFFSET
  ITEM_READS[f"{short_name} Big Key"] = ItemRead(ItemReadKind.DUNGEON, saved_address, DUNGEON_ITEM_BIG_KEY, stage_id)
  # Small keys: the number obtained, from the tracker's own counters (mKeyNum goes down when keys are used).
  ITEM_READS[f"{short_name} Small Key"] = ItemRead(ItemReadKind.BYTE, SMALL_KEYS_OBTAINED_ADDR + DUNGEON_KEY_COUNTERS[short_name])

def _load_chart_item_ids() -> dict[str, int]:
  with open(os.path.join(DATA_PATH, "item_names.txt"), "r") as f:
    matches = re.findall(r"^([0-9a-f]{2}) - (.+)$", f.read(), re.IGNORECASE | re.MULTILINE)
  return {
    item_name: int(item_id, 16) for item_id, item_name in matches
    if re.fullmatch(r"(Treasure|Triforce) Chart \d+|Ghost Ship Chart", item_name)
  }

# Chart N is item 0xFF - N.
for chart_name, item_id in _load_chart_item_ids().items():
  ITEM_READS[chart_name] = chart_owned(0xFF - item_id)


def get_item_read(item_name: str) -> ItemRead:
  if item_name not in ITEM_READS:
    raise KeyError(f"The in-game tracker can't read logic item {item_name!r}")
  return ITEM_READS[item_name]

def serialize_item_reads(item_names: Sequence[str]) -> bytes:
  return b"".join(get_item_read(item_name).pack() for item_name in item_names)


def read_item_count(read: ItemRead, read_u8) -> int:
  """Python reference for tracker_item_count(): read_u8(address) reads game memory."""
  match read.kind:
    case ItemReadKind.FLAG:
      return int(read_u8(read.address) & read.a != 0)
    case ItemReadKind.POPCOUNT:
      return bin(read_u8(read.address) & read.a).count("1")
    case ItemReadKind.BYTE:
      return read_u8(read.address)
    case ItemReadKind.LEVELS:
      value = read_u8(read.address)
      return int(value >= read.a) + int(value >= read.b)
    case ItemReadKind.DUNGEON:
      address = read.address
      if read_u8(0x803C53A4) == read.b:
        address = 0x803C5380 + DUNGEON_ITEM_OFFSET
      return int(read_u8(address) & read.a != 0)
    case ItemReadKind.SLOTS:
      return sum(read_u8(read.address + i) != 0xFF for i in range(read.a))
  raise ValueError(read.kind)
