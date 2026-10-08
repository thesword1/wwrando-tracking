// The tracker's sea chart UI. dMenu_Fmap_c (the sea chart menu, docs/dev/memory-map.md section 4) is
// hooked twice (asm/patches/tracker.asm):
// - tracker_fmap_proc replaces FmapProc in the chart's main proc table. It runs once per frame while
//   the normal sea chart is open and idle (not during the open/close animations, the compare page,
//   or warp mode) and records which view is shown.
// - tracker_fmap_draw replaces dDlst_FMAP_c::draw in its vtable. It draws the chart, then the
//   tracker on top of it, but only while the input handler ran recently, so nothing is drawn in
//   the views the tracker doesn't handle.

#include "tracker_detect.h"
#include "tracker_logic.h"
#include "tracker_mem.h"
#include "tracker_save.h"
#include "tracker_state.h"
#include "tracker_tables.h"
#include "tracker_ui.h"

#define TRK_SQUARES 49

// Whether a location is in logic (unknown if the logic isn't available).
TRK_INLINE u8 trk_ui_location_logic(u16 location_index) {
  if (!tracker_logic_available()) {
    return TRK_UI_UNKNOWN;
  }
  return tracker_is_in_logic(location_index) ? TRK_UI_IN_LOGIC : TRK_UI_OUT_OF_LOGIC;
}

TRK_EXPORT void tracker_ui_group_counter(u16 group_index, TrkUiCounter* out) {
  TrkGroup group;
  trk_get_group(group_index, &group);
  out->remaining = 0;
  out->available = TRK_UI_COUNTER_UNKNOWN;
  out->status = TRK_UI_NONE;
  if (group.num_locations == 0) {
    return;
  }
  u8 checked = group_index < TRK_MAX_GROUPS ? TRK_STATE->group_checked[group_index] : 0;
  out->remaining = (u8)(group.num_locations - checked);
  if (out->remaining == 0) {
    out->status = TRK_UI_DONE;
    return;
  }
  u8 available = 0;
  bool known = true;
  for (u16 i = 0; i < group.num_locations; i++) {
    u16 location_index = group.first_location + i;
    if (tracker_is_checked(location_index)) {
      continue;
    }
    u8 logic = trk_ui_location_logic(location_index);
    if (logic == TRK_UI_UNKNOWN) {
      known = false;
    } else if (logic == TRK_UI_IN_LOGIC) {
      available++;
    }
  }
  if (!known) {
    out->status = TRK_UI_UNKNOWN;
    return;
  }
  out->available = available;
  out->status = available > 0 ? TRK_UI_IN_LOGIC : TRK_UI_OUT_OF_LOGIC;
}

TRK_EXPORT u8 tracker_ui_location_status(u16 location_index) {
  if (tracker_is_checked(location_index)) {
    return TRK_UI_DONE;
  }
  return trk_ui_location_logic(location_index);
}

// Moves a list selection and scrolls the list so it stays visible.
static void trk_ui_move_selection(u8* sel, u8* scroll, int delta, u16 count, bool wrap, u8 rows) {
  int new_sel = *sel + delta;
  if (new_sel < 0) {
    new_sel = wrap ? count - 1 : 0;
  } else if (new_sel >= count) {
    new_sel = wrap ? 0 : count - 1;
  }
  *sel = (u8)new_sel;
  if (*sel < *scroll) {
    *scroll = *sel;
  } else if (*sel >= *scroll + rows) {
    *scroll = (u8)(*sel - rows + 1);
  }
}

// Main stick up/down for a list: moves on a fresh push (wrapping around), then auto-repeats while
// held (stopping at the ends). Returns whether the selection moved.
static bool trk_ui_stick_select(TrkUiState* ui, s8 stick_y, u8* sel, u8* scroll, u16 count, u8 rows) {
  s8 dir = 0;
  if (stick_y > TRK_UI_STICK_THRESHOLD) {
    dir = -1;
  } else if (stick_y < -TRK_UI_STICK_THRESHOLD) {
    dir = 1;
  }
  bool moved = false;
  if (dir != 0 && dir != ui->stick_dir) {
    trk_ui_move_selection(sel, scroll, dir, count, true, rows);
    ui->stick_timer = TRK_UI_REPEAT_DELAY;
    moved = true;
  } else if (dir != 0 && --ui->stick_timer == 0) {
    trk_ui_move_selection(sel, scroll, dir, count, false, rows);
    ui->stick_timer = TRK_UI_REPEAT_RATE;
    moved = true;
  }
  ui->stick_dir = dir;
  return moved;
}

