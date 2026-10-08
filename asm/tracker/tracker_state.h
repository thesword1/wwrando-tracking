// The tracker's runtime state: not saved, rebuilt every frame. It lives in the tracker_state reserve
// (asm/patches/tracker.asm) and doubles as a debug view of the tracker for Dolphin tests, which read
// it from RAM (test/test_tracker_dolphin.py), so keep the layout in sync with TRACKER_STATE_FORMAT
// there.

#ifndef TRACKER_STATE_H
#define TRACKER_STATE_H

#include "tracker_types.h"

#define TRK_STATE_MAGIC 0x54524B53 // "TRKS"
#define TRK_MAX_GROUPS 128

typedef struct {
  u32 magic; // 0x00: TRK_STATE_MAGIC once the per-frame update has run
  u32 frame_count; // 0x04: frames the per-frame update has run
  u16 num_locations; // 0x08
  u16 num_checked; // 0x0A: auto-detected or manually marked
  u16 num_auto_checked; // 0x0C
  u16 save_resets; // 0x0E: times the save region was reset
  u8 in_game; // 0x10
  s8 room; // 0x11: current stage's room and spawn when the update last ran
  s16 spawn; // 0x12
  char stage_name[8]; // 0x14
  u8 last_visited_entrance; // 0x1C: last entrance whose visited bit was set, 0xFF for none
  u8 num_groups; // 0x1D
  u8 pad[2]; // 0x1E
  u8 group_checked[TRK_MAX_GROUPS]; // 0x20: checked locations per group (by group index)
} TrkState;

#ifdef TRACKER_HOST
extern TrkState trk_host_state;
#define TRK_STATE (&trk_host_state)
#else
extern u8 tracker_state[];
#define TRK_STATE ((TrkState*)tracker_state)
#endif

#endif
