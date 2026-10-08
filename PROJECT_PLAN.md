# wwrando-tracking — Project Plan / Implementation Prompt

> This document is both the project brief and the prompt used to drive implementation.
> Hand it to an agent (Claude Code) with the instruction: **"Read PROJECT_PLAN.md and produce a detailed
> implementation plan. Ask me clarifying questions while designing the plan before writing code."**

---

## 1. Goal

Build a single Wind Waker randomizer ("wwrando-tracking") that:

1. Patches a vanilla NTSC-U Wind Waker ISO into a randomized ISO, in **either** of two modes:
   - **Archipelago mode** — user supplies a `.aptww` file; behaves exactly like tanjo3's AP randomizer.
   - **Offline mode** — no `.aptww`; generates a solo seed locally, with **all options and features the
     Archipelago TWW world supports**, fully self-contained (no Archipelago install, no server, no network).
2. Embeds an **in-game tracker** into the patched ISO (both modes) that replicates the core of the
   WWRando-APTracker website inside the game's sea chart: per-location checked state, auto-detection,
   manual toggling, remaining counts, in-logic colouring, entrance and treasure-chart tracking.

Audience: the owner and friends. Dolphin on Linux is the target platform.

---

## 2. Source folders (all under `/media/storage/Downloads/Randomizer changes/`)

| Folder | What it is | Role in this project |
|---|---|---|
| `wwrando-tracking/` | Our repo. Remote `origin` = `github.com/thesword1/wwrando-tracking`. Currently LagoLunatic upstream v1.10.0 (`master` @ 9775811). | **All final code lives here.** |
| `wwrando-archipelago-branch/` | tanjo3's fork (`github.com/tanjo3/wwrando`, branch `archipelago`), v2.5.2 @ 054d4f3. AP-only: requires a `.aptww` file (`wwr_ui/randomizer_window.py`, `tweaks.apply_*_for_archipelago`). | **New base** for `wwrando-tracking`. |
| `wwrando-master (Archipelago)/`, `wwrando-master (No Archipelago)/` | Byte-identical to each other and to current `wwrando-tracking` (upstream v1.10.0). | Reference only (pre-AP standalone randomizer). Effectively superseded. |
| `Archipelago-main/worlds/tww/` | The TWW APWorld: `Options.py`, `Locations.py` (location → stage/flag data), `Rules.py`, `Macros.py`, `Items.py`, `Presets.py`, `TWWClient.py` (Dolphin memory reading of check flags), `randomizers/`. | Reference for options, logic, fill, and **how to detect checked locations from game memory**. Must not become a runtime dependency. |
| `WWRando-APTracker-main/` | Owner's website tracker (JS/React). `src/services/` (logic-loader, logic-calculation, boolean-expression, entrance-auto-tracker, locations, macros, settings), `src/data/*.json` (islands, charts, entrances, flags, options…). | Reference for tracker UX, location grouping by island/sea-chart square, logic evaluation approach, entrance/chart tracking. |

Verified facts:
- `wwrando-tracking` HEAD is **not** an ancestor of tanjo3 `archipelago` → the base switch cannot fast-forward.
- Dolphin is installed as a flatpak: `org.DolphinEmu.dolphin-emu` (2606, stable).
- Test ISO: `/media/storage/Documents/Games/Emulator/Rom/Gamecube/The Legend of Zelda - Wind Waker/Legend of Zelda, The - The Wind Waker (USA).iso` (never commit it, never upload it, never copy it into the repo).

---

## 3. Requirements

### A. Base & randomizer modes
- **A1.** Reset `wwrando-tracking` onto tanjo3 `archipelago` (v2.5.2). Add `upstream` remote → `https://github.com/tanjo3/wwrando` so future tanjo3 updates can be merged.
- **A2. Archipelago mode:** unchanged behaviour when a `.aptww` is supplied. The `.aptww` format is **not modified in any way**.
- **A3. Offline mode:** when no `.aptww` is supplied, the UI exposes every option the TWW APWorld supports (including those absent from wwrando 1.10.0) and generates a beatable solo seed locally.
  - Self-contained: port/embed the APWorld's options, location data, rules/macros and fill behaviour into wwrando's own code. Archipelago may be used as a *reference* and in tests for parity checks, never as a runtime dependency.
  - Items for the solo player are placed directly in the ISO (no server item delivery).
  - Offline mode needs no hints (hints are out of scope for now).
  - Spoiler log and permalink/seed sharing for offline seeds.