// Input for a group's location list: the main stick moves the selection and X toggles the selected
// location's manual mark.
TRK_EXPORT void tracker_ui_list_input(u8 group_index, u16 buttons, s8 stick_y) {
  TrkUiState* ui = TRK_UI_STATE;
  if (ui->list_group != group_index) {
    ui->list_group = group_index;
    ui->sel = 0;
    ui->scroll = 0;
    ui->flash_timer = 0;
  }
  TrkGroup group;
  trk_get_group(group_index, &group);
  if (group.num_locations == 0) {
    return;
  }
  if (ui->flash_timer > 0) {
    ui->flash_timer--;
  }
  u8 rows = (u8)(TRK_UI_LIST_ROWS - tracker_ui_info_lines(group_index, NULL));
  if (trk_ui_stick_select(ui, stick_y, &ui->sel, &ui->scroll, group.num_locations, rows)) {
    ui->flash_timer = 0;
  }

  if (buttons & TRK_BTN_X) {
    u16 location_index = group.first_location + ui->sel;
    if (tracker_toggle_manual(location_index)) {
      ui->last_toggle = tracker_is_manual(location_index) ? 1 : 2;
      tracker_update_counts();
    } else {
      ui->last_toggle = 3;
      ui->flash_timer = TRK_UI_FLASH_FRAMES;
    }
  }
}

// The groups on the list page: every group that isn't a sea square and has tracked locations, in
// table order (dungeons, other zones, then caves). Returns the group index of the nth one, or -1.
// Its count is returned through count if not NULL.
TRK_EXPORT int tracker_ui_page_group(u16 n, u16* count) {
  u16 num_groups = trk_count(TRK_SEC_GROUPS);
  u16 found = 0;
  int result = -1;
  for (u16 i = 0; i < num_groups && i < TRK_UI_NO_GROUP; i++) {
    TrkGroup group;
    trk_get_group(i, &group);
    if (group.id <= TRK_SQUARES || group.num_locations == 0) {
      continue;
    }
    if (found == n) {
      result = i;
    }
    found++;
  }
  if (count != NULL) {
    *count = found;
  }
  return result;
}

static bool trk_streq(const char* a, const char* b) {
  while (*a != '\0' && *a == *b) {
    a++;
    b++;
  }
  return *a == *b;
}

// The tracked entrance that leads to a group in this seed, or -1 if its entrances aren't randomized.
// Prefers the entrance into the group's own exit (a dungeon's entrance rather than a boss door that
// leads into the dungeon's boss arena).
TRK_EXPORT int tracker_ui_group_entrance(u8 group_index) {
  TrkGroup group;
  trk_get_group(group_index, &group);
  u16 num_entrances = trk_count(TRK_SEC_ENTRANCES);
  int result = -1;
  for (u16 i = 0; i < num_entrances; i++) {
    TrkEntrance entrance;
    trk_get_entrance(i, &entrance);
    if (entrance.exit_group != group.id) {
      continue;
    }
    if (trk_streq(trk_string(entrance.exit_name), trk_string(group.name))) {
      return i;
    }
    if (result < 0) {
      result = i;
    }
  }
  return result;
}

// The info lines of a group's location list (see TrkUiInfo), up to TRK_UI_MAX_INFO. Writes them to
// out unless it's NULL and returns how many there are.
// - Tracked entrances on the square's island, or nested in the group (a dungeon's boss door, an
//   inner cave's entrance in its cave).
// - For a square with a tracked sunken treasure, the chart that leads there.
TRK_EXPORT u16 tracker_ui_info_lines(u8 group_index, TrkUiInfo* out) {
  TrkGroup group;
  trk_get_group(group_index, &group);
  bool is_square = group.id >= 1 && group.id <= TRK_SQUARES;
  u16 count = 0;
  u16 num_entrances = trk_count(TRK_SEC_ENTRANCES);
  for (u16 i = 0; i < num_entrances && count < TRK_UI_MAX_INFO; i++) {
    TrkEntrance entrance;
    trk_get_entrance(i, &entrance);
    bool here = is_square ? entrance.island_number == group.id : entrance.parent_group == group.id;
    if (!here) {
      continue;
    }
    if (out != NULL) {
      out[count].kind = TRK_INFO_ENTRANCE;
      out[count].revealed = tracker_is_entrance_visited(i);
      out[count].index = i;
    }
    count++;
  }
  if (is_square && count < TRK_UI_MAX_INFO && group.id <= trk_count(TRK_SEC_CHARTS)) {
    bool has_treasure = false;
    for (u16 i = 0; i < group.num_locations; i++) {
      TrkLocation loc;
      trk_get_location(group.first_location + i, &loc);
      if (loc.type == TRK_TYPE_CHART) {
        has_treasure = true;
      }
    }
    TrkChart chart;
    trk_get_chart(group.id - 1, &chart);
    if (has_treasure && chart.destination_square == group.id) {
      if (out != NULL) {
        out[count].kind = TRK_INFO_CHART;
        out[count].revealed = (trk_mem_u8(TRK_GET_MAP_ADDR + chart.owned_offset) & chart.owned_mask) != 0;
        out[count].index = group.id - 1;
      }
      count++;
    }
  }
  return count;
}

// Opens the list page if it has any groups.
static bool trk_ui_open_page(TrkUiState* ui) {
  u16 count;
  tracker_ui_page_group(0, &count);
  if (count == 0) {
    return false;
  }
  ui->page = TRK_PAGE_GROUPS;
  if (ui->page_sel >= count) {
    ui->page_sel = 0;
    ui->page_scroll = 0;
  }
  return true;
}

