// Tracker data in the save file: the 0x50-byte dSv_reserve_c area that vanilla never uses
// (docs/dev/memory-map.md, section 1.4). It's saved to and loaded from the memory card with the rest
// of the save, so everything here persists.

#ifndef TRACKER_SAVE_H
#define TRACKER_SAVE_H

#include "tracker_types.h"

#define TRK_SAVE_ADDR 0x803C532C
#define TRK_SAVE_SIZE 0x50
#define TRK_SAVE_LAYOUT_VERSION 1

// Offsets into the save region.
#define TRK_SAVE_VERSION 0x00 // u8, 0 = never initialised
#define TRK_SAVE_FLAGS 0x01 // u8, reserved
#define TRK_SAVE_SEED_TAG 0x02 // u16, the tables' seed tag
#define TRK_SAVE_KEYS 0x04 // u8[6], small keys obtained per dungeon (enum TrkDungeon)
#define TRK_SAVE_MANUAL_BITS 0x10 // 384 bits, manual marks by location index
#define TRK_SAVE_VISITED_BITS 0x40 // 64 bits, visited entrances by entrance index

#define TRK_MAX_LOCATIONS 384
#define TRK_MAX_ENTRANCES 64

// Bit i of a bitfield is in byte i >> 3, mask 1 << (i & 7).

enum TrkDungeon {
  TRK_DUNGEON_DRC = 0,
  TRK_DUNGEON_FW = 1,
  TRK_DUNGEON_TOTG = 2,
  TRK_DUNGEON_ET = 3,
  TRK_DUNGEON_WT = 4,
  TRK_NUM_DUNGEONS = 5,
};

void trk_save_reset(void);
void trk_save_validate(void);
u8 tracker_small_keys_obtained(int dungeon);
void tracker_count_small_key(int dungeon);
bool tracker_is_manual(u16 location_index);
bool tracker_is_entrance_visited(u16 entrance_index);
void trk_save_set_entrance_visited(u16 entrance_index);
bool trk_save_toggle_manual(u16 location_index);

#endif
