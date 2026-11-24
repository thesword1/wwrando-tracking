# Roadmap

Status: `done`, `in progress`, `planned`, `blocked`. One squash-merged PR per item into `master`.

## Android app (planned order from `docs/android-app-plan.md` §9)

| # | Item | Status |
|---|---|---|
| 1 | Plan + standalone `android/` skeleton: Termux `RUN_COMMAND` hello shim, CI builds the debug APK from the in-repo same-commit sources | done (PR #42) |
| 2 | [Android: first-run setup + headless run](../PLAN.md) | in progress |
| 3 | Outputs: generated-ISO list, spoiler log / tracker hints viewer, Delete old, Play -> Dolphin `content://` link | planned |
| 4 | Settings: presets + generated settings screens, permalink share, seed history | planned |
| 5 | Later: `.aptww` import, Chaquopy fallback if Termux limits bite, signed Android release asset | planned |

## Shipped: offline mode + in-game tracker

`master` already carries the offline/Archipelago randomizer and the in-game tracker (through
v2.5.2-tracking.3): offline solo seeds with spoiler log and permalink, offline item-pool parity, the
tracker data layer, logic compiler and C runtime, sea-chart/dungeon-map/Quest Status UI, GO MODE, and
dungeon key counts (PRs #14–#41). Full history in `CHANGELOG.md`.