// Input while a page is shown:
// - List page (groups): the stick selects, A opens the group's location list, B or Z closes the page.
// - A group's location list: the stick and X as in square view, B goes back to the groups, Z closes.
static void trk_ui_page_input(TrkUiState* ui, u16 buttons, s8 stick_y) {
  if (buttons & TRK_BTN_Z) {
    ui->page = TRK_PAGE_NONE;
    return;
  }
  if (ui->page == TRK_PAGE_GROUPS) {
    u16 count;
    tracker_ui_page_group(0, &count);
    trk_ui_stick_select(ui, stick_y, &ui->page_sel, &ui->page_scroll, count, TRK_UI_LIST_ROWS);
    if (buttons & TRK_BTN_A) {
      int group_index = tracker_ui_page_group(ui->page_sel, NULL);
      if (group_index >= 0) {
        ui->page = TRK_PAGE_GROUP;
        ui->page_group = (u8)group_index;
        ui->stick_dir = 0;
      }
    } else if (buttons & TRK_BTN_B) {
      ui->page = TRK_PAGE_NONE;
    }
  } else {
    if (buttons & TRK_BTN_B) {
      ui->stick_dir = 0;
      if (!trk_ui_open_page(ui)) {
        ui->page = TRK_PAGE_NONE;
      }
    } else {
      tracker_ui_list_input(ui->page_group, buttons, stick_y);
    }
  }
}

// All input while the normal sea chart is idle. view is the chart's view (enum TrkUiView) and
// square_group the group of the square shown in square view (-1 for none). Returns whether the
// tracker consumed the input, in which case the chart's own input handler must not run.
//
// - World or square view: Z opens the list page. In square view, the stick and X work on the
//   square's location list (tracker_ui_list_input); vanilla doesn't read them there.
// - A page: trk_ui_page_input.
TRK_EXPORT bool tracker_ui_input(u8 view, int square_group, u16 buttons, s8 stick_y) {
  TrkUiState* ui = TRK_UI_STATE;
  if (ui->page == TRK_PAGE_NONE) {
    if ((buttons & TRK_BTN_Z) && (view == TRK_VIEW_WORLD || view == TRK_VIEW_SQUARE) && trk_ui_open_page(ui)) {
      return true;
    }
    if (view == TRK_VIEW_SQUARE && square_group >= 0) {
      tracker_ui_list_input((u8)square_group, buttons, stick_y);
    }
    return false;
  }
  trk_ui_page_input(ui, buttons, stick_y);
  return true;
}

// Whether name (8 characters, NUL-padded) is the current stage's name.
static bool trk_is_current_stage(const char* name) {
  for (u32 i = 0; i < 8; i++) {
    char c = (char)trk_mem_u8(TRK_CURRENT_STAGE_NAME_ADDR + i);
    if (c != name[i]) {
      return false;
    }
    if (c == '\0') {
      break;
    }
  }
  return true;
}

// The group the player is in, from the current stage's name and the STAGES table (tracker/stages.py), or -1 if the
// stage isn't one group or the group has nothing to show.
TRK_EXPORT int tracker_ui_stage_group(void) {
  u16 count = trk_count(TRK_SEC_STAGES);
  for (u16 i = 0; i < count; i++) {
    TrkStage stage;
    trk_get_stage(i, &stage);
    if (!trk_is_current_stage(stage.stage_name)) {
      continue;
    }
    int group_index = trk_find_group(stage.group_id);
    if (group_index < 0 || group_index >= TRK_UI_NO_GROUP) {
      return -1;
    }
    TrkGroup group;
    trk_get_group(group_index, &group);
    return group.num_locations > 0 || tracker_ui_info_lines((u8)group_index, NULL) > 0 ? group_index : -1;
  }
  return -1;
}

// Z on the dungeon map or the Quest Status screen (tracker_ui_menu.c): opens the location list of the group the
// player is in (stage_group, from tracker_ui_stage_group), or the list page if there's none. B on that list goes to
// the list page, with the group selected if it's there. Once a page is shown, the input is the same as on the sea
// chart (trk_ui_page_input). Returns whether a page is shown.
TRK_EXPORT bool tracker_ui_menu_input(int stage_group, u16 buttons, s8 stick_y) {
  TrkUiState* ui = TRK_UI_STATE;
  if (ui->page != TRK_PAGE_NONE) {
    trk_ui_page_input(ui, buttons, stick_y);
  } else if (buttons & TRK_BTN_Z) {
    if (stage_group >= 0) {
      ui->page = TRK_PAGE_GROUP;
      ui->page_group = (u8)stage_group;
      ui->stick_dir = 0;
      u16 count;
      tracker_ui_page_group(0, &count);
      for (u16 n = 0; n < count; n++) {
        if (tracker_ui_page_group(n, NULL) == stage_group) {
          ui->page_sel = (u8)n;
          ui->page_scroll = n >= TRK_UI_LIST_ROWS ? (u8)(n - TRK_UI_LIST_ROWS + 1) : 0;
        }
      }
    } else {
      trk_ui_open_page(ui);
    }
  }
  return ui->page != TRK_PAGE_NONE;
}

