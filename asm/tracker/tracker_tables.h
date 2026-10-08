// Reader for the patch-time tracker tables written by tracker/serialize.py into tracker_data.
// tracker/serialize.py documents the format; the constants here must match it.

#ifndef TRACKER_TABLES_H
#define TRACKER_TABLES_H

#include "tracker_types.h"

#define TRK_MAGIC 0x5757544B // "WWTK"
#define TRK_FORMAT_VERSION 4
#define TRK_HEADER_SIZE 0x20
#define TRK_DIR_ENTRY_SIZE 8

enum TrkSection {
  TRK_SEC_LOCATIONS = 0,
  TRK_SEC_GROUPS = 1,
  TRK_SEC_ENTRANCES = 2,
  TRK_SEC_TRIGGERS = 3,
  TRK_SEC_CHARTS = 4,
  TRK_SEC_STRINGS = 5,
  TRK_SEC_LOGIC = 6,
  TRK_SEC_ITEMS = 7,
  TRK_SEC_STAGES = 8,
  TRK_SEC_DUNGEONS = 9,
  TRK_NUM_SECTIONS = 10,
};

// tracker/location_data.py LocationType.
enum TrkLocationType {
  TRK_TYPE_NONE = 0,
  TRK_TYPE_CHART = 1,
  TRK_TYPE_BOCTO = 2,
  TRK_TYPE_CHEST = 3,
  TRK_TYPE_SWTCH = 4,
  TRK_TYPE_PCKUP = 5,
  TRK_TYPE_EVENT = 6,
  TRK_TYPE_SPECL = 7,
};

// tracker/locations.py SpecialCheck.
enum TrkSpecial {
  TRK_SPECIAL_LENZO_ASSISTANT = 0,
  TRK_SPECIAL_MAGGIE_DELIVERY = 1,
  TRK_SPECIAL_LETTER_HOSKITS_GIRLFRIEND = 2,
  TRK_SPECIAL_LETTER_BAITOS_MOTHER = 3,
  TRK_SPECIAL_LETTER_GRANDMA = 4,
  TRK_SPECIAL_ANKLE_ALL_STATUES = 5,
};

// tracker/locations.py GroupKind.
enum TrkGroupKind {
  TRK_GROUP_SQUARE = 0,
  TRK_GROUP_DUNGEON = 1,
  TRK_GROUP_ZONE = 2,
  TRK_GROUP_CAVE = 3,
};

#define TRK_NONE 0xFF

typedef struct {
  u8 group_id;
  u8 type;
  u8 stage_id; // TRK_NONE unless CHEST/SWTCH/PCKUP
  u8 mask;
  u32 address; // For stage flags, the saved copy's byte
  u16 name;
  u8 special; // TRK_NONE unless SPECL
  u8 flags;
} TrkLocation;

typedef struct {
  u8 id; // 1-49: sea square, 50+: list-page group
  u8 kind;
  u16 first_location;
  u16 num_locations;
  u16 name;
} TrkGroup;

typedef struct {
  u8 island_number; // 0 when nested in another exit
  u8 parent_group; // Group of the exit it's nested in, or TRK_NONE
  u8 exit_group;
  u8 category;
  u16 entrance_name;
  u16 exit_name;
} TrkEntrance;

typedef struct {
  char stage_name[8]; // Not NUL-terminated when 8 characters long
  u8 room; // TRK_NONE matches any room
  u8 spawn; // TRK_NONE matches any spawn
  u8 entrance_index;
} TrkTrigger;

typedef struct {
  u8 destination_square;
  u8 vanilla_square;
  u8 chart_number;
  u8 item_id;
  u8 owned_offset; // From TRK_GET_MAP_ADDR
  u8 owned_mask;
  u8 salvaged_offset; // From TRK_COMPLETE_MAP_ADDR
  u8 salvaged_mask;
  u16 name;
} TrkChart;

typedef struct {
  char stage_name[8]; // Not NUL-terminated when 8 characters long
  u8 group_id;
} TrkStage;

// tracker/dungeons.py DungeonFlag.
enum TrkDungeonFlag {
  TRK_DUNGEON_HAS_BIG_KEY = 0x01,
  TRK_DUNGEON_START_WITH_SMALL_KEYS = 0x02,
  TRK_DUNGEON_START_WITH_BIG_KEY = 0x04,
};

typedef struct {
  u8 group_id;
  u8 counter; // Small-keys-obtained counter (enum TrkDungeon)
  u8 stage_id;
  u8 small_keys; // Number of small keys in the dungeon
  u8 flags; // enum TrkDungeonFlag
} TrkDungeonInfo;

#define TRK_GET_MAP_ADDR 0x803C4CDC
#define TRK_COMPLETE_MAP_ADDR 0x803C4CFC

bool trk_tables_valid(void);
u16 trk_seed_tag(void);
u16 trk_table_flags(void);
u16 trk_count(int section);
const u8* trk_section(int section);
const char* trk_string(u16 offset);
void trk_get_location(u16 index, TrkLocation* out);
void trk_get_group(u16 index, TrkGroup* out);
int trk_find_group(u8 group_id);
void trk_get_entrance(u16 index, TrkEntrance* out);
void trk_get_trigger(u16 index, TrkTrigger* out);
void trk_get_chart(u16 index, TrkChart* out);
void trk_get_stage(u16 index, TrkStage* out);
int trk_find_dungeon(u8 group_id, TrkDungeonInfo* out);

#endif
