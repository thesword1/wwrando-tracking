; In-game tracker runtime. Only applied when the tracker is enabled (tweaks.add_in_game_tracker).
; The C sources live in asm/tracker/. See docs/dev/tracker-runtime.md.

.open "sys/main.dol"

; Patch-time tables, written by tweaks.add_in_game_tracker (format: tracker/serialize.py).
; This is .bss so the 24 KB reserve isn't stored as zeros in the patch diff. The tweak writes the
; whole reserve into main.dol, which extends the custom code section over it.
; It comes first so the C code below can link against it.
.org @NextFreeSpace
.section ".bss"
.global tracker_data
tracker_data:
  .space 0x6000
.global tracker_data_end
tracker_data_end:

.org @NextFreeSpace
.include "tracker/tracker.c"

.close