#ifndef TRACKER_HOST

typedef struct { u8 r, g, b, a; } TrkColor; // JUtility::TColor
typedef struct JUTFont JUTFont;
typedef struct J2DOrthoGraph J2DOrthoGraph;
typedef struct { u8 offset, width; } TrkFontWidth; // JUTFont::TWidth

void setCharColor__7JUTFontFQ28JUtility6TColor(JUTFont* font, TrkColor color);
float drawString_size_scale__7JUTFontFffffPCcUlb(JUTFont* font, float x, float y, float w, float h, const char* str, u32 len, bool visible);
void J2DFillBox__FffffQ28JUtility6TColor(float x, float y, float w, float h, TrkColor color);
void setPort__13J2DOrthoGraphFv(J2DOrthoGraph* port);
void draw__12dDlst_FMAP_cFv(void* dlst);
void FmapProc__12dMenu_Fmap_cFv(void* fmap);

#define TRK_CURRENT_GRAF_PORT_ADDR 0x803CA908

// dMenu_Fmap_c members (zeldaret/tww include/d/d_menu_fmap.h).
#define TRK_FMAP_DLST_OFFSET 0x1C // dDlst_FMAP_c fmapDl
#define TRK_FMAP_FONT_OFFSET 0x50D0 // JUTFont* mFont (the message font)
#define TRK_FMAP_PROC_IDX_OFFSET 0x5114 // u8 mFmapProcIdx: index into fmapProcMain
#define TRK_FMAP_SV_OFFSET 0x2878 // dMenu_FmapSv_c* fmapSv
#define TRK_FMAP_SV_CUR_X 0x4 // s8 curX, -3..3
#define TRK_FMAP_SV_CUR_Y 0x5 // s8 curY, -3..3
#define TRK_FMAP_PROC_SELECT_GRID 0
#define TRK_FMAP_PROC_ZOOM_LV1 2 // ZoomGridLv1Proc: square view

// Controller 1 (docs/dev/memory-map.md section 4.2).
#define TRK_PAD_TRIG_ADDR 0x803A4E22 // g_mDoCPd_cpadInfo[0].mButtonTrig
#define TRK_PAD_TRIG_A 0x0100 // As a big-endian u16
#define TRK_PAD_TRIG_Z 0x0800
#define TRK_PAD_TRIG_B 0x0080
#define TRK_PAD_TRIG_X 0x0040
#define TRK_PAD_STICK_Y_ADDR 0x803ED81B // JUTGamePad::mPadStatus[0].stickY

// Layout, in the 640x480 screen space of the chart's ortho port. Measured on screenshots.
#define TRK_GRID_X 42.0f // Top left corner of square 1
#define TRK_GRID_Y 19.5f
#define TRK_CELL_W 56.0f
#define TRK_CELL_H 56.5f
#define TRK_COUNTER_SIZE 16.0f
#define TRK_TOTALS_X 466.0f // In the empty strip of the salvage panel
#define TRK_TOTALS_Y 262.0f
#define TRK_TOTALS_SIZE 16.0f
#define TRK_COUNTER_PAD 2.0f
// Location list over the zoomed square. The dungeon map and Quest Status screens show the same panel at another
// position (tracker_ui_menu.c).
#define TRK_PANEL_X 48.0f
#define TRK_PANEL_Y 26.0f
#define TRK_PANEL_W 380.0f
#define TRK_PANEL_H 382.0f
#define TRK_TITLE_SIZE 18.0f
#define TRK_ROWS_OFFSET 28.0f // Top of the first row, from the top of the panel
#define TRK_ROW_H 21.0f
#define TRK_ROW_SIZE 16.0f
#define TRK_HINT_SIZE 14.0f

static const TrkColor trk_status_colors[] = {
  [TRK_UI_NONE] = {0x00, 0x00, 0x00, 0x00},
  [TRK_UI_DONE] = {0x80, 0x80, 0x80, 0xFF},
  [TRK_UI_IN_LOGIC] = {0x29, 0x29, 0xCC, 0xFF},
  [TRK_UI_OUT_OF_LOGIC] = {0xCC, 0x29, 0x29, 0xFF},
  [TRK_UI_UNKNOWN] = {0x30, 0x20, 0x10, 0xFF},
};
static const TrkColor trk_box_color = {0xFF, 0xF8, 0xE0, 0xD0};
static const TrkColor trk_panel_color = {0xFF, 0xF8, 0xE0, 0xE8};
static const TrkColor trk_select_color = {0xE8, 0xCC, 0x8C, 0xFF};
static const TrkColor trk_flash_color = {0xF0, 0x98, 0x80, 0xFF};
static const TrkColor trk_text_color = {0x30, 0x20, 0x10, 0xFF};
static const TrkColor trk_hint_color = {0x70, 0x58, 0x40, 0xFF};

TRK_INLINE void trk_font_set_gx(JUTFont* font) {
  void (*set_gx)(JUTFont*) = (*(void (***)(JUTFont*))font)[0x0C/4];
  set_gx(font);
}

