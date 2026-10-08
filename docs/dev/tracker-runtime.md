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
| `asm/patches/tracker.asm` | The `tracker_data` (0x6000 bytes), `tracker_state` (0x200 bytes) and `tracker_ui_state` reserves, `.include "tracker/tracker.c"`, and the hooks |
| `asm/tracker/tracker.c` | Single translation unit that `#include`s every module, so the whole runtime is one assembled chunk |
| `asm/tracker/tracker_types.h` | `u8`/`u16`/`u32`, `bool`, `TRK_INLINE` (always_inline, since the game build uses `-fno-inline`) |
| `asm/tracker/tracker_mem.h` | All reads/writes of game memory and the tables go through these helpers |
| `asm/tracker/tracker_tables.[ch]` | Reader for the table format |
| `asm/tracker/tracker_save.[ch]` | Tracker save data (reset, seed tag, small-key counters, manual and visited bits) |
| `asm/tracker/tracker_detect.[ch]` | Check detection, manual marks, per-group counts |
| `asm/tracker/tracker_items.[ch]` | Item counts for the logic from the ITEMS read descriptors (`tracker/items.py`) |
| `asm/tracker/tracker_runtime.c` | Game hooks, entrance triggers, per-frame update |
| `asm/tracker/tracker_state.h` | Runtime state / debug struct in the `tracker_state` reserve |
| `asm/tracker/tracker_logic.[ch]` | Logic bytecode interpreter, evaluation triggers, in-logic results |
| `asm/tracker/tracker_ui.[ch]` | Sea chart UI: hooks into the chart menu, counters and drawing; its state is in the `tracker_ui_state` reserve |
| `asm/tracker/tracker_host.c` | Host build only: mock RAM and the table pointer |
| `asm/tracker/Makefile` | Host build (`make -C asm/tracker host`) |
| `tracker/serialize.py` | Table format (documented at the top of the file), serializer and a Python reader |
| `tracker/logic_compiler.py` | Logic compiler, bytecode format and Python reference evaluator |

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
| 0x800C2E1C in `execItemGet` (every item get: pickups, chests, shops, NPCs, Archipelago deliveries) | Replaces the `bctrl` to the item's function with `bl tracker_exec_item_func` (`tracker.asm`), which calls it and then `tracker_on_item_get()` to request a logic evaluation |
| 0x8023502C in `dScnPly_Execute` (every gameplay frame, also with a menu open) | Replaces the call to `dKy_itudemo_se` with `tracker_on_frame`, which calls it and then `tracker_frame()` |
| 0x803923EC: the `FmapProc` pointer-to-member that `__sinit_d_menu_fmap_cpp` copies into `mainProc[0]` | `tracker_fmap_proc` (sea chart UI input), which calls `FmapProc` |
| 0x803925A0: `draw` in the vtable of `dDlst_FMAP_c` | `tracker_fmap_draw`, which calls `dDlst_FMAP_c::draw` and then draws the tracker over the chart |
| `item_func_ptr` entries 0x13, 0x1D, 0x5B, 0x73, 0x77 (dungeon small keys) | `tweaks.add_in_game_tracker` points them at `tracker_<dungeon>_small_key_item_get_func`, which counts the key and calls the randomizer's `<dungeon>_small_key_item_get_func`. Both field pickups and Archipelago deliveries go through `execItemGet` and therefore through these. |

