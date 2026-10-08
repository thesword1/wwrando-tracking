# In-game tracker runtime

Developer notes for the tracker code that runs inside the game (Phase 4 of `PROJECT_PLAN.md`).
Memory addresses it relies on are in `memory-map.md`; the patch-time Python side is `tracker/`.

## Enabling it

The tracker is only patched in when the randomizer is run with the development flag `--tracker`:

```sh
python wwrando.py --aptww seed.aptww --clean-iso vanilla.iso --output-folder out --tracker
```

Without the flag, the output is byte-identical to a build without the tracker. The flag sets
`WWRandomizer.in_game_tracker`, which makes `apply_necessary_post_randomization_tweaks` call
`tweaks.add_in_game_tracker`. It will be replaced by the user-facing "In-game tracker" option
(default on) once the offline-mode options work has landed.

`add_in_game_tracker`:

1. applies the `tracker` patch (`asm/patches/tracker.asm`, which compiles `asm/tracker/tracker.c`),
2. builds the seed's tables with `tracker.serialize.build_tracker_tables()`. In AP mode they come
   from the plando's locations, charts, entrances and required bosses. In offline mode they come
   from the logic's progress locations (minus those banned by required bosses), the chart and
   entrance randomizers, and the required dungeons. Both modes use the entrance options,
3. serializes them with `serialize_tracker_tables()` and writes them into the `tracker_data` reserve,
   failing the build if they don't fit.

## Code layout

| File | Contents |
|---|---|
| `asm/patches/tracker.asm` | The `tracker_data` reserve (0x6000 bytes) and `.include "tracker/tracker.c"` |
| `asm/tracker/tracker.c` | Single translation unit that `#include`s every module, so the whole runtime is one assembled chunk |
| `asm/tracker/tracker_types.h` | `u8`/`u16`/`u32`, `bool`, `TRK_INLINE` (always_inline, since the game build uses `-fno-inline`) |
| `asm/tracker/tracker_mem.h` | All reads/writes of game memory and the tables go through these helpers |
| `asm/tracker/tracker_tables.[ch]` | Reader for the table format |
| `asm/tracker/tracker_host.c` | Host build only: mock RAM and the table pointer |
| `asm/tracker/Makefile` | Host build (`make -C asm/tracker host`) |
| `tracker/serialize.py` | Table format (documented at the top of the file), serializer and a Python reader |

Rules for the C code (see the comment in `tracker.c`):

- **Freestanding.** No libc. Game functions are declared by hand and their symbols added to
  `asm/linker.ld`.
- **No mutable globals.** `asm/assemble.py` places `.data`/`.bss` from C right after the code, but
  only the bytes of the code chunk end up in main.dol, so a trailing `.bss` would overlap the
  game's heap. Runtime state goes in a reserve declared in `tracker.asm`.
- **Memory access through `tracker_mem.h`.** In the game, `TRK_MEM(addr)` is the address itself and
  `TRK_DATA` is `tracker_data`. In the host build (`-DTRACKER_HOST`), game memory is a 24 MiB buffer
  standing in for 0x80000000-0x817FFFFF and the tables are a buffer passed in by the test.
- Big-endian data is read byte by byte (`trk_be16`, `trk_mem_u32`, ...) so the same code is correct
  on the little-endian host.
- Non-static functions become custom symbols (`asm/custom_symbols.txt`) that other patches and
  `tweaks.py` can call or reference. Mark functions that host tests call with `TRK_EXPORT`.

### Placement

`asm/assemble.py` assembles `tracker.asm` last (after `offline_mode.asm`), so enabling the tracker
never moves any other custom code or data. The Archipelago client relies on fixed addresses in
`archipelago.asm`.

### Why the reserve is `.bss`

`tracker_data` is declared in a `.bss` section in its own free-space chunk, so the patch diff
doesn't carry 24 KB of zeros. The tweak writes the whole reserve (tables plus zero padding) with
`patcher.add_or_extend_main_dol_free_space_section`, which extends the custom code section over it
and moves the start of the game's heap past it. The reserve comes first in `tracker.asm` so that
the C code, linked afterwards, can reference it.

## Table format

`tracker/serialize.py` has the byte-level description. In short: a 0x20-byte header (magic
`WWTK`, format version, seed tag, total size, section count), a directory with one
`{offset, count, entry size}` entry per section, then the sections:

| Section | Entry | Contents |
|---|---|---|
| LOCATIONS | 12 B | group ID, detection type, stage ID, mask, byte address, name, special case |
| GROUPS | 8 B | ID (1-49 squares, 50+ list page), kind, first location, location count, name |
| ENTRANCES | 8 B | island square / parent group, exit's group, category, entrance and exit names. Index = visited bit |
| TRIGGERS | 12 B | stage name, room/spawn (0xFF = any), entrance index |
| CHARTS | 12 B | destination square, chart number, item ID, owned and salvaged byte offset + mask, name |
| STRINGS | bytes | NUL-terminated ASCII, referenced by offset |
| LOGIC | bytes | Compiled logic bytecode (Phase 3, empty for now) |
| ITEMS | 8 B | Item-read descriptors for logic (Phase 3, empty for now) |

Locations are ordered by group, so each group's locations are contiguous. The C reader checks the
magic and format version (`trk_tables_valid`); bump `FORMAT_VERSION` and `TRK_FORMAT_VERSION`
together on any layout change. `test_tracker_serialize.py` checks the Python and C constants agree.

Sizes (bytes) for the test fixtures: 5.7-11.3 KB; the worst case (all 320 locations and every
entrance tracked) is 14.1 KB. About 60% is strings. The 24 KB reserve leaves room for the logic
bytecode.

## Size in main.dol

With the table reader only, the tracker adds 0x568 bytes of code plus the 0x6000-byte reserve:
main.dol grows by 26,124 bytes, and the game heap shrinks by the same amount.

## Tests

- `test/test_tracker_serialize.py`: round trip of every `.aptww` fixture through the serializer
  and the Python reader, size budget, and constants shared with the C code and `tracker.asm`.
- `test/test_tracker_c.py`: builds the C runtime for the host (`test/tracker_c_host.py` runs
  `make -C asm/tracker host` with `gcc` into a temp dir and loads it with ctypes) and checks the C
  reader returns exactly what the serializer wrote, for every fixture. Skipped when `make` or `gcc`
  is missing. CI (ubuntu) has both.

Run them with the rest of the suite:

```sh
pytest test -m "not saving" -q
```

After changing anything under `asm/`, regenerate the patch diffs with `tools/devkitppc/assemble.sh`
(`toolchain.md`) and commit them; the ASM workflow checks they are reproducible.
