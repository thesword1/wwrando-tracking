# Roadmap

Status: `done`, `in progress`, `planned`, `blocked`. One squash-merged PR per item into `master`.

## Android app (planned order from `docs/android-app-plan.md` §9)

| # | Item | Status |
|---|---|---|
| 1 | Plan + standalone `android/` skeleton: Termux `RUN_COMMAND` hello shim, CI builds the debug APK from the in-repo same-commit sources | done (PR #42) |
| 2 | Android: first-run setup + headless dry run (loopback bridge, Py 3.14 via gclib fork, build commit in bundle) | done (PRs #44–#47) |
| 3 | Real run: SAF ISO picker + copy, foreground service, cancel mid-run | done (PRs #49–#52) |
| 4 | Outputs: generated-ISO list, spoiler log viewer, Delete old, Play -> Dolphin `content://` link | done (PR #53) |
| 5 | [Settings: presets + generated settings screens (5a), seed history (5b), UI cleanup + automatic setup + system back (5c)](../PLAN.md). Seed/permalink paste/Share were built in 5b, then dropped from the UI in 5c (backend `run.sh`/`android_run.py --permalink` kept) | done (PRs #54–#56) |
| 6a | [UI redesign (PLAN §6 + "6a decisions"): GameHub-style nav rail + dark theme; startup loading (icon + title) then Self-Check card; Home = Self-Check, ISO+output row, Randomize, Preset, Seed (+ New seed), outputs, History; Logic (desktop groups + Advanced, `randomize_enemies` with warning); Tweaks (Meta, In-game tracker, Convenience, Hints); Starting items (desktop INVENTORY_ITEMS picker + HC/PoH/extra numbers + health label); desktop dependency rules as hidden-not-greyed; presets = Logic+Tweaks+Starting items, last preset/settings restored at launch](../PLAN.md) | done (PR #57), device-tested |
| 6b | Customize (PLAN §6 item 5 + §5d item 2): model preview with color masks, model `.zip` import + bridge sync to `~/wwrando/models`, casual clothes / custom voice / custom items, color presets, orderly/chaotic randomize, per-color picker; persists outside presets | done (PR #59, device-tested; in-app color presets + reset) |
| 6c | Advanced: About + permalink for current settings, paste to load (decode in Termux via `android_run.py`) | done (PR #60), device-tested 2026-11-25 on Y700 — `--encode-permalink`/`--decode-permalink` + shared option loader, `PermalinkRunner`, `AdvancedScreen` (generate/copy with stale-hide, paste/load, About) |
| 7 | Later: Chaquopy fallback if Termux limits bite, signed Android release asset. Not planned: `.aptww`/Archipelago on Android (can't be played there) | planned |

## Shipped: offline mode + in-game tracker

`master` already carries the offline/Archipelago randomizer and the in-game tracker (through
v2.5.2-tracking.3): offline solo seeds with spoiler log and permalink, offline item-pool parity, the
tracker data layer, logic compiler and C runtime, sea-chart/dungeon-map/Quest Status UI, GO MODE, and
dungeon key counts (PRs #14–#41). Full history in `CHANGELOG.md`.
