// The tracker's runtime state: not saved, rebuilt every frame. It lives in the tracker_state reserve
// (asm/patches/tracker.asm) and doubles as a debug view of the tracker for Dolphin tests, which read
// it from RAM (test/test_tracker_dolphin.py), so keep the layout in sync with TRACKER_STATE_FORMAT
// there.

#ifndef TRACKER_STATE_H
#define TRACKER_STATE_H

#include "tracker_types.h"

#define TRK_STATE_MAGIC 0x54524B53 // "TRKS"
#define TRK_MAX_GROUPS 128
#define TRK_STATE_MAX_LOCATIONS 384

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
  // Logic (asm/tracker/tracker_logic.c).
  u32 logic_evals; // 0xA0: number of logic evaluations
  u32 logic_ticks; // 0xA4: time base ticks the last evaluation took (40.5 MHz)
  u32 logic_max_ticks; // 0xA8: longest evaluation
  u16 num_in_logic; // 0xAC: unchecked locations in logic
  u8 logic_status; // 0xAE: enum TrkLogicStatus
  u8 logic_delay; // 0xAF: frames until a requested evaluation runs, 0 = none requested
  u16 logic_seen_checked; // 0xB0: num_checked at the last evaluation
  u16 logic_seen_resets; // 0xB2: save_resets at the last evaluation
  u8 logic_seen_visited[8]; // 0xB4: visited-entrance bits at the last evaluation
  u8 in_logic[TRK_STATE_MAX_LOCATIONS/8]; // 0xBC: bit i = location i is in logic
  u8 group_available[TRK_MAX_GROUPS]; // 0xEC: unchecked locations in logic per group
  u8 goal_in_logic; // 0x16C: 1 if the seed's goal (defeating Ganondorf) is in logic ("GO MODE")
  u8 pad2[3]; // 0x16D
} TrkState; // 0x170

#ifdef TRACKER_HOST
extern TrkState trk_host_state;
#define TRK_STATE (&trk_host_state)
#else
extern u8 tracker_state[];
#define TRK_STATE ((TrkState*)tracker_state)
#endif

#endif
