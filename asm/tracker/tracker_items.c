// Reads how many of a logic item the player has (docs/dev/memory-map.md, section 3).

#include "tracker_items.h"
#include "tracker_mem.h"
#include "tracker_tables.h"

#define TRK_ITEM_CURRENT_STAGE_ID_ADDR 0x803C53A4
#define TRK_ITEM_LIVE_DUNGEON_ITEM_ADDR (0x803C5380 + 0x21)
#define TRK_ITEM_SAVED_STAGE_INFO_ADDR 0x803C4F88 // dSv_memory_c mSavedata.mMemory[], 0x24 bytes each
#define TRK_ITEM_STAGE_INFO_SIZE 0x24
#define TRK_ITEM_DUNGEON_ITEM_OFFSET 0x21 // mDungeonItem

TRK_INLINE u8 trk_popcount8(u8 value) {
  u8 count = 0;
  while (value) {
    count += value & 1;
    value >>= 1;
  }
  return count;
}

// Bits of a dungeon stage's mDungeonItem (map, compass, big key, ...). Like stage flags, they're in the live copy while
// the player is in that stage. saved_address is the saved copy's byte.
TRK_INLINE bool trk_dungeon_item_bit(u32 saved_address, u8 stage_id, u8 mask) {
  u32 address = saved_address;
  if (trk_mem_u8(TRK_ITEM_CURRENT_STAGE_ID_ADDR) == stage_id) {
    address = TRK_ITEM_LIVE_DUNGEON_ITEM_ADDR;
  }
  return (trk_mem_u8(address) & mask) != 0;
}

// Whether the dungeon with stage stage_id's big key is owned.
TRK_EXPORT bool tracker_has_big_key(u8 stage_id) {
  u32 saved_address = TRK_ITEM_SAVED_STAGE_INFO_ADDR + TRK_ITEM_STAGE_INFO_SIZE*stage_id + TRK_ITEM_DUNGEON_ITEM_OFFSET;
  return trk_dungeon_item_bit(saved_address, stage_id, TRK_ITEM_DUNGEON_BIG_KEY);
}

TRK_EXPORT u8 tracker_item_count(u16 item_index) {
  if (item_index >= trk_count(TRK_SEC_ITEMS)) {
    return 0;
  }
  const u8* p = trk_section(TRK_SEC_ITEMS) + item_index*TRK_ITEM_ENTRY_SIZE;
  u8 a = p[1];
  u8 b = p[2];
  u32 address = trk_be32(p + 4);
  switch (p[0]) {
    case TRK_ITEM_FLAG:
      return (trk_mem_u8(address) & a) != 0;
    case TRK_ITEM_POPCOUNT:
      return trk_popcount8(trk_mem_u8(address) & a);
    case TRK_ITEM_BYTE:
      return trk_mem_u8(address);
    case TRK_ITEM_LEVELS: {
      u8 value = trk_mem_u8(address);
      return (value >= a) + (value >= b);
    }
    case TRK_ITEM_DUNGEON:
      return trk_dungeon_item_bit(address, b, a);
    case TRK_ITEM_SLOTS: {
      u8 count = 0;
      for (u8 i = 0; i < a; i++) {
        count += trk_mem_u8(address + i) != 0xFF;
      }
      return count;
    }
    default:
      return 0;
  }
}
