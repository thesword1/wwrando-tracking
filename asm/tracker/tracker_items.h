// Item counts for the tracker's logic. The ITEMS section has one read descriptor per logic item;
// tracker/items.py documents the format and is the Python reference for tracker_item_count().

#ifndef TRACKER_ITEMS_H
#define TRACKER_ITEMS_H

#include "tracker_types.h"

// tracker/items.py ItemReadKind.
enum TrkItemReadKind {
  TRK_ITEM_FLAG = 0,
  TRK_ITEM_POPCOUNT = 1,
  TRK_ITEM_BYTE = 2,
  TRK_ITEM_LEVELS = 3,
  TRK_ITEM_DUNGEON = 4,
  TRK_ITEM_SLOTS = 5,
};

#define TRK_ITEM_ENTRY_SIZE 8
#define TRK_ITEM_DUNGEON_BIG_KEY 0x04 // mDungeonItem bit (tracker/items.py DUNGEON_ITEM_BIG_KEY)

u8 tracker_item_count(u16 item_index);
bool tracker_has_big_key(u8 stage_id);

#endif
