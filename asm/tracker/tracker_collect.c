// Triforce shard counter on the Quest Status (Collect) screen. The shards are drawn as eight small
// pieces of one triangle, so it's hard to tell how many are owned; this draws "n/8" under it.
// tracker_collect_draw replaces dMenu_Collect_c::draw in its vtable (asm/patches/tracker.asm). It
// draws the screen, then the counter on top, positioned from the Triforce frame pane so it follows
// the screen's slide and fade animations.

#include "tracker_mem.h"
#include "tracker_state.h"
#include "tracker_ui.h"

#define TRK_TRIFORCE_ADDR 0x803C4CC6 // dSv_player_collect_c::mTriforce: bit i = shard i+1
#define TRK_TRIFORCE_SHARDS 8

// Number of Triforce shards owned.
TRK_EXPORT u8 tracker_triforce_count(void) {
  u8 bits = trk_mem_u8(TRK_TRIFORCE_ADDR);
  u8 count = 0;
  for (int i = 0; i < TRK_TRIFORCE_SHARDS; i++) {
    count += (bits >> i) & 1;
  }
  return count;
}

// The counter's text, "n/8". out needs 4 bytes.
TRK_EXPORT void tracker_triforce_text(char* out) {
  out[0] = (char)('0' + tracker_triforce_count());
  out[1] = '/';
  out[2] = (char)('0' + TRK_TRIFORCE_SHARDS);
  out[3] = '\0';
}

#ifndef TRACKER_HOST

void draw__15dMenu_Collect_cFv(void* collect);

// dMenu_Collect_c members (zeldaret/tww include/d/d_menu_collect.h).
#define TRK_COLLECT_TRIB_PANE_OFFSET 0xFC8 // fopMsgM_pane_class mFC8: 'trib', the Triforce frame
#define TRK_COLLECT_NOTE_OPEN_OFFSET 0x81E // s16 m7E8.mUserArea: 1 while an item's description is shown
#define TRK_COLLECT_FONT_OFFSET 0x2470 // JUTFont* mpFont
#define TRK_COLLECT_MODE_OFFSET 0x27EE // u8 mCollectMode: 0 = cursor on the screen, 1/2 = song, 3 = save, 4 = options, 5 = save prompt
// J2DPane members.
#define TRK_PANE_GLOBAL_BOUNDS_OFFSET 0x1C // TBox2<f32> mGlobalBounds, screen space after the screen's draw
#define TRK_PANE_VISIBLE_OFFSET 0xAA
#define TRK_PANE_ALPHA_OFFSET 0xAC
#define TRK_PANE_CLASS_INIT_ALPHA_OFFSET 0x34 // fopMsgM_pane_class mInitAlpha: the pane's alpha when fully shown

// Layout, relative to the frame pane's bottom edge, in the screen's 640x480 space.
#define TRK_TRIFORCE_TEXT_SIZE 22.0f
#define TRK_TRIFORCE_BOX_Y 6.0f // Below the bottom of the frame pane
#define TRK_TRIFORCE_BOX_PAD 6.0f

static const TrkColor trk_triforce_box_color = {0x30, 0x20, 0x10, 0xC0};
static const TrkColor trk_triforce_text_color = {0xFF, 0xE8, 0x60, 0xFF};
static const TrkColor trk_triforce_full_color = {0xFF, 0xFF, 0xFF, 0xFF};

TRK_INLINE TrkColor trk_fade(TrkColor color, u32 fade) {
  color.a = (u8)(color.a * fade / 0xFF);
  return color;
}

void tracker_collect_draw(u8* collect) {
  draw__15dMenu_Collect_cFv(collect);
  // Only on the screen itself: not over an item's description, a song, or the save/options windows.
  if (collect[TRK_COLLECT_MODE_OFFSET] != 0 || *(s16*)(collect + TRK_COLLECT_NOTE_OPEN_OFFSET) == 1) {
    return;
  }
  u8* pane = *(u8**)(collect + TRK_COLLECT_TRIB_PANE_OFFSET);
  u32 alpha = pane[TRK_PANE_ALPHA_OFFSET];
  u32 init_alpha = collect[TRK_COLLECT_TRIB_PANE_OFFSET + TRK_PANE_CLASS_INIT_ALPHA_OFFSET];
  if (!pane[TRK_PANE_VISIBLE_OFFSET] || alpha == 0 || init_alpha == 0) {
    return;
  }
  // The frame is translucent when fully shown, so fade relative to its own alpha.
  u32 fade = alpha >= init_alpha ? 0xFF : alpha * 0xFF / init_alpha;
  float* bounds = (float*)(pane + TRK_PANE_GLOBAL_BOUNDS_OFFSET);
  JUTFont* font = *(JUTFont**)(collect + TRK_COLLECT_FONT_OFFSET);
  char text[4];
  tracker_triforce_text(text);
  float width = trk_text_width(font, text, TRK_TRIFORCE_TEXT_SIZE);
  float x = (bounds[0] + bounds[2] - width) / 2.0f;
  float y = bounds[3] + TRK_TRIFORCE_BOX_Y;
  TrkDraw draw;
  draw.port = *(J2DOrthoGraph**)TRK_CURRENT_GRAF_PORT_ADDR;
  draw.font = font;
  TrkColor color = tracker_triforce_count() == TRK_TRIFORCE_SHARDS ? trk_triforce_full_color : trk_triforce_text_color;
  trk_fill_box(&draw, x - TRK_TRIFORCE_BOX_PAD, y, width + 2*TRK_TRIFORCE_BOX_PAD, TRK_TRIFORCE_TEXT_SIZE + 4.0f,
               trk_fade(trk_triforce_box_color, fade));
  trk_draw_text(font, x, y + TRK_TRIFORCE_TEXT_SIZE, TRK_TRIFORCE_TEXT_SIZE, text, trk_fade(color, fade));
  // Leave the port's 2D setup for whatever draws next.
  setPort__13J2DOrthoGraphFv(draw.port);
  TRK_UI_STATE->collect_draw_frame = TRK_STATE->frame_count;
}

#endif