TRK_INLINE int trk_font_cell_width(JUTFont* font) {
  int (*get_cell_width)(JUTFont*) = (*(int (***)(JUTFont*))font)[0x30/4];
  return get_cell_width(font);
}

TRK_INLINE void trk_font_width_entry(JUTFont* font, int c, TrkFontWidth* out) {
  void (*get_width_entry)(JUTFont*, int, TrkFontWidth*) = (*(void (***)(JUTFont*, int, TrkFontWidth*))font)[0x2C/4];
  get_width_entry(font, c, out);
}

static u32 trk_strlen(const char* str) {
  u32 len = 0;
  while (str[len] != '\0') {
    len++;
  }
  return len;
}

// Width of a string as drawString_size_scale draws it at the given size.
static float trk_text_width(JUTFont* font, const char* str, float size) {
  float scale = size / (float)trk_font_cell_width(font);
  float width = 0.0f;
  for (u32 i = 0; str[i] != '\0'; i++) {
    TrkFontWidth entry;
    trk_font_width_entry(font, (u8)str[i], &entry);
    width += (float)entry.width * scale;
  }
  return width;
}

// Writes a number in decimal and returns the end of the string.
static char* trk_format_uint(char* out, u16 value) {
  char digits[5];
  int count = 0;
  do {
    digits[count++] = (char)('0' + value % 10);
    value /= 10;
  } while (value != 0);
  while (count > 0) {
    *out++ = digits[--count];
  }
  *out = '\0';
  return out;
}

static char* trk_format_str(char* out, const char* str) {
  while (*str != '\0') {
    *out++ = *str++;
  }
  *out = '\0';
  return out;
}

static void trk_format_counter(char* out, const TrkUiCounter* counter) {
  if (counter->available != TRK_UI_COUNTER_UNKNOWN) {
    out = trk_format_uint(out, counter->available);
    *out++ = '/';
  }
  trk_format_uint(out, counter->remaining);
}

// Sets up GX for the font every time, since boxes drawn in between change it.
static void trk_draw_text(JUTFont* font, float x, float y, float size, const char* str, TrkColor color) {
  trk_font_set_gx(font);
  setCharColor__7JUTFontFQ28JUtility6TColor(font, color);
  drawString_size_scale__7JUTFontFffffPCcUlb(font, x, y, size, size, str, trk_strlen(str), true);
}

// Drawing context: the menu's ortho port and font, and the top left corner of the list panel.
typedef struct {
  J2DOrthoGraph* port;
  JUTFont* font;
  float x;
  float y;
} TrkDraw;

// J2DFillBox doesn't set up the GX state for untextured quads, so after drawing text it needs the
// port's 2D setup again.
static void trk_fill_box(const TrkDraw* draw, float x, float y, float w, float h, TrkColor color) {
  setPort__13J2DOrthoGraphFv(draw->port);
  J2DFillBox__FffffQ28JUtility6TColor(x, y, w, h, color);
}

// A counter in a box. x and y are the box's top left corner.
static void trk_draw_counter(const TrkDraw* draw, float x, float y, const TrkUiCounter* counter) {
  JUTFont* font = draw->font;
  char text[8];
  trk_format_counter(text, counter);
  float width = trk_text_width(font, text, TRK_COUNTER_SIZE);
  trk_fill_box(draw, x, y, width + 2*TRK_COUNTER_PAD, TRK_COUNTER_SIZE + TRK_COUNTER_PAD, trk_box_color);
  trk_draw_text(font, x + TRK_COUNTER_PAD, y + TRK_COUNTER_SIZE - 1.0f, TRK_COUNTER_SIZE, text, trk_status_colors[counter->status]);
}

static void trk_draw_world(const TrkDraw* draw) {
  u16 num_groups = trk_count(TRK_SEC_GROUPS);
  for (u16 group_index = 0; group_index < num_groups; group_index++) {
    TrkGroup group;
    trk_get_group(group_index, &group);
    if (group.id < 1 || group.id > TRK_SQUARES) {
      continue;
    }
    TrkUiCounter counter;
    tracker_ui_group_counter(group_index, &counter);
    if (counter.status == TRK_UI_NONE) {
      continue;
    }
    int column = (group.id - 1) % 7;
    int row = (group.id - 1) / 7;
    trk_draw_counter(draw, TRK_GRID_X + column*TRK_CELL_W + 2.0f, TRK_GRID_Y + row*TRK_CELL_H + 2.0f, &counter);
  }

  char text[24];
  char* end = trk_format_str(text, "Checked ");
  end = trk_format_uint(end, TRK_STATE->num_checked);
  end = trk_format_str(end, "/");
  trk_format_uint(end, TRK_STATE->num_locations);
  trk_draw_text(draw->font, TRK_TOTALS_X, TRK_TOTALS_Y, TRK_TOTALS_SIZE, text, trk_status_colors[TRK_UI_UNKNOWN]);
  u16 count;
  tracker_ui_page_group(0, &count);
  if (count > 0) {
    trk_draw_text(draw->font, TRK_TOTALS_X, TRK_TOTALS_Y + 18.0f, TRK_HINT_SIZE, "Z: other locations", trk_hint_color);
  }
}

