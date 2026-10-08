// The tracker's sea chart UI (asm/tracker/tracker_ui.c): counters on the chart, and the hooks into
// dMenu_Fmap_c that drive them.

#ifndef TRACKER_UI_H
#define TRACKER_UI_H

#include "tracker_types.h"

// Colour state of a counter or a location, like the website tracker.
enum TrkUiStatus {
  TRK_UI_NONE = 0, // Nothing tracked here: draw nothing
  TRK_UI_DONE = 1, // Everything checked
  TRK_UI_IN_LOGIC = 2, // Some (counter) / this (location) unchecked location is in logic
  TRK_UI_OUT_OF_LOGIC = 3, // Unchecked, and nothing in logic
  TRK_UI_UNKNOWN = 4, // Unchecked, logic not available
};

// Sea chart views the UI draws on (dMenu_Fmap_c::mFmapProcIdx).
enum TrkUiView {
  TRK_VIEW_NONE = 0,
  TRK_VIEW_WORLD = 1, // SelectGrid: the whole chart
};

// UI state, in the tracker_ui_state reserve (asm/patches/tracker.asm). Not saved. The Dolphin tests
// read it from RAM (test/test_tracker_ui_dolphin.py).
typedef struct {
  u32 proc_frame; // 0x00: TrkState frame_count when the chart's input handler last ran
  u32 draw_frame; // 0x04: TrkState frame_count when the tracker last drew on the chart
  u8 view; // 0x08: enum TrkUiView, from the input handler
  u8 pad[0x37]; // 0x09
} TrkUiState;

#define TRK_UI_COUNTER_UNKNOWN 0xFF

// Remaining and in-logic counts of a group, and its colour state. available is
// TRK_UI_COUNTER_UNKNOWN while logic isn't available.
typedef struct {
  u8 remaining;
  u8 available;
  u8 status;
} TrkUiCounter;

void tracker_ui_group_counter(u16 group_index, TrkUiCounter* out);

#ifdef TRACKER_HOST
extern TrkUiState trk_host_ui_state;
#define TRK_UI_STATE (&trk_host_ui_state)
#else
extern u8 tracker_ui_state[];
#define TRK_UI_STATE ((TrkUiState*)tracker_ui_state)
#endif

#endif