- **A4. Version:** keep tanjo3's version with a `-tracking` suffix (e.g. `2.5.2-tracking`). Credit LagoLunatic and tanjo3 in the about box and link this repo.

### B. In-game tracker (both modes)
- **B1. Option:** "In-game tracker" checkbox in the randomizer UI, **on by default**. It is a local randomizer setting only — never part of the APWorld, never in the `.aptww`. Works for AP and offline seeds.
- **B2. Option-aware location set (must-have):** only locations that actually exist in this seed's settings are tracked/shown (e.g. Battlesquid minigame hidden when that location type is off). Resolved at patch time and baked into the ISO.
- **B3. Sea chart overview:** each of the 49 sea chart squares shows its remaining-location count (and colour state).
- **B4. Square detail view:** when a square is selected/expanded (quadrant/zoomed view), list its **individual locations** with their state.
- **B5. Auto-detection:** locations are marked checked automatically by reading the game's own chest / event / item-get / stage flags (mapping derived from APWorld `Locations.py` / `TWWClient.py`).
- **B6. Manual toggle:** player can mark individual locations checked/unchecked (e.g. auction items, rupee they don't want). An auto-detected check may stay locked as checked; manual marks apply to locations not yet auto-detected. Manual state persists in the save file.
- **B7. Counts:** remaining / checked totals per square and overall.
- **B8. In-logic colouring (desired must-have, see §4):** locations coloured by whether they're reachable with current inventory. **Re-evaluated on events** (item obtained, sea chart opened), not continuously.
- **B9. Entrance tracking (if feasible):** for randomized entrances, show where an entrance leads **only after the player has gone through it**.
- **B10. Treasure chart mapping (if feasible):** show a chart's target square **only once the player owns that chart**.
- **B11. No item spoilers, ever:** the tracker shows only checked/unchecked/in-logic state, never what item is at a location.
- Out of scope (note for later): notes; hints (would only matter for AP).
- Triforce shard count on the Quest Status screen's Triforce (`n/8`): added later at the owner's request, part of the in-game tracker.

### C. Engineering process
- **C1. Trunk-based Git:** trunk = `master`. Every change on a short-lived `feature/<name>` (or `fix/`, `docs/`, `ci/`) branch → PR into `master` with a description of what/why → agent merges its own PRs (GitHub doesn't allow self-approval; merge without required review). Branch protection may be added later. Commit messages and PR bodies use the attribution lines configured in the session.
- **C2. CHANGELOG.md** entry per feature.
- **C3. CI:** GitHub Actions (ubuntu) running the pytest suite + new tests. No ISO in CI — ISO-dependent tests are skipped there.
- **C4. Local integration testing on Linux:** subagents may build test ISOs and launch Dolphin (flatpak) to verify behaviour with screenshots. Prefer Dolphin features that allow automation (e.g. `--exec`, `--batch`, save states, memory inspection via the Dolphin memory engine / Python bindings) over manual play.
- **C5. Autonomy:** once the plan is approved and test infrastructure exists, proceed through all phases without stopping for review; report at the end (and surface blockers if something is truly impossible).

---

## 4. Feasibility notes (from initial analysis)

| Item | Assessment |
|---|---|
| A1–A2 | Straightforward. Base switch needs a history reset (see Phase 0). |
| A3 offline parity | **Largest backend task.** tanjo3's branch is AP-only; standalone code from master still exists in history but lacks AP options/logic. Port APWorld options/rules/fill into wwrando. Parity tests against the APWorld are the safety net. |
| B2, B5, B7 | Feasible. Location table + flag mapping generated at patch time; ASM reads flags. Existing `asm/` assembler + patch system supports custom code. |
| B3, B4, B6 | **Hard but likely possible.** Requires custom ASM hooking the sea chart (`dMenu_Fmap`-family) draw and input code; must find free memory/space for new code, textures/text, and save-file bits. Riskiest UI work. Fallback ladder: custom icons/numbers → text overlays (e.g. "3/5") → text in the existing island-name/description box. |
| B8 in-logic | **Viable in event-driven form.** At patch time, take every active location's requirement, resolve all options and the seed's (known) entrance mapping, flatten macros, and compile to a compact bytecode (AND/OR/HAS item[count]/CAN_REACH). An ASM interpreter evaluates all ~hundreds of locations against inventory when an item is obtained or the chart opens — cheap in practice. Spoiler caveat: logic using the true entrance mapping could leak entrance info; default to treating locations behind not-yet-visited randomized entrances as "unknown / not in logic" (mirrors the website tracker). |
| B9, B10 | Feasible once B3/B4 exist: data known at patch time; reveal gated on "entrance visited" / "chart owned" flags. |

---

## 5. Suggested phases & branches

Each phase = one or more `feature/*` PRs. Planning agent should refine and may reorder.

- **Phase 0 — Base & repo setup**
  - Tag old trunk `legacy/1.10.0` and push the tag.
  - Add `upstream` remote (tanjo3). Reset `master` to `upstream/archipelago` (force-push trunk once, explicitly authorized by owner as "reset"). Then commit this `PROJECT_PLAN.md` via `docs/project-plan` PR.
  - `feature/version-tracking-suffix`: `-tracking` version, credits/about box.
  - `ci/github-actions`: pytest on ubuntu.
- **Phase 1 — Test & tooling infrastructure**
  - Headless "patch ISO from CLI" path usable by tests/agents (ISO path via env var).
  - Dolphin (flatpak) launch helper + screenshot + memory-inspection helper for integration checks on Linux.
- **Phase 2 — Offline mode parity**
  - Inventory every APWorld option vs. wwrando options (subagent research task) → gap list.
  - Port options to UI, logic/macros/rules, location set, fill; spoiler log; permalink.
  - Parity tests: same options → same set of active locations / beatable seeds; compare against APWorld in tests only.
- **Phase 3 — Tracker data layer (patch time)**
  - Tracker option (B1). Generate per-seed tables: active locations → sea chart square, flag source, display name; entrance & chart data; compiled logic bytecode. Write into ISO.
- **Phase 4 — In-game runtime (ASM)**
  - Save-file storage for manual marks / visited entrances.
  - Flag reader for auto-detection; counts.
  - Sea chart overview counts → square detail list → manual toggle input.
  - Logic bytecode interpreter + event hooks (item get, chart open).
  - Entrance reveal + treasure chart reveal.
- **Phase 5 — Polish & docs**
  - README/docs for both modes, CHANGELOG, release build (Linux first; existing `build.py`/`wwrando.spec`), then Windows (`chore/windows-build`).
  - No new hints in either mode and none on the tracker (D14). Archipelago `!hint` results on the tracker would need a custom TWW client; noted for the future.

---

## 6. How to use subagents

- **Research (read-only, parallel):** APWorld options/logic/fill inventory; APWorld check-flag mapping (`Locations.py`, `TWWClient.py`); sea chart menu code (decomp / existing `asm/` patches / tanjo3 changes) and free memory regions; website tracker's grouping/logic/entrance/chart behaviour.
- **Implementation:** one feature branch per subagent where tasks are independent; use git worktrees to avoid collisions.
- **Verification:** a testing subagent builds ISOs and drives Dolphin, reporting screenshots and pass/fail.

---

## 7. Instructions for the planning agent

1. Read this document, then do **targeted** exploration (via subagents) of the folders in §2.
2. **Ask the owner clarifying questions while designing the plan** — especially on: sea chart UI layout/controls for the detail view and toggle button, colour scheme, which tracker behaviours from the website to mirror exactly, and anything in §4 that turns out harder than expected.
3. Produce a phased plan with concrete branches, files to touch, tests, and acceptance criteria per phase.
4. If anything is impossible or unreasonably costly, say so and propose the nearest viable alternative before starting.
5. Never commit or upload the ISO or any copyrighted game files/extracted assets.

---

# Part II — Detailed Implementation Plan (v1)

## 8. Decisions log

| # | Decision | Source |
|---|---|---|
| D1 | Base = tanjo3 `archipelago` @ 054d4f3 (v2.5.2); `upstream` remote = tanjo3. | Owner |
| D2 | Offline mode revives **wwrando's own** txt logic + fill (`logic/`, `randomizers/items.py`, `entrances.py`, `charts.py`), extended for AP-only options. The *same* logic files feed the tracker's logic compiler (single source of truth). APWorld = reference/tests only. | Owner |
| D3 | Offline output is a `Plando`-equivalent produced locally, so the existing save path is reused. AP-only runtime patches (item-pickup skip in `d_a_demo_item`, give-item queue) are **disabled in offline mode** so items are received on pickup. | Research |
| D4 | Tracker shows only **progress** locations of the seed; non-required-boss dungeons hidden. AP mode: active set = `plando.Locations` keys. Offline: logic's progress locations. | Owner |
| D5 | Sea chart overview: per-square counter `available/remaining`. Square detail (zoomed) view: per-location list. Dungeons + non-island zones (Mailbox, Great Sea misc, Hyrule, Ganon's Tower, dungeon/cave interiors) on a **separate list page** opened from the sea chart. | Owner |
| D6 | Colours mirror the website: blue = in logic (progress), red = out of logic, grey/strikethrough-style = checked; counter: all checked / none in logic / some in logic. | Website parity (default) |
| D7 | Logic re-evaluated on events (item obtained, chart/menu opened), not per frame. Entrance-dependent requirements use "entrance visited" bits (website behaviour) → no entrance spoilers. | Owner + default |
| D8 | Manual toggle: player may mark an unchecked location checked (and unmark own manual marks). Auto-detected checks are locked as checked. Persisted in save. | Owner |
| D9 | Tracker runtime written in **C**, compiled with devkitPPC through `asm/assemble.py` `.include "*.c"`, hooked into `dMenu_Fmap_c` and draw via `J2DPrint`/`JUTFont`. Same C core also compiled for host (gcc) for unit tests. | Research |
| D10 | Tracker option: local randomizer setting, default on, not in `.aptww`; for permalinks it's encoded in our local settings only. | Owner |
| D12 | Small-key logic uses exact in-game keys-obtained counters per dungeon, not inference. | Owner |
| D13 | Controls: X = toggle mark, main stick = select location, Z = list page. Save storage at 0x803C532C (80 bytes, zeroed at new game). See docs/dev/memory-map.md. | Research |
| D11 | Hints: out of scope. Triforce-count icon: out of scope at first, later added (`n/8` on the Quest Status screen, gated on the In-Game Tracker option). | Owner |
| D14 | No new hints in either mode: offline seeds get no NPC hints, and the tracker shows no hints (Archipelago seeds keep upstream's fishmen/Hoho/KoRL hints from the `.aptww` options). Showing Archipelago server hints (`!hint`) on the tracker isn't possible with the stock Archipelago TWW client: the game has no network access, and the client (`worlds/tww/TWWClient.py` in Archipelago core) never writes hint data into game RAM. It would need a modified client/apworld, installed by every player, that writes hinted location IDs into a reserved RAM array (like the give-item array at 0x803FE87C) for the tracker to read. Out of scope; see §10 Phase 5 notes for future. | Owner |

## 9. Research findings that shape the plan (summary)

- **AP branch pipeline:** `.aptww` = zip → `plando` → base64 YAML (Version, Seed, Slot, Name, Options as ints, Required Bosses, Locations{name→{player,name,game,classification}}, Entrances, Charts[49]). Charts/bosses/entrances/items steps `return` early after applying plando; standalone fill code is dead *and* broken (`options.keylunacy` no longer exists — `logic/logic.py:562`, `randomizers/items.py:72,684`, `hints.py`, `extra_starting_items.py:110`, `test/test_helpers.py:57`). CLI ignores plando (`wwrando.py:232-238`); logs forced off (`randomizer.py:131`).
- **Option gaps for offline:** 6-mode dungeon item placement (`randomize_smallkeys/bigkeys/mapcompass`: startwith/vanilla/dungeon/any_dungeon/local/keylunacy), `swords_optional` in logic, `enable_tuner_logic`, `included/excluded_dungeons` for required bosses, start-inventory, inner-cave auto-disable rule. `logic/item_locations.txt` is identical to upstream; macros differ only by "X Capacity Upgrade" renames.
- **Check detection** (from `TWWClient.py`): saved stage info `0x803C4F88 + 0x24*stage` (chests +0x00 u32, switches +0x04 10 bytes big-endian-bit-order, pickups +0x14 u32); live stage info `0x803C5380` when current stage id (`0x803C53A4`) matches; charts/salvage bitfield `0x803C4CFC`; Big Octo u16 per sea room `0x803C51C8+2*room`; event bytes `0x803C522C..`; 6 special cases (Lenzo, Maggie, 3 letters, Ankle). 321 locations.
- **Sea squares:** 1..49 row-major (1 = Forsaken Fortress Sector), `sector_x=(n-1)%7`, `sector_y=(n-1)//7`.
- **ASM infra:** patches → precompiled diffs in `asm/patch_diffs/`; custom code in DOL Text2 at 0x803FCFA8 (~8.5 KB used, growth eats arena); patch-time tables via `.space` + `self.dol.write_data` (`archipelago_charts_mapping` pattern); vanilla symbols must be added to `asm/linker.ld`; `framework.map` in ISO provides addresses. No existing custom text drawing.
- **Save space for tracker bits:** event-bit area ends near `0x803C532B`; ~0x50 bytes `0x803C532C–0x803C537F` look unused → **must verify** against zeldaret/tww `d_save.h` before use.
- **Tooling gaps:** `gclib/` submodule uninitialised in the tanjo3 checkout; devkitPPC not installed.

## 10. Phases, branches, deliverables, acceptance criteria

Branch naming: `feature/*`, `fix/*`, `ci/*`, `docs/*`, `chore/*`, `tooling/*`. One PR per branch, squash-merge into `master`, CHANGELOG entry per feature PR. Agent merges its own PRs after CI is green.

### Phase 0 — Repo base (sequential)
| Branch / step | Work | Acceptance |
|---|---|---|
| (direct) | Tag `legacy/1.10.0` at current master; add `upstream`; reset `master` to `upstream/archipelago`; `git submodule update --init`; single authorized force-push of `master`. | `origin/master` == 054d4f3, tag pushed. |
| `docs/project-plan` | Commit this file. | Merged. |
| `chore/version-and-credits` | `version.txt` → `2.5.2-tracking`; about box credits LagoLunatic, tanjo3, links repo. | UI shows new version. |
| `ci/github-actions` | Ubuntu workflow: checkout w/ submodules, Python per `requirements.txt` (headless Qt via `QT_QPA_PLATFORM=offscreen`), `pytest`; ISO tests skipped when `WW_ISO_PATH` unset. Second job (later): devkitPPC container (`devkitpro/devkitppc`) verifies `asm/assemble.py` reproduces committed `patch_diffs`. | Green on master. |

### Phase 1 — Tooling & test infrastructure
| Branch | Work | Acceptance |
|---|---|---|
| `fix/cli-headless-randomize` | CLI accepts `--aptww <file>`, `--offline`, `--tracker/--no-tracker`, ISO in/out paths; re-enable logs for offline. | `python wwrando.py --aptww fx.aptww ...` produces an ISO. |
| `tooling/devkitppc` | `tools/setup_devkitppc.sh` (devkitPro pacman on Fedora/Nobara, Docker fallback); docs. Verify regenerated diffs are byte-identical. | Rebuilt diffs == committed. |
| `tooling/aptww-fixtures` | Dev-only script using `Archipelago-main` `Generate.py` to make small `.aptww` fixtures across option sets; commit fixtures (no game data). | Fixtures load via `read_ap_plando_file`. |
| `tooling/dolphin-harness` | `tools/dolphin/`: launch flatpak Dolphin with isolated user dir (scratch), `--exec`/`--batch`; Pipe input backend for scripted controller input; `dolphin-memory-engine` (Python) to read/write RAM; screenshot capture; savestate load/save. Smoke test: boot patched ISO, reach title/file select, read a known address. | Smoke test passes locally. |
| `docs/memory-map` | Verify free save bytes against zeldaret/tww `d_save.h`; document all addresses used by tracker in `docs/dev/memory-map.md`. | Confirmed reserved region (or alternative chosen). |

### Phase 2 — Offline mode parity
| Branch | Work | Acceptance |
|---|---|---|
| `feature/offline-mode-switch` | Randomizer mode: AP when `.aptww` supplied, otherwise offline. Gate the early `return`s on mode; offline-only disables `archipelago.asm` pickup-skip/give-queue behaviour (split patch or runtime flag). Offline UI shows all options; AP mode greys them out (read from plando). | Offline seed with defaults builds; items obtained on pickup in Dolphin. |
| `feature/offline-dungeon-item-modes` | Replace `keylunacy` with the 3 × 6-mode options in `logic.py`, `items.py`, extra starting items, hints refs, tests. | Fill respects each mode across seed matrix. |
| `feature/offline-swords-optional` | Logic/macros/fill for `swords_optional`. | Beatable seeds; swordless paths valid. |
| `feature/offline-tuner-logic` | `enable_tuner_logic` option + macros (mirror AP `Macros.py:133`). | Matches AP rule set in tests. |
| `feature/offline-required-bosses-filters` | `included/excluded_dungeons` for required bosses. | Respected over 200 seeds. |
| `feature/offline-item-pool-parity` | Item pool & "Capacity Upgrade" names consistent with AP; starting inventory option; inner-cave auto-disable rule. | Pool tests pass. |
| `feature/offline-spoiler-permalink` | Spoiler log + permalink including new options; tracker flag outside AP-shared data. | Round-trip permalink tests. |
| `test/offline-parity` | Parametrized tests: for option matrix compare offline progress-location set vs APWorld classification (APWorld imported in tests only, optional dependency) + N-seed beatability. | Parity within documented exceptions. |

### Phase 3 — Tracker data layer (Python, patch time)
| Branch | Work | Acceptance |
|---|---|---|
| `feature/tracker-option` | Checkbox, default on, local only. | Off → no tracker patches applied. |
| `feature/tracker-location-table` | `tracker/locations.py`: per location → group (square 1-49 or list-page group: each dungeon, Mailbox, Great Sea, Hyrule, Ganon's Tower, inner caves), detection descriptor (type, stage, bit, address, special id) ported from APWorld `Locations.py` (MIT, attributed); active filter per D4; sunken treasure → square via chart mapping. | All 321 mapped; unit tests. |
| `feature/tracker-logic-compiler` | `tracker/logic_compiler.py`: resolve `Option` terms, starting items, swordless; inline `Can Access Item Location`; macros → shared subroutines (memoized per evaluation); entrance macros → `VISITED(entrance)` AND reachability; key-logic: small-key requirements read a per-dungeon **keys-obtained counter** maintained in-game (exact, all modes); startwith mode resolves to TRUE at compile time. Emit compact bytecode (`TRUE/FALSE/AND n/OR n/HAS item cnt/VISITED e/CHECKED loc/CALL macro`). Python reference evaluator. | Reference evaluator == `Logic` reachability for random inventories (property tests); bytecode size budget ≤ 24 KB. |
| `feature/tracker-item-map` | Map each logic item name → inventory read descriptor (slot byte, bitfield, counter, progressive level, songs, pearls, shards, charts owned, tingle statues, keys per dungeon). | Covered by host C tests. |
| `feature/tracker-entrance-chart-data` | Entrance table (entrance id → stage names that mark it visited, display names, nesting) from `entrances.py` tables; chart → island table. | Unit tests. |

### Phase 4 — In-game runtime (C + ASM hooks)
| Branch | Work | Acceptance |
|---|---|---|
| `feature/tracker-c-toolchain` | `asm/tracker/` C sources; `.include` into a new `tracker.asm` patch; host build (`make -C asm/tracker host`) + ctypes test harness with mock RAM. Reserved `.space` symbols filled by `tweaks.py` (tables from Phase 3). Add needed vanilla symbols to `linker.ld`. | Patch assembles; host tests run in CI. |
| `feature/tracker-detection-and-save` | C: per-dungeon small-keys-obtained counters hooked on item get; check-flag evaluation per descriptor (incl. live-stage fallback + 6 special cases); manual-mark & visited-entrance bitfields in verified save region; stage-change hook records visited entrances (incl. CliPlaH special case). | Dolphin test: set flags via memory engine → tracker state matches. |
| `feature/tracker-logic-runtime` | Bytecode interpreter; re-eval hooks on item get (`execItemGet` path / AP give-queue) and on Fmap open; results cache. | Host tests match Python evaluator on 1000 random states; in-game eval < 1 frame budget measured. |
| `feature/tracker-chart-overview` | Hook `dMenu_Fmap_c` draw: per-square `a/r` counters with colour state. | Screenshot test on 3 seeds. |
| `feature/tracker-square-detail` | Zoomed square view: location list, D-pad selection, toggle button **X** (Y opens chart-compare in vanilla), main stick selects (D-pad Left/Down close the chart), scroll if > fits. | Scripted input test toggles a location; persists after save/reload. |
| `feature/tracker-list-page` | Separate page (**Z** on sea chart opens/closes; verified free) listing dungeon & non-island groups with counts → drill into group list with same controls. | Scripted test. |
| `feature/tracker-entrance-reveal` | Show entrance → destination only once visited; locations behind unvisited entrances shown under "Unknown entrance" and out of logic. | Test with ER seed. |
| `feature/tracker-chart-reveal` | Treasure chart → destination square shown once chart owned (randomized charts). | Test with chart-rando seed. |

Fallback ladder for UI branches if J2DPrint drawing proves unworkable: (1) repurpose existing `f_map.blo` panes/BMG text; (2) text in island-name box; (3) per-square count only. Any fallback is reported to the owner.

### Phase 5 — Polish & release
- `docs/user-guide`: README sections for offline vs AP mode and the tracker, controls.
- `chore/linux-build`: `build.py`/PyInstaller Linux build; tag `v2.5.2-tracking.1`, GitHub release with Linux binary (no ISO).
- `chore/windows-build`: Windows one-file `.exe` built by the same release workflow (matrix with Linux), released as `wwrando-<version>-windows-x64.zip`.
- Notes for future: Archipelago hints on the tracker (D14: needs a modified TWW client/apworld that every player installs, writing hinted location IDs into a reserved RAM array the tracker reads; the stock client can't do it), website "items needed" estimate.

## 11. Parallelisation & subagents

- Phase 0 sequential (main agent).
- Phase 1: `cli`, `devkitppc`, `fixtures`, `dolphin-harness`, `memory-map` in parallel worktrees.
- Phase 2 and Phase 3 (location table, item map, entrance/chart data) run in parallel; logic compiler starts after `offline-dungeon-item-modes` lands (shared logic code).
- Phase 4: toolchain first; then detection/save and logic-runtime in parallel; UI branches sequential (overview → detail → list page → reveals).
- A dedicated testing subagent runs the Dolphin harness for each Phase 4 PR and attaches screenshots/results to the PR description.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Free save bytes not actually free | Verify in decomp first; alternative: pack into unused stage-info bits or reduce to per-location manual bits only (~321 bits = 41 bytes). |
| Custom text drawing in Fmap crashes / font not loaded | Prototype early in `tracker-chart-overview` behind a debug build; fallback ladder. |
| Code/data size eating game heap | Size budgets (code ≤ 24 KB, tables ≤ 24 KB); measure arena impact; compress tables. |
| Key-count logic | Exact: custom per-dungeon "small keys obtained" counters (1 byte × 6 dungeons, save region) incremented by a hook on the item-give path (covers pickups and AP server deliveries). Big keys/map/compass use existing owned flags. |
| Offline logic diverges from AP logic | Parity tests vs APWorld; documented exceptions. |
| Dolphin automation flakiness under flatpak (ptrace for memory engine) | Use `--filesystem`/`--talk-name` overrides or native Dolphin build if needed; keep host C tests as the primary gate. |
