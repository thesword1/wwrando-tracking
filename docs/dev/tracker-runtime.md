# In-game tracker runtime

Developer notes for the tracker code that runs inside the game (Phase 4 of `PROJECT_PLAN.md`).
Memory addresses it relies on are in `memory-map.md`; the patch-time Python side is `tracker/`.

## Enabling it

The tracker is controlled by the "In-Game Tracker" option (`Options.in_game_tracker`, on by default). It is a local
setting (`permalink=False`, so it's also in `AP_MODE_LOCAL_OPTIONS`): it isn't in permalinks or `.aptww` files and
stays editable in the GUI in both modes. On the command line the saved setting is used unless `--tracker` or
`--no-tracker` is given:

```sh
python wwrando.py --aptww seed.aptww --clean-iso vanilla.iso --output-folder out --no-tracker
```

With the option off, the output is byte-identical to a build without the tracker. When it's on,
`apply_necessary_post_randomization_tweaks` calls `tweaks.add_in_game_tracker`. Dry runs never build it.

The tracker's logic also depends on "Enable Tuner Logic". Archipelago doesn't write that option into `.aptww` files, so
in Archipelago mode it's a local setting too (default off, like the APWorld) that only affects the tracker.

`add_in_game_tracker`:

1. applies the `tracker` patch (`asm/patches/tracker.asm`, which compiles `asm/tracker/tracker.c`),
2. builds the seed's tables with `tracker.serialize.build_tracker_tables()` from `WWRandomizer.get_seed_plando()`: the
   `.aptww` plando in AP mode, and the equivalent plando built from the randomization results in offline mode
   (progress locations minus those banned by required bosses, entrances, chart mapping, required bosses). Both modes
   use the entrance options,
3. serializes them with `serialize_tracker_tables()` and writes them into the `tracker_data` reserve,
   failing the build if they don't fit.

## Code layout

| File | Contents |
|---|---|
| `asm/patches/tracker.asm` | The `tracker_data` (0x6000 bytes) and `tracker_state` (0x100 bytes) reserves, `.include "tracker/tracker.c"`, and the hooks |
| `asm/tracker/tracker.c` | Single translation unit that `#include`s every module, so the whole runtime is one assembled chunk |
| `asm/tracker/tracker_types.h` | `u8`/`u16`/`u32`, `bool`, `TRK_INLINE` (always_inline, since the game build uses `-fno-inline`) |
| `asm/tracker/tracker_mem.h` | All reads/writes of game memory and the tables go through these helpers |
| `asm/tracker/tracker_tables.[ch]` | Reader for the table format |
| `asm/tracker/tracker_save.[ch]` | Tracker save data (reset, seed tag, small-key counters, manual and visited bits) |
| `asm/tracker/tracker_detect.[ch]` | Check detection, manual marks, per-group counts |
| `asm/tracker/tracker_runtime.c` | Game hooks, entrance triggers, per-frame update |
| `asm/tracker/tracker_state.h` | Runtime state / debug struct in the `tracker_state` reserve |
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

## Hooks

| Where | What |
|---|---|
| 0x8005D618 in `dSv_info_c::init` (new game) | `misc_rando_features.asm` makes this call `init_save_with_tweaks`. `tracker.asm` redirects it to `tracker_init_save`, which resets the tracker save data and then calls `init_save_with_tweaks`. The reset comes first so small keys from the starting items are counted. |
| 0x8023502C in `dScnPly_Execute` (every gameplay frame, also with a menu open) | Replaces the call to `dKy_itudemo_se` with `tracker_on_frame`, which calls it and then `tracker_frame()` |
| `item_func_ptr` entries 0x13, 0x1D, 0x5B, 0x73, 0x77 (dungeon small keys) | `tweaks.add_in_game_tracker` points them at `tracker_<dungeon>_small_key_item_get_func`, which counts the key and calls the randomizer's `<dungeon>_small_key_item_get_func`. Both field pickups and Archipelago deliveries go through `execItemGet` and therefore through these. |

`tracker_frame()` does nothing until the tables are valid. It skips the title screen and file
select (stage `""`, `sea_T`, `Name`, like `TWWClient.py`'s `check_ingame`). In gameplay it:

1. validates the save data, resetting it if its layout version or seed tag doesn't match the
   tables. This covers a save from another seed or from before the tracker was enabled.
2. sets the visited bit of every entrance whose trigger matches the current stage name, room and
   spawn (`0x803C9D3C`, `0x803C9D46`, `0x803C9D44`). Triggers are checked every frame instead of on
   stage changes, so a visit is recorded again if a save without it is reloaded in the same place.
3. recomputes the totals and per-group checked counts in the runtime state.

## Save data

The tracker uses the 0x50 bytes of `dSv_reserve_c` at 0x803C532C (`memory-map.md`, section 1.4),
which are saved to the memory card:

| Offset | Size | Contents |
|---|---|---|
| 0x00 | 1 | layout version (1; 0 = never initialised) |
| 0x01 | 1 | flags (reserved) |
| 0x02 | 2 | seed tag (from the tables header) |
| 0x04 | 6 | small keys obtained: DRC, FW, TotG, ET, WT, spare |
| 0x10 | 48 | manual marks, bit *i* = location *i* |
| 0x40 | 8 | visited entrances, bit *i* = entrance *i* |

Bit *i* of a bitfield is in byte `i >> 3`, mask `1 << (i & 7)`.

## Detection

`tracker_is_auto_checked(i)` follows `TWWClient.py` exactly:

- CHART, BOCTO and EVENT test the location's byte and mask.
- CHEST, SWTCH and PCKUP test the stage's saved copy. If that bit isn't set and the current stage ID
  (0x803C53A4) is the location's stage, they test the same bit in the live copy at 0x803C5380.
- SPECL: Lenzo needs both bits 0x06 (0x07 implies it). The three letters need 0x03. Maggie's
  delivery reward counts once Moblin's Letter was owned (bit 15 of 0x803C4C98) and is no longer in
  the delivery bag. Ankle needs 0x803C523E & 0x40 and 0x803C5249 & 0x0F.
- NONE is never auto-checked.

`tracker_is_checked(i)` is auto-checked or manually marked. `tracker_toggle_manual(i)` refuses
(returns false) for auto-checked locations, so an auto-detected check stays locked (D8).
`tracker_group_counts(group, &checked, &total)` counts one group. The per-frame update also keeps
all of them in the runtime state.

## Runtime state

`TrkState` (`tracker_state.h`) at the `tracker_state` symbol isn't saved. It holds a magic
(`TRKS`), the frame counter, total/checked/auto-checked counts, the number of save resets, the
in-game flag, the current stage/room/spawn, the last entrance marked visited, and the checked count
of each group (by group index, up to 128 groups). The UI branches will read the counts from here,
and the Dolphin test reads it from RAM.

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

The tracker adds 0x10C4 bytes of code and read-only data, plus the 0x6000-byte table reserve and
the 0x100-byte state reserve. In total the custom code section grows by 0x71DC bytes (29,148), and
the game heap shrinks by the same amount.

## Tests

- `test/test_tracker_serialize.py`: round trip of every `.aptww` fixture through the serializer
  and the Python reader, size budget, and constants shared with the C code and `tracker.asm`.
- `test/test_tracker_c.py`: builds the C runtime for the host (`test/tracker_c_host.py` runs
  `make -C asm/tracker host` with `gcc` into a temp dir and loads it with ctypes) and checks the C
  reader returns exactly what the serializer wrote, for every fixture. Skipped when `make` or `gcc`
  is missing. CI (ubuntu) has both.

- `test/test_tracker_c_runtime.py`: detection of every location type against flags set the way
  `TWWClient.py` reads them, including the live-stage fallback, the chart mapping and all six
  special cases. It also covers manual marks, save reset on new game or another seed, small-key
  counters, entrance triggers (including the Cliff Plateau Isles inner cave) and per-group counts.
- `test/test_tracker_dolphin.py` (marker `dolphin`, needs flatpak Dolphin and `WW_ISO_PATH`):
  builds an AP ISO (`entrance_rando` fixture) with `--tracker --test sea,44,0`, which boots straight
  into gameplay with a new save. It then checks in RAM that the tables are loaded, the save data
  carries the seed tag, chest/switch/pickup/event flags written into RAM are detected (including
  the live copy), and a DRC small key sent through the AP give-item array is counted. It also
  checks that the Cliff Plateau inner-cave spawn marks its entrance visited and that a foreign seed
  tag resets the save data, and takes a screenshot. Set `WW_TRACKER_DOLPHIN_CACHE` to a directory
  to keep the built ISO and an in-game savestate between runs (about 20 s per run with the cache,
  about 90 s without).

Run them with the rest of the suite:

```sh
pytest test -m "not saving" -q
WW_ISO_PATH=/path/to/vanilla.iso WW_TRACKER_DOLPHIN_CACHE=/some/dir pytest test/test_tracker_dolphin.py -m dolphin -s
```

After changing anything under `asm/`, regenerate the patch diffs with `tools/devkitppc/assemble.sh`
(`toolchain.md`) and commit them; the ASM workflow checks they are reproducible.
