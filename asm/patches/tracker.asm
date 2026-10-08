; In-game tracker runtime. Only applied when the tracker is enabled (tweaks.add_in_game_tracker).
; The C sources live in asm/tracker/. See docs/dev/tracker-runtime.md.

.open "sys/main.dol"

; Patch-time tables, written by tweaks.add_in_game_tracker (format: tracker/serialize.py), followed
; by the runtime state (asm/tracker/tracker_state.h).
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
  .space 0x100
.global tracker_reserve_end
tracker_reserve_end:

.org @NextFreeSpace
.include "tracker/tracker.c"

; misc_rando_features.asm makes dSv_info_c::init call init_save_with_tweaks here when a new game is
; started. tracker_init_save resets the tracker's save data, then calls init_save_with_tweaks.
.org 0x8005D618 ; In dSv_info_c::init
  bl tracker_init_save

; Run the tracker's per-frame update during gameplay.
.org 0x8023502C ; In dScnPly_Execute
  bl tracker_on_frame ; Replaces a call to dKy_itudemo_se, which tracker_on_frame calls first

.close