// Draws text at the given size, or smaller if it would be wider than max_width.
static void trk_draw_text_fit(JUTFont* font, float x, float y, float size, float max_width, const char* str, TrkColor color) {
  float width = trk_text_width(font, str, size);
  if (width > max_width) {
    size = size*max_width/width;
  }
  trk_draw_text(font, x, y, size, str, color);
}

static void trk_draw_right_aligned(JUTFont* font, float right, float y, float size, const char* str, TrkColor color) {
  trk_draw_text(font, right - trk_text_width(font, str, size), y, size, str, color);
}

// "sel+1/count" right-aligned at right.
static void trk_draw_position(const TrkDraw* draw, float right, float y, u16 sel, u16 count) {
  char text[16];
  char* end = trk_format_uint(text, sel + 1);
  end = trk_format_str(end, "/");
  trk_format_uint(end, count);
  trk_draw_right_aligned(draw->font, right, y, TRK_HINT_SIZE, text, trk_hint_color);
}

// For a group behind a randomized entrance, the entrance it's reached from once the player has been
// through it (no spoilers before that).
static void trk_draw_entrance_line(const TrkDraw* draw, u8 group_index) {
  int entrance_index = tracker_ui_group_entrance(group_index);
  if (entrance_index < 0) {
    return;
  }
  char text[64];
  char* end = trk_format_str(text, "Entrance: ");
  if (tracker_is_entrance_visited((u16)entrance_index)) {
    TrkEntrance entrance;
    trk_get_entrance((u16)entrance_index, &entrance);
    trk_format_str(end, trk_string(entrance.entrance_name));
  } else {
    trk_format_str(end, "Unknown entrance");
  }
  trk_draw_text(draw->font, draw->x + 8.0f, draw->y + TRK_PANEL_H - 25.0f, TRK_HINT_SIZE, text, trk_text_color);
}

// A group's locations: a title with the group's counter, one row per location (checkbox, name in its
// status colour, struck through once checked) and a hint line.
static void trk_draw_location_list(const TrkDraw* draw, u8 group_index, const char* hint) {
  JUTFont* font = draw->font;
  TrkUiState* ui = TRK_UI_STATE;
  TrkGroup group;
  trk_get_group(group_index, &group);
  trk_fill_box(draw, draw->x, draw->y, TRK_PANEL_W, TRK_PANEL_H, trk_panel_color);

  float right = draw->x + TRK_PANEL_W - 8.0f;
  trk_draw_text(font, draw->x + 8.0f, draw->y + TRK_TITLE_SIZE + 3.0f, TRK_TITLE_SIZE, trk_string(group.name), trk_text_color);
  TrkUiCounter counter;
  tracker_ui_group_counter(group_index, &counter);
  char text[16];
  trk_format_counter(text, &counter);
  trk_draw_right_aligned(font, right, draw->y + TRK_TITLE_SIZE + 3.0f, TRK_TITLE_SIZE, text, trk_status_colors[counter.status]);
  trk_fill_box(draw, draw->x + 6.0f, draw->y + TRK_ROWS_OFFSET - 4.0f, TRK_PANEL_W - 12.0f, 1.0f, trk_hint_color);

  TrkUiInfo info[TRK_UI_MAX_INFO];
  u16 num_info = tracker_ui_info_lines(group_index, info);
  u16 rows = TRK_UI_LIST_ROWS - num_info;
  u16 row = 0;
  for (; row < rows && ui->scroll + row < group.num_locations; row++) {
    u16 i = ui->scroll + row;
    u16 location_index = group.first_location + i;
    TrkLocation loc;
    trk_get_location(location_index, &loc);
    float top = draw->y + TRK_ROWS_OFFSET + row*TRK_ROW_H;
    if (i == ui->sel) {
      trk_fill_box(draw, draw->x + 4.0f, top, TRK_PANEL_W - 8.0f, TRK_ROW_H, ui->flash_timer > 0 ? trk_flash_color : trk_select_color);
    }
    u8 status = tracker_ui_location_status(location_index);
    TrkColor color = trk_status_colors[status];
    // Checkbox: filled once checked.
    float box_y = top + (TRK_ROW_H - 11.0f)/2;
    trk_fill_box(draw, draw->x + 10.0f, box_y, 11.0f, 11.0f, color);
    if (status != TRK_UI_DONE) {
      trk_fill_box(draw, draw->x + 12.0f, box_y + 2.0f, 7.0f, 7.0f, trk_panel_color);
    }
    const char* name = trk_string(loc.name);
    float baseline = top + TRK_ROW_H - 5.0f;
    trk_draw_text(font, draw->x + 28.0f, baseline, TRK_ROW_SIZE, name, color);
    if (status == TRK_UI_DONE) {
      trk_fill_box(draw, draw->x + 27.0f, baseline - 5.0f, trk_text_width(font, name, TRK_ROW_SIZE) + 2.0f, 1.5f, color);
    }
  }

  // Info lines right after the locations, under a separator.
  for (u16 i = 0; i < num_info; i++, row++) {
    float top = draw->y + TRK_ROWS_OFFSET + row*TRK_ROW_H;
    if (i == 0 && group.num_locations > 0) {
      trk_fill_box(draw, draw->x + 6.0f, top + 1.0f, TRK_PANEL_W - 12.0f, 1.0f, trk_hint_color);
    }
    char line[96];
    char* end;
    if (info[i].kind == TRK_INFO_ENTRANCE) {
      TrkEntrance entrance;
      trk_get_entrance(info[i].index, &entrance);
      end = trk_format_str(line, trk_string(entrance.entrance_name));
      end = trk_format_str(end, " -> ");
      trk_format_str(end, info[i].revealed ? trk_string(entrance.exit_name) : "?");
    } else {
      TrkChart chart;
      trk_get_chart(info[i].index, &chart);
      end = trk_format_str(line, "Chart: ");
      trk_format_str(end, info[i].revealed ? trk_string(chart.name) : "not owned");
    }
    trk_draw_text_fit(font, draw->x + 10.0f, top + TRK_ROW_H - 5.0f, TRK_HINT_SIZE + 1.0f, TRK_PANEL_W - 20.0f, line,
      info[i].revealed ? trk_text_color : trk_hint_color);
  }

  trk_draw_entrance_line(draw, group_index);
  float hint_y = draw->y + TRK_PANEL_H - 8.0f;
  trk_draw_text(font, draw->x + 8.0f, hint_y, TRK_HINT_SIZE, hint, trk_hint_color);
  if (group.num_locations > 0) {
    trk_draw_position(draw, right, hint_y, ui->sel, group.num_locations);
  }
}

