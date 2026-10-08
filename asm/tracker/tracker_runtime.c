// Game hooks (asm/patches/tracker.asm, tweaks.add_in_game_tracker) and the per-frame update.

#include "tracker_detect.h"
#include "tracker_mem.h"
#include "tracker_save.h"
#include "tracker_state.h"
#include "tracker_tables.h"

#define TRK_CURRENT_STAGE_NAME_ADDR 0x803C9D3C
#define TRK_CURRENT_SPAWN_ADDR 0x803C9D44
#define TRK_CURRENT_ROOM_ADDR 0x803C9D46

// Same as TWWClient.py's check_ingame: not on the title screen or file select.
TRK_EXPORT bool tracker_is_in_game(void) {
  char first = (char)trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR);
  if (first == '\0') {
    return false;
  }
  static const char* const not_in_game[] = {"sea_T", "Name"};
  for (u32 i = 0; i < sizeof(not_in_game)/sizeof(not_in_game[0]); i++) {
    const char* name = not_in_game[i];
    u32 j = 0;
    while (name[j] != '\0' && (char)trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR + j) == name[j]) {
      j++;
    }
    if (name[j] == '\0' && trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR + j) == 0) {
      return false;
    }
  }
  return true;
}

static bool trk_trigger_matches(const TrkTrigger* trigger, s8 room, s16 spawn) {
  for (u32 i = 0; i < 8; i++) {
    char c = (char)trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR + i);
    if (c != trigger->stage_name[i]) {
      return false;
    }
    if (c == '\0') {
      break;
    }
  }
  if (trigger->room != TRK_NONE && trigger->room != (u8)room) {
    return false;
  }
  if (trigger->spawn != TRK_NONE && trigger->spawn != spawn) {
    return false;
  }
  return true;
}

// Sets the visited bit of every entrance whose exit's stage (and room/spawn, for the Cliff Plateau
// Isles inner cave) is the current one. Runs every frame rather than on stage changes, so a visit is
// recorded again if a save without it is reloaded in the same place.
TRK_EXPORT void tracker_check_stage(void) {
  TrkState* state = TRK_STATE;
  s8 room = (s8)trk_mem_u8(TRK_CURRENT_ROOM_ADDR);
  s16 spawn = (s16)trk_mem_u16(TRK_CURRENT_SPAWN_ADDR);
  for (u32 i = 0; i < 8; i++) {
    state->stage_name[i] = (char)trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR + i);
  }
  state->room = room;
  state->spawn = spawn;

  u16 num_triggers = trk_count(TRK_SEC_TRIGGERS);
  for (u16 i = 0; i < num_triggers; i++) {
    TrkTrigger trigger;
    trk_get_trigger(i, &trigger);
    if (trk_trigger_matches(&trigger, room, spawn) && !tracker_is_entrance_visited(trigger.entrance_index)) {
      trk_save_set_entrance_visited(trigger.entrance_index);
      state->last_visited_entrance = trigger.entrance_index;
    }
  }
}

TRK_EXPORT void tracker_update_counts(void) {
  TrkState* state = TRK_STATE;
  u16 num_groups = trk_count(TRK_SEC_GROUPS);
  u16 num_checked = 0;
  u16 num_auto_checked = 0;
  for (u16 group_index = 0; group_index < num_groups && group_index < TRK_MAX_GROUPS; group_index++) {
    TrkGroup group;
    trk_get_group(group_index, &group);
    u8 group_checked = 0;
    for (u16 i = 0; i < group.num_locations; i++) {
      u16 location_index = group.first_location + i;
      if (tracker_is_auto_checked(location_index)) {
        num_auto_checked++;
        group_checked++;
      } else if (tracker_is_manual(location_index)) {
        group_checked++;
      }
    }
    state->group_checked[group_index] = group_checked;
    num_checked += group_checked;
  }
  state->num_locations = trk_count(TRK_SEC_LOCATIONS);
  state->num_groups = (u8)num_groups;
  state->num_checked = num_checked;
  state->num_auto_checked = num_auto_checked;
}

TRK_EXPORT void tracker_frame(void) {
  if (!trk_tables_valid()) {
    return;
  }
  TrkState* state = TRK_STATE;
  if (state->magic != TRK_STATE_MAGIC) {
    state->magic = TRK_STATE_MAGIC;
    state->last_visited_entrance = TRK_NONE;
  }
  state->frame_count++;
  state->in_game = tracker_is_in_game();
  if (!state->in_game) {
    return;
  }
  trk_save_validate();
  tracker_check_stage();
  tracker_update_counts();
}

#ifndef TRACKER_HOST

void dKy_itudemo_se__Fv(void);
void init_save_with_tweaks(void* save);
void drc_small_key_item_get_func(void);
void fw_small_key_item_get_func(void);
void totg_small_key_item_get_func(void);
void et_small_key_item_get_func(void);
void wt_small_key_item_get_func(void);

// Replaces the call to dKy_itudemo_se in dScnPly_Execute, which runs every frame of gameplay
// (including while a menu is open).
void tracker_on_frame(void) {
  dKy_itudemo_se__Fv();
  tracker_frame();
}

// Replaces the call to init_save_with_tweaks in dSv_info_c::init (new game). Vanilla doesn't clear
// the reserve area on a new game. Reset it before the starting items are given, so starting small
// keys are counted.
void tracker_init_save(void* save) {
  if (trk_tables_valid()) {
    trk_save_reset();
  }
  init_save_with_tweaks(save);
}

// Item get functions of the dungeon small keys (item_func_ptr entries set by
// tweaks.add_in_game_tracker). These cover keys picked up in the world and keys delivered by
// Archipelago, which both go through execItemGet.
void tracker_drc_small_key_item_get_func(void) {
  tracker_count_small_key(TRK_DUNGEON_DRC);
  drc_small_key_item_get_func();
}

void tracker_fw_small_key_item_get_func(void) {
  tracker_count_small_key(TRK_DUNGEON_FW);
  fw_small_key_item_get_func();
}

void tracker_totg_small_key_item_get_func(void) {
  tracker_count_small_key(TRK_DUNGEON_TOTG);
  totg_small_key_item_get_func();
}

void tracker_et_small_key_item_get_func(void) {
  tracker_count_small_key(TRK_DUNGEON_ET);
  et_small_key_item_get_func();
}

void tracker_wt_small_key_item_get_func(void) {
  tracker_count_small_key(TRK_DUNGEON_WT);
  wt_small_key_item_get_func();
}

#endif
