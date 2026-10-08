// The tracker runtime as a single translation unit. asm/patches/tracker.asm includes this file, so
// all modules share one compiled chunk (and GCC's local labels can't collide between files).
//
// Rules for code in this directory:
// - Freestanding: no libc headers or calls. Game functions are declared by hand and their symbols
//   listed in asm/linker.ld.
// - No mutable globals (.data/.bss): the assembler doesn't reserve space for them in main.dol. Keep
//   runtime state in TRK_STATE (tracker_state.h) and saved state in the save region (tracker_save.h).
// - Game memory and the tables are only read through tracker_mem.h, so the host build can mock them.

#include "tracker_tables.c"
#include "tracker_save.c"
#include "tracker_detect.c"
#include "tracker_runtime.c"