// The groups on the list page with their counters. The footer says how the selected group is reached.
static void trk_draw_page(const TrkDraw* draw) {
  JUTFont* font = draw->font;
  TrkUiState* ui = TRK_UI_STATE;
  trk_fill_box(draw, draw->x, draw->y, TRK_PANEL_W, TRK_PANEL_H, trk_panel_color);
  float right = draw->x + TRK_PANEL_W - 8.0f;
  trk_draw_text(font, draw->x + 8.0f, draw->y + TRK_TITLE_SIZE + 3.0f, TRK_TITLE_SIZE, "Other Locations", trk_text_color);
  trk_fill_box(draw, draw->x + 6.0f, draw->y + TRK_ROWS_OFFSET - 4.0f, TRK_PANEL_W - 12.0f, 1.0f, trk_hint_color);

  u16 count;
  tracker_ui_page_group(0, &count);
  for (u16 row = 0; row < TRK_UI_LIST_ROWS && ui->page_scroll + row < count; row++) {
    u16 n = ui->page_scroll + row;
    int group_index = tracker_ui_page_group(n, NULL);
    TrkGroup group;
    trk_get_group(group_index, &group);
    float top = draw->y + TRK_ROWS_OFFSET + row*TRK_ROW_H;
    if (n == ui->page_sel) {
      trk_fill_box(draw, draw->x + 4.0f, top, TRK_PANEL_W - 8.0f, TRK_ROW_H, trk_select_color);
    }
    TrkUiCounter counter;
    tracker_ui_group_counter(group_index, &counter);
    float baseline = top + TRK_ROW_H - 5.0f;
    TrkColor color = counter.status == TRK_UI_DONE ? trk_status_colors[TRK_UI_DONE] : trk_text_color;
    trk_draw_text(font, draw->x + 10.0f, baseline, TRK_ROW_SIZE, trk_string(group.name), color);
    char text[16];
    trk_format_counter(text, &counter);
    trk_draw_right_aligned(font, right, baseline, TRK_ROW_SIZE, text, trk_status_colors[counter.status]);
  }

  int selected = tracker_ui_page_group(ui->page_sel, NULL);
  if (selected >= 0) {
    trk_draw_entrance_line(draw, (u8)selected);
  }
  float hint_y = draw->y + TRK_PANEL_H - 8.0f;
  trk_draw_text(font, draw->x + 8.0f, hint_y, TRK_HINT_SIZE, "Stick: select    A: open    B: back", trk_hint_color);
  trk_draw_position(draw, right, hint_y, ui->page_sel, count);
}

// The group of the square shown in square view, or -1.
static int trk_fmap_square_group(u8* fmap) {
  s8* sv = *(s8**)(fmap + TRK_FMAP_SV_OFFSET);
  int square = (sv[TRK_FMAP_SV_CUR_X] + 3) + (sv[TRK_FMAP_SV_CUR_Y] + 3)*7 + 1;
  if (square < 1 || square > TRK_SQUARES) {
    return -1;
  }
  int group_index = trk_find_group((u8)square);
  if (group_index < 0 || group_index >= TRK_UI_NO_GROUP) {
    return -1;
  }
  TrkGroup group;
  trk_get_group(group_index, &group);
  return group.num_locations > 0 || tracker_ui_info_lines((u8)group_index, NULL) > 0 ? group_index : -1;
}

