# Roadmap

Status: `done`, `in progress`, `planned`, `blocked`. One squash-merged PR per item into `master`.

## Android app (planned order from `docs/android-app-plan.md` §9)

| # | Item | Status |
|---|---|---|
| 1 | Plan + standalone `android/` skeleton: Termux `RUN_COMMAND` hello shim, CI builds the debug APK from the in-repo same-commit sources | done (PR #42) |
| 2 | Android: first-run setup + headless dry run (loopback bridge, Py 3.14 via gclib fork, build commit in bundle) | done (PRs #44–#47) |
| 3 | Real run: SAF ISO picker + copy, foreground service, cancel mid-run | done (PRs #49–#52) |
| 4 | Outputs: generated-ISO list, spoiler log viewer, Delete old, Play -> Dolphin `content://` link | done (PR #53) |
| 5 | [Settings: presets + generated settings screens (5a), permalink share, seed history (5b), Android UI cleanup (5c)](../PLAN.md) | done (PRs #54–#56) |
| 6 | [Android UI redesign (6a): nav rail, startup Self-Check, Home/Logic/Tweaks/Starting items, preset scope (PLAN §6)](../PLAN.md) | in progress |
| 7 | Later: `.aptww` import, Chaquopy fallback if Termux limits bite, signed Android release asset | planned |

## Shipped: offline mode + in-game tracker

`master` already carries the offline/Archipelago randomizer and the in-game tracker (through
v2.5.2-tracking.3): offline solo seeds with spoiler log and permalink, offline item-pool parity, the
tracker data layer, logic compiler and C runtime, sea-chart/dungeon-map/Quest Status UI, GO MODE, and
dungeon key counts (PRs #14–#41). Full history in `CHANGELOG.md`.
