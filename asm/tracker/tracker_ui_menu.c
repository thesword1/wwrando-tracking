// The tracker's pages on the dungeon map (dMenu_Dmap_c) and the Quest Status screen (dMenu_Collect_c), where the
// sea chart can't be opened. Z opens the location list of the group the player is in (tracker_ui_stage_group), or
// the list page if the stage isn't a tracked group. The pages and their input are the sea chart's (tracker_ui.c).
//
// Both menus are hooked through their vtables (asm/patches/tracker.asm), so no vanilla code is changed:
// - _move (once per frame while the menu is open and idle) is replaced by tracker_dmap_move / tracker_collect_move.
//   While a page is shown, the menu's own _move isn't called.
// - draw (the 2D display-list callback) is replaced by tracker_dmap_draw / tracker_collect_draw, which call it and
//   then draw the page on top.
// The pause menu's window code (dMs_Execute) checks the close and page-switch buttons (B, Start, R, L on Quest
// Status; B, D-pad Down and Left on the dungeon map) itself, before calling _move, unless the menu's noteCheck() is
// true (an item description is open). While a page is shown, the hooks set the flag noteCheck() reads, so those
// buttons only reach the tracker. The flag is only set while no description is open, and cleared again when the
// page closes.

#include "tracker_logic.h"
#include "tracker_mem.h"
#include "tracker_state.h"
#include "tracker_tables.h"
#include "tracker_ui.h"

#ifndef TRACKER_HOST

void _move__12dMenu_Dmap_cFv(void* dmap);
void draw__12dMenu_Dmap_cFv(void* dmap);
void _move__15dMenu_Collect_cFv(void* collect);
void draw__15dMenu_Collect_cFv(void* collect);

// dMenu_Dmap_c members (zeldaret/tww include/d/d_menu_dmap.h); dMenu_Collect_c's are in tracker_collect.c.
// noteCheck() is mUserArea (fopMsgM_pane_class +0x36) == 1 of mNk00Pane (Dmap) / m7E8 (Collect).
#define TRK_DMAP_NOTE_OFFSET 0x972 // s16 mNk00Pane.mUserArea
#define TRK_DMAP_FONT_OFFSET 0x14A8 // JUTFont* mFont

// The panel is centered vertically, and left of the button icons in the top right corner of the screen.
#define TRK_MENU_PANEL_X 96.0f
#define TRK_MENU_PANEL_Y ((480.0f - TRK_PANEL_H)/2)

// The menus are busier than the sea chart, so the panel is made opaque.
static const TrkColor trk_menu_backing_color = {0xFF, 0xF8, 0xE0, 0xFF};

// Input for a menu. can_open is whether Z may open a page (the menu is idle). Returns whether the menu's own _move
// may run.
static bool trk_menu_move(u8* menu, u8 kind, u16 note_offset, bool can_open) {
  TrkUiState* ui = TRK_UI_STATE;
  trk_ui_menu_frame(kind);
  if (!trk_tables_valid()) {
    return true;
  }
  bool was_shown = ui->page != TRK_PAGE_NONE;
  if (!was_shown && !can_open) {
    return true;
  }
  bool shown = tracker_ui_menu_input(tracker_ui_stage_group(), trk_ui_buttons(), trk_ui_stick_y());
  s16* note = (s16*)(menu + note_offset);
  if (shown && !was_shown) {
    *note = 1;
    tracker_logic_evaluate();
  } else if (!shown && was_shown) {
    *note = 0;
  }
  return !shown && !was_shown;
}

static void trk_menu_draw(u8 kind, JUTFont* font) {
  if (!trk_tables_valid()) {
    return;
  }
  TrkUiState* ui = TRK_UI_STATE;
  if (TRK_STATE->frame_count - ui->proc_frame > 1 || ui->menu != kind || ui->page == TRK_PAGE_NONE) {
    return;
  }
  TrkDraw draw;
  draw.port = *(J2DOrthoGraph**)TRK_CURRENT_GRAF_PORT_ADDR;
  draw.font = font;
  draw.x = TRK_MENU_PANEL_X;
  draw.y = TRK_MENU_PANEL_Y;
  trk_fill_box(&draw, draw.x, draw.y, TRK_PANEL_W, TRK_PANEL_H, trk_menu_backing_color);
  trk_draw_ui_page(&draw);
  setPort__13J2DOrthoGraphFv(draw.port);
  ui->draw_frame = TRK_STATE->frame_count;
}

void tracker_dmap_move(u8* dmap) {
  bool idle = *(s16*)(dmap + TRK_DMAP_NOTE_OFFSET) != 1;
  if (trk_menu_move(dmap, TRK_MENU_DMAP, TRK_DMAP_NOTE_OFFSET, idle)) {
    _move__12dMenu_Dmap_cFv(dmap);
  }
}

void tracker_dmap_draw(u8* dmap) {
  draw__12dMenu_Dmap_cFv(dmap);
  trk_menu_draw(TRK_MENU_DMAP, *(JUTFont**)(dmap + TRK_DMAP_FONT_OFFSET));
}

void tracker_collect_move(u8* collect) {
  bool idle = *(s16*)(collect + TRK_COLLECT_NOTE_OPEN_OFFSET) != 1 && collect[TRK_COLLECT_MODE_OFFSET] == 0;
  if (trk_menu_move(collect, TRK_MENU_COLLECT, TRK_COLLECT_NOTE_OPEN_OFFSET, idle)) {
    _move__15dMenu_Collect_cFv(collect);
  }
}

// The Triforce shard counter (tracker_collect.c) hides itself while a page is shown, since the page sets the
// description flag.
void tracker_collect_draw(u8* collect) {
  draw__15dMenu_Collect_cFv(collect);
  trk_draw_triforce_counter(collect);
  trk_menu_draw(TRK_MENU_COLLECT, *(JUTFont**)(collect + TRK_COLLECT_FONT_OFFSET));
}

#endif
