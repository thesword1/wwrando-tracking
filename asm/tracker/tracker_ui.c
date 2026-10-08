// The tracker's sea chart UI. dMenu_Fmap_c (the sea chart menu, docs/dev/memory-map.md section 4) is
// hooked twice (asm/patches/tracker.asm):
// - tracker_fmap_proc replaces FmapProc in the chart's main proc table. It runs once per frame while
//   the normal sea chart is open and idle (not during the open/close animations, the compare page,
//   or warp mode) and records which view is shown.
// - tracker_fmap_draw replaces dDlst_FMAP_c::draw in its vtable. It draws the chart, then the
//   tracker on top of it, but only while the input handler ran recently, so nothing is drawn in
//   the views the tracker doesn't handle.

#include "tracker_detect.h"
#include "tracker_mem.h"
#include "tracker_state.h"
#include "tracker_tables.h"
#include "tracker_ui.h"

#define TRK_SQUARES 49

// Whether a location is in logic. The logic runtime isn't there yet, so this is always unknown.
TRK_INLINE u8 trk_ui_location_logic(u16 location_index) {
  (void)location_index;
  return TRK_UI_UNKNOWN;
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
#define TRK_FMAP_PROC_SELECT_GRID 0

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

static const TrkColor trk_status_colors[] = {
  [TRK_UI_NONE] = {0x00, 0x00, 0x00, 0x00},
  [TRK_UI_DONE] = {0x80, 0x80, 0x80, 0xFF},
  [TRK_UI_IN_LOGIC] = {0x29, 0x29, 0xCC, 0xFF},
  [TRK_UI_OUT_OF_LOGIC] = {0xCC, 0x29, 0x29, 0xFF},
  [TRK_UI_UNKNOWN] = {0x30, 0x20, 0x10, 0xFF},
};
static const TrkColor trk_box_color = {0xFF, 0xF8, 0xE0, 0xD0};

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

static void trk_draw_text(JUTFont* font, float x, float y, float size, const char* str, TrkColor color) {
  setCharColor__7JUTFontFQ28JUtility6TColor(font, color);
  drawString_size_scale__7JUTFontFffffPCcUlb(font, x, y, size, size, str, trk_strlen(str), true);
}

// Drawing context: the chart's ortho port and font.
typedef struct {
  J2DOrthoGraph* port;
  JUTFont* font;
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
  trk_font_set_gx(font);
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
  trk_font_set_gx(draw->font);
  trk_draw_text(draw->font, TRK_TOTALS_X, TRK_TOTALS_Y, TRK_TOTALS_SIZE, text, trk_status_colors[TRK_UI_UNKNOWN]);
}

void tracker_fmap_proc(u8* fmap) {
  TrkUiState* ui = TRK_UI_STATE;
  ui->proc_frame = TRK_STATE->frame_count;
  ui->view = fmap[TRK_FMAP_PROC_IDX_OFFSET] == TRK_FMAP_PROC_SELECT_GRID ? TRK_VIEW_WORLD : TRK_VIEW_NONE;
  FmapProc__12dMenu_Fmap_cFv(fmap);
}

void tracker_fmap_draw(u8* dlst) {
  draw__12dDlst_FMAP_cFv(dlst);
  if (!trk_tables_valid()) {
    return;
  }
  TrkUiState* ui = TRK_UI_STATE;
  // The input handler runs in the same frame (or the one before, depending on the order of the
  // menu's move and draw), unless the chart is in a state the tracker doesn't draw on.
  if (TRK_STATE->frame_count - ui->proc_frame > 1) {
    return;
  }
  u8* fmap = dlst - TRK_FMAP_DLST_OFFSET;
  if (fmap[TRK_FMAP_PROC_IDX_OFFSET] != TRK_FMAP_PROC_SELECT_GRID || ui->view != TRK_VIEW_WORLD) {
    return;
  }
  TrkDraw draw;
  draw.port = *(J2DOrthoGraph**)TRK_CURRENT_GRAF_PORT_ADDR;
  draw.font = *(JUTFont**)(fmap + TRK_FMAP_FONT_OFFSET);
  trk_draw_world(&draw);
  // Leave the port's 2D setup for whatever draws next.
  setPort__13J2DOrthoGraphFv(draw.port);
  ui->draw_frame = TRK_STATE->frame_count;
}

#endif