// Buttons pressed this frame (enum TrkUiButton).
static u16 trk_ui_buttons(void) {
  u16 trig = trk_mem_u16(TRK_PAD_TRIG_ADDR);
  u16 buttons = 0;
  if (trig & TRK_PAD_TRIG_X) {
    buttons |= TRK_BTN_X;
  }
  if (trig & TRK_PAD_TRIG_Z) {
    buttons |= TRK_BTN_Z;
  }
  if (trig & TRK_PAD_TRIG_A) {
    buttons |= TRK_BTN_A;
  }
  if (trig & TRK_PAD_TRIG_B) {
    buttons |= TRK_BTN_B;
  }
  return buttons;
}

TRK_INLINE s8 trk_ui_stick_y(void) {
  return (s8)trk_mem_u8(TRK_PAD_STICK_Y_ADDR);
}

// Called first by each menu's input hook. Starts without a page if the menu was closed since the last frame (or
// another menu ran). The sea chart re-evaluates the logic then; the other menus do when a page opens.
static void trk_ui_menu_frame(u8 menu) {
  TrkUiState* ui = TRK_UI_STATE;
  if (TRK_STATE->frame_count - ui->proc_frame > 2 || ui->menu != menu) {
    ui->page = TRK_PAGE_NONE;
    if (menu == TRK_MENU_FMAP && trk_tables_valid()) {
      tracker_logic_evaluate();
    }
  }
  ui->proc_frame = TRK_STATE->frame_count;
  ui->menu = menu;
}

// The page shown: the list page or a group's location list.
static void trk_draw_ui_page(const TrkDraw* draw) {
  TrkUiState* ui = TRK_UI_STATE;
  if (ui->page == TRK_PAGE_GROUPS) {
    trk_draw_page(draw);
  } else {
    trk_draw_location_list(draw, ui->page_group, "Stick: select    X: mark    B: back");
  }
}

void tracker_fmap_proc(u8* fmap) {
  TrkUiState* ui = TRK_UI_STATE;
  trk_ui_menu_frame(TRK_MENU_FMAP);
  ui->view = TRK_VIEW_NONE;
  bool consumed = false;
  if (trk_tables_valid()) {
    u8 proc = fmap[TRK_FMAP_PROC_IDX_OFFSET];
    if (proc == TRK_FMAP_PROC_SELECT_GRID) {
      ui->view = TRK_VIEW_WORLD;
    } else if (proc == TRK_FMAP_PROC_ZOOM_LV1) {
      ui->view = TRK_VIEW_SQUARE;
    }
    int square_group = ui->view == TRK_VIEW_SQUARE ? trk_fmap_square_group(fmap) : -1;
    consumed = tracker_ui_input(ui->view, square_group, trk_ui_buttons(), trk_ui_stick_y());
  }
  // While a tracker page is shown, the chart's own input handler doesn't run, so none of its buttons
  // (B and D-pad Left/Down close the chart, A zooms, Y opens the compare page) do anything.
  if (!consumed && ui->page == TRK_PAGE_NONE) {
    FmapProc__12dMenu_Fmap_cFv(fmap);
  }
}

void tracker_fmap_draw(u8* dlst) {
  draw__12dDlst_FMAP_cFv(dlst);
  if (!trk_tables_valid()) {
    return;
  }
  TrkUiState* ui = TRK_UI_STATE;
  // The input handler runs in the same frame (or the one before, depending on the order of the
  // menu's move and draw), unless the chart is in a state the tracker doesn't draw on.
  if (TRK_STATE->frame_count - ui->proc_frame > 1 || ui->menu != TRK_MENU_FMAP) {
    return;
  }
  u8* fmap = dlst - TRK_FMAP_DLST_OFFSET;
  u8 proc = fmap[TRK_FMAP_PROC_IDX_OFFSET];
  TrkDraw draw;
  draw.port = *(J2DOrthoGraph**)TRK_CURRENT_GRAF_PORT_ADDR;
  draw.font = *(JUTFont**)(fmap + TRK_FMAP_FONT_OFFSET);
  draw.x = TRK_PANEL_X;
  draw.y = TRK_PANEL_Y;
  if (ui->page != TRK_PAGE_NONE) {
    trk_draw_ui_page(&draw);
  } else if (proc == TRK_FMAP_PROC_SELECT_GRID && ui->view == TRK_VIEW_WORLD) {
    trk_draw_world(&draw);
  } else if (proc == TRK_FMAP_PROC_ZOOM_LV1 && ui->view == TRK_VIEW_SQUARE) {
    int group_index = trk_fmap_square_group(fmap);
    if (group_index < 0) {
      return;
    }
    trk_draw_location_list(&draw, (u8)group_index, "Stick: select    X: mark    Z: more");
  } else {
    return;
  }
  // Leave the port's 2D setup for whatever draws next.
  setPort__13J2DOrthoGraphFv(draw.port);
  ui->draw_frame = TRK_STATE->frame_count;
}

#endif
