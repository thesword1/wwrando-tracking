; In-game tracker runtime. Only applied when the tracker is enabled (tweaks.add_in_game_tracker).
; The C sources live in asm/tracker/. See docs/dev/tracker-runtime.md.

.open "sys/main.dol"

; Patch-time tables, written by tweaks.add_in_game_tracker (format: tracker/serialize.py), followed
; by the runtime state (asm/tracker/tracker_state.h) and the sea chart UI's state (asm/tracker/tracker_ui.h).
; This is .bss so the reserve isn't stored as zeros in the patch diff. The tweak writes the whole
; reserve into main.dol, which extends the custom code section over it (and zero-initialises the
; state). It comes first so the C code below can link against it.
.org @NextFreeSpace
.section ".bss"
.global tracker_data
tracker_data:
  .space 0x6000
.global tracker_data_end
tracker_data_end:
.global tracker_state
tracker_state:
  .space 0x200
.global tracker_ui_state
tracker_ui_state:
  .space 0x40
.global tracker_reserve_end
tracker_reserve_end:

.org @NextFreeSpace
.include "tracker/tracker.c"

; misc_rando_features.asm makes dSv_info_c::init call init_save_with_tweaks here when a new game is
; started. tracker_init_save resets the tracker's save data, then calls init_save_with_tweaks.
.org 0x8005D618 ; In dSv_info_c::init
  bl tracker_init_save

; Every item get goes through execItemGet (pickups, chests, shops, NPCs, Archipelago deliveries). Call
; the item's function, then tell the tracker so it re-evaluates the logic.
.org 0x800C2E1C ; In execItemGet
  bl tracker_exec_item_func ; Replaces bctrl (the item_func_ptr entry is in ctr)
.org @NextFreeSpace
.global tracker_exec_item_func
tracker_exec_item_func:
  stwu sp, -0x10 (sp)
  mflr r0
  stw r0, 0x14 (sp)
  bctrl
  bl tracker_on_item_get
  lwz r0, 0x14 (sp)
  mtlr r0
  addi sp, sp, 0x10
  blr

; Run the tracker's per-frame update during gameplay.
.org 0x8023502C ; In dScnPly_Execute
  bl tracker_on_frame ; Replaces a call to dKy_itudemo_se, which tracker_on_frame calls first

; Sea chart UI (asm/tracker/tracker_ui.c).
.org 0x803923EC ; Function of the FmapProc pointer-to-member that __sinit copies into mainProc
  .int tracker_fmap_proc
.org 0x803925A0 ; __vt__12dDlst_FMAP_c: draw
  .int tracker_fmap_draw

; Triforce shard counter on the Quest Status screen (asm/tracker/tracker_collect.c).
.org 0x803920EC ; __vt__15dMenu_Collect_c: draw
  .int tracker_collect_draw

.close
