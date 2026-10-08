// Reads how many of a logic item the player has (docs/dev/memory-map.md, section 3).

#include "tracker_items.h"
#include "tracker_mem.h"
#include "tracker_tables.h"

#define TRK_ITEM_CURRENT_STAGE_ID_ADDR 0x803C53A4
#define TRK_ITEM_LIVE_DUNGEON_ITEM_ADDR (0x803C5380 + 0x21)

TRK_INLINE u8 trk_popcount8(u8 value) {
  u8 count = 0;
  while (value) {
    count += value & 1;
    value >>= 1;
  }
  return count;
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
      // Like stage flags, a dungeon's items are in the live copy while the player is in it.
      if (trk_mem_u8(TRK_ITEM_CURRENT_STAGE_ID_ADDR) == b) {
        address = TRK_ITEM_LIVE_DUNGEON_ITEM_ADDR;
      }
      return (trk_mem_u8(address) & a) != 0;
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
