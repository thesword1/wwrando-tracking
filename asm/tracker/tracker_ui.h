// The tracker's sea chart UI (asm/tracker/tracker_ui.c): counters on the chart, and the hooks into
// dMenu_Fmap_c that drive them. The dungeon map and Quest Status screens show its pages too
// (asm/tracker/tracker_ui_menu.c).

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
  TRK_VIEW_SQUARE = 2, // ZoomGridLv1Proc: one square zoomed in
};

// Buttons pressed this frame, as passed to the input functions (not the game's bit layout).
enum TrkUiButton {
  TRK_BTN_X = 1 << 0,
  TRK_BTN_Z = 1 << 1,
  TRK_BTN_A = 1 << 2,
  TRK_BTN_B = 1 << 3,
};

// Tracker pages shown over the sea chart, dungeon map or Quest Status screen (opened with Z).
enum TrkUiPage {
  TRK_PAGE_NONE = 0,
  TRK_PAGE_GROUPS = 1, // The list page: groups that aren't on a sea square
  TRK_PAGE_GROUP = 2, // A group's location list: from the list page, or the current group's (dungeon map, Quest Status)
};

// Menus the UI is shown on (TrkUiState.menu).
enum TrkUiMenu {
  TRK_MENU_NONE = 0,
  TRK_MENU_FMAP = 1, // Sea chart (tracker_ui.c)
  TRK_MENU_DMAP = 2, // Dungeon map (tracker_ui_menu.c)
  TRK_MENU_COLLECT = 3, // Quest Status (tracker_ui_menu.c)
};

// Main stick deflection (PADStatus stickY, about -72..72) that counts as up/down, and the auto-repeat
// delays in frames.
#define TRK_UI_STICK_THRESHOLD 40
#define TRK_UI_REPEAT_DELAY 14
#define TRK_UI_REPEAT_RATE 4
// Rows of a list that fit on screen. A location list's info lines take some of them.
#define TRK_UI_LIST_ROWS 15
// Frames a refused toggle is shown.
#define TRK_UI_FLASH_FRAMES 20

#define TRK_UI_NO_GROUP 0xFF

// Info lines under a location list: where a square's (or a cave's/dungeon's) randomized entrances
// lead, once visited, and which chart leads to a square's sunken treasure, once owned.
enum TrkUiInfoKind {
  TRK_INFO_ENTRANCE = 0, // index: entrance index
  TRK_INFO_CHART = 1, // index: chart index (destination square - 1)
};
typedef struct {
  u8 kind;
  u8 revealed; // Visited (entrance) / owned (chart)
  u16 index;
} TrkUiInfo;
#define TRK_UI_MAX_INFO 4

// UI state, in the tracker_ui_state reserve (asm/patches/tracker.asm). Not saved. The Dolphin tests
// read it from RAM (test/test_tracker_ui_dolphin.py).
typedef struct {
  u32 proc_frame; // 0x00: TrkState frame_count when the chart's input handler last ran
  u32 draw_frame; // 0x04: TrkState frame_count when the tracker last drew on the chart
  u8 view; // 0x08: enum TrkUiView, from the input handler
  u8 list_group; // 0x09: group index of the location list shown, TRK_UI_NO_GROUP for none
  u8 sel; // 0x0A: selected row of the location list
  u8 scroll; // 0x0B: first row shown
  s8 stick_dir; // 0x0C: -1 up, 1 down, 0 neutral, last frame
  u8 stick_timer; // 0x0D: frames until the stick repeats
  u8 flash_timer; // 0x0E: frames left of the "can't unmark" flash on the selected row
  u8 last_toggle; // 0x0F: 1 = marked, 2 = unmarked, 3 = refused (auto-checked), for tests
  u8 page; // 0x10: enum TrkUiPage
  u8 page_sel; // 0x11: selected row of the list page
  u8 page_scroll; // 0x12: first row of the list page shown
  u8 page_group; // 0x13: group index of the location list shown on TRK_PAGE_GROUP
  u32 collect_draw_frame; // 0x14: TrkState frame_count when the Triforce counter was last drawn (tracker_collect.c)
  u8 menu; // 0x18: enum TrkUiMenu whose input handler last ran
  u8 pad[0x27]; // 0x19
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
u8 tracker_ui_location_status(u16 location_index);
void tracker_ui_list_input(u8 group_index, u16 buttons, s8 stick_y);
int tracker_ui_page_group(u16 n, u16* count);
int tracker_ui_group_entrance(u8 group_index);
u16 tracker_ui_info_lines(u8 group_index, TrkUiInfo* out);
bool tracker_ui_input(u8 view, int square_group, u16 buttons, s8 stick_y);
int tracker_ui_stage_group(void);
bool tracker_ui_menu_input(int stage_group, u16 buttons, s8 stick_y);
u8 tracker_triforce_count(void);
void tracker_triforce_text(char* out);

#ifdef TRACKER_HOST
extern TrkUiState trk_host_ui_state;
#define TRK_UI_STATE (&trk_host_ui_state)
#else
extern u8 tracker_ui_state[];
#define TRK_UI_STATE ((TrkUiState*)tracker_ui_state)
#endif

#endif