`tracker_frame()` does nothing until the tables are valid. It skips the title screen and file
select (stage `""`, `sea_T`, `Name`, like `TWWClient.py`'s `check_ingame`). In gameplay it:

1. validates the save data, resetting it if its layout version or seed tag doesn't match the
   tables. This covers a save from another seed or from before the tracker was enabled.
2. sets the visited bit of every entrance whose trigger matches the current stage name, room and
   spawn (`0x803C9D3C`, `0x803C9D46`, `0x803C9D44`). Triggers are checked every frame instead of on
   stage changes, so a visit is recorded again if a save without it is reloaded in the same place.
3. recomputes the totals and per-group checked counts in the runtime state.

## Sea chart UI

`tracker_ui.c` draws on the sea chart (`dMenu_Fmap_c`, `memory-map.md` section 4). Both hooks are
data patches, so no vanilla code is changed:

- **Input:** `mainProc[0]` (`FmapProc`) is called once per frame while the normal sea chart is open
  and idle. It isn't called during the open and close animations, on the Y compare page
  (`mainProc[1]`), or in the warp, wallpaper and fishman modes. `tracker_fmap_proc` records the
  frame and the view (`mFmapProcIdx`), then calls `FmapProc`.
- **Drawing:** `dDlst_FMAP_c::draw` is the 2D display-list callback that draws the chart.
  `tracker_fmap_draw` calls it, then draws the tracker on top. It only draws if
  `tracker_fmap_proc` ran in this frame or the one before, and the chart's view is one the tracker
  handles. Everything else (animations, the compare page, warp mode) stays vanilla. The
  `dMenu_Fmap_c` is found from the display-list object (`fmapDl` is at +0x1C).

Drawing uses the current graf port (`J2DOrthoGraph`, 640x480 screen space) and the chart's message
font (`mFont`):

- Text: `font->setGX()` (vtable +0x0C), `JUTFont::setCharColor`, then
  `JUTFont::drawString_size_scale(x, y, w, h, str, len, true)`. `y` is the baseline. Text width comes
  from `getWidthEntry` (vtable +0x2C) scaled by `w / getCellWidth()` (vtable +0x30).
- Boxes: `J2DFillBox(x, y, w, h, color)`. It **doesn't** set up the GX state for untextured quads,
  so a box drawn after text comes out as garbage. `trk_fill_box` calls `J2DOrthoGraph::setPort()`
  (which runs `setup2D`) first. The draw hook ends with `setPort()` too.
- `JUtility::TColor` arguments are declared as a 4-byte struct passed by value. GCC passes it as a
  pointer to a copy, the same as MWCC.

Layout constants (`TRK_GRID_*`, `TRK_CELL_*`) are in screen space and were measured on Dolphin
screenshots. A 640x528 screenshot shows screen-space point (x, y) at about (0.97x + 9, 0.975y + 19).

**World view** (`SelectGrid`): every sea square with tracked locations shows a counter in its top
left corner, and the empty strip of the salvage panel shows `Checked n/total`. A counter is the
remaining (unchecked) count, or `available/remaining` once logic is available, in a light box:

| Colour | Status (`enum TrkUiStatus`) |
|---|---|
| grey | everything checked |
| blue (#2929CC) | some unchecked location is in logic |
| red (#CC2929) | nothing unchecked is in logic |
| dark brown | logic not available (until the logic runtime lands) |

**Square view** (`ZoomGridLv1Proc`, after A on a square): if the square has tracked locations, a
panel over the zoomed map lists them: the square's name and counter, then one row per location with
a checkbox and the name in its status colour (struck through and grey once checked), then a hint
line and the position in the list. Fifteen rows fit; the list scrolls with the selection.

| Input (square view) | Action |
|---|---|
| Main stick up/down | Select. Holding repeats after 14 frames, then every 4. A fresh push wraps around |
| X | Toggle the selected location's manual mark (save data). Refused for auto-detected checks: the row flashes red |

**Info lines** (`tracker_ui_info_lines()`) follow a location list, under a separator, and take
some of its 15 rows (at most 4):

- A square's tracked (randomized) entrances on its island, or the entrances nested in a list-page
  group (a dungeon's miniboss and boss doors, an inner cave's entrance in its cave):
  `Outset Island Cave -> ?` until the visited bit is set, then `Outset Island Cave -> Gohma Boss Arena`.
- On a square with a tracked sunken treasure, the chart that leads there in this seed:
  `Chart: not owned` until that chart's owned bit (GetMap, 0x803C4CDC) is set, then its name, for
  example `Chart: Treasure Chart 17`.

A square without tracked locations still gets a square view panel if it has info lines. Lines too
wide for the panel are drawn at a smaller size.

**List page** (Z on the world or square view): everything that isn't on a sea square. That's
every group with tracked locations whose ID is 50 or more: dungeons, Hyrule, Ganon's Tower, Mailbox,
The Great Sea, and caves whose entrances are randomized. Each row has the group's name and counter.
A opens a group's location list, which works like a square's. For a group behind a tracked
(randomized) entrance, a footer line shows `Entrance: Unknown entrance` until the player has been
through it, and then the entrance's name (`tracker_ui_group_entrance()`, which prefers the entrance
into the group's own exit over, say, a boss door into the dungeon's boss arena).

| Input | World view | Square view | List page | Group list (from the list page) |
|---|---|---|---|---|
| Z | open list page | open list page | close | close |
| Main stick | vanilla (cursor) | select location | select group | select location |
| X | - | toggle mark | - | toggle mark |
| A | vanilla (zoom) | vanilla (detail zoom) | open group | - |
| B | vanilla (close chart) | vanilla (zoom out) | close page | back to list page |

While a page is shown, `FmapProc` isn't called at all, so none of the chart's own buttons
(B, D-pad Left/Down, A, Y) do anything until the page is closed. The page is also closed when the
chart is reopened. `tracker_ui_input()` is the whole state machine. It takes the view, the square's
group, abstract buttons and the stick value, and returns whether the input was consumed, so it's
host-testable.

Vanilla doesn't read the main stick or X in square view, so both work without blocking any vanilla
input. A, B and Y keep their vanilla meanings. The input is read from `g_mDoCPd_cpadInfo[0].mButtonTrig`
(0x803A4E22, X = 0x0040) and the raw stick Y of `JUTGamePad::mPadStatus[0]` (0x803ED81B).
`tracker_ui_list_input()` is host-testable: it takes abstract buttons (`TRK_BTN_*`) and the stick
value. The selection is kept per group and reset when another group's list is shown.

`tracker_ui_group_counter()` computes a group's counter. Logic comes from `trk_ui_location_logic()`,
which returns "unknown" until the logic runtime is wired in.

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

## Logic

`tweaks.add_in_game_tracker` compiles the seed's logic with `tracker/logic_compiler.py` from the same
`logic/item_locations.txt` and `logic/macros.txt` the offline fill uses. Options, Tuner logic, sword mode, starting
items, Start With dungeon items, the chart mapping and the required bosses are resolved at patch time; the bytecode
only reads items, the small-keys-obtained counters, visited entrances and checked locations. Following the website:
what's behind a randomized entrance is out of logic until that entrance is visited, mail letters and Knight's Crest
farming count another location once it's checked or in logic, and required bosses count once their location is
checked or in logic.

The bytecode is straight-line postfix code: shared subexpressions (macros used several times) are evaluated first
into result slots, then one slot per tracked location, so an evaluation is one pass with a small stack and no
recursion. `evaluate_bytecode` is the Python reference. Sizes: 1.5-4.1 KB for the fixtures and all-options offline
seeds (budget 8 KB, tested), maximum stack depth 33 (limit 64).

### Evaluation at runtime

`asm/tracker/tracker_logic.c` runs the bytecode in one pass (item counts are read once per evaluation through the
ITEMS descriptors) and stores each location's result as a bit in `TrkState.in_logic`. Malformed bytecode is
detected (bounds, stack, slot order) and makes the results unknown (`logic_status` = error) instead of crashing.
Following D7 it runs on events, not every frame:

- when the sea chart opens (`tracker_fmap_proc` sees the chart's first frame),
- 30 frames after an item get (the `execItemGet` hook), so that the magic meter, which the HUD fills gradually, is
  counted,
- on the next frame when the checked count, the visited entrances or the save data (reset) change, and on the first
  gameplay frame.

`tracker_is_in_logic(i)` and `tracker_logic_available()` are the API for the UI. The per-frame update also keeps
the number of unchecked in-logic locations per group (`group_available`) and in total (`num_in_logic`).

Measured in Dolphin (`test_tracker_logic_dolphin.py`, progression_all fixture: 313 locations, 3.8 KB of bytecode):
one evaluation takes about 11,600 time base ticks, **0.29 ms** (1.7% of a frame).

## Runtime state

`TrkState` (`tracker_state.h`) at the `tracker_state` symbol isn't saved. It holds a magic
(`TRKS`), the frame counter, total/checked/auto-checked counts, the number of save resets, the
in-game flag, the current stage/room/spawn, the last entrance marked visited, and the checked count
of each group (by group index, up to 128 groups), then the logic's results: evaluation count and duration,
status, the in-logic bit of each location and the in-logic count of each group. The UI reads the counts from here,
and the Dolphin tests read it from RAM.

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
| LOGIC | bytes | Compiled logic bytecode (`tracker/logic_compiler.py` documents the opcodes) |
| ITEMS | 8 B | How to read each logic item's count from game memory (`tracker/items.py`) |

Locations are ordered by group, so each group's locations are contiguous. The C reader checks the
magic and format version (`trk_tables_valid`); bump `FORMAT_VERSION` and `TRK_FORMAT_VERSION`
together on any layout change. `test_tracker_serialize.py` checks the Python and C constants agree.

Sizes (bytes) for the test fixtures: 5.7-11.3 KB; the worst case (all 320 locations and every
entrance tracked) is 14.1 KB. About 60% is strings. The 24 KB reserve leaves room for the logic
bytecode.

## Size in main.dol

The tracker adds 0x42BC bytes of code and read-only data (about 0x2348 of it for the sea chart UI and 0xD00 for the
logic interpreter), plus the 0x6000-byte table reserve, the 0x200-byte state reserve and the 0x40-byte UI state
reserve. In total the custom code section grows by about 0xA4FC bytes (42,236), and the game heap shrinks by the same
amount.

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
- `test/test_tracker_logic_c.py`: the C interpreter gives the same results as the Python reference for 1000
  random states (items, stage, manual marks, visited entrances) per `.aptww` fixture and for an all-options offline
  seed; evaluation triggers; in-logic counts; no logic and corrupted bytecode.
  `test/test_tracker_logic_dolphin.py` (marker `dolphin`) checks evaluations after loading, after item gets and on
  opening the chart against the reference for the state in RAM, and prints the evaluation time.
- `test/test_tracker_items.py`: every logic item has a read descriptor, the C reader agrees with the Python
  reference on random memory, and counts for memory as the item get functions leave it.
  `test/test_tracker_items_dolphin.py` (marker `dolphin`) gives items through the Archipelago give-item array in
  Dolphin and checks each descriptor's count.
- `test/test_tracker_dolphin.py` (marker `dolphin`, needs flatpak Dolphin and `WW_ISO_PATH`):
  builds an AP ISO (`entrance_rando` fixture) with `--tracker --test sea,44,0`, which boots straight
  into gameplay with a new save. It then checks in RAM that the tables are loaded, the save data
  carries the seed tag, chest/switch/pickup/event flags written into RAM are detected (including
  the live copy), and a DRC small key sent through the AP give-item array is counted. It also
  checks that the Cliff Plateau inner-cave spawn marks its entrance visited and that a foreign seed
  tag resets the save data, and takes a screenshot. Set `WW_TRACKER_DOLPHIN_CACHE` to a directory
  to keep the built ISO and an in-game savestate between runs (about 20 s per run with the cache,
  about 90 s without).

- `test/test_tracker_ui.py`: the sea chart UI's counters (`tracker_ui_group_counter`) and the
  location list's input (selection, repeat, wrap, scrolling, marking, refused toggles), the list page's
  groups and navigation, which entrance a group shows, and the entrance and chart info lines, on the
  host.
- `test/test_tracker_ui_dolphin.py` (marker `dolphin`): builds the `progression_all` fixture, opens the
  sea chart with D-pad Up and checks through `tracker_ui_state` in RAM that the tracker draws on the
  world view, follows manual marks and stops drawing after the chart is closed, and that A/B/D-pad
  Down still work. In square view it selects with the main stick, marks and unmarks with X (checking
  the bit in the save region at 0x803C533C, which is written to the memory card with the save) and
  checks that an auto-detected location can't be unmarked. With the `entrance_rando` fixture it opens
  the list page with Z, checks that D-pad Down and B don't reach the chart, opens Dragon Roost
  Cavern after marking its entrance visited, marks a location there with X, and closes everything
  again. The reveal tests open Outset's square view in the `entrance_rando` and
  `charts_required_bosses` seeds before and after setting an entrance's visited bit and the chart's
  owned bit, for screenshots. Screenshots are printed with `-s`; set
  `WW_TRACKER_SCREENSHOT_DIR` to also copy them to a directory.

- `test/test_tracker_save_dolphin.py` (marker `dolphin`): end-to-end save persistence with the game's
  own save. Session 1 boots the `entrance_rando` `--test` ISO (new game), marks a location through
  the Z page, gets a DRC small key through the Archipelago give-item array and visits the Cliff
  Plateau Isles inner cave's exit. It then saves through the pause menu (Quest Status, Save; the
  memory card starts empty, so it also confirms creating the file). Session 2 boots an ISO of the
  same seed *without* `--test` in the same Dolphin user directory, so the same GCI-folder card is
  used. It loads Quest Log 1 from the file select screen and checks that the 0x50-byte save region is
  byte-identical to what was saved, that the mark, key count and visited bit are set, that loading
  didn't reset the data, and that the mark shows on the chart. `dSv_info_c::init` also runs once at
  boot, so the tracker save data is reset (`save_resets` = 1) before the title screen. That's
  harmless, because loading a file restores it.

Run them with the rest of the suite:

```sh
pytest test -m "not saving" -q
WW_ISO_PATH=/path/to/vanilla.iso WW_TRACKER_DOLPHIN_CACHE=/some/dir pytest test/test_tracker_dolphin.py -m dolphin -s
```

After changing anything under `asm/`, regenerate the patch diffs with `tools/devkitppc/assemble.sh`
(`toolchain.md`) and commit them; the ASM workflow checks they are reproducible.
