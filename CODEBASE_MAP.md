# CODEBASE_MAP

Fork of LagoLunatic/wwrando ("tracking edition") adding an offline mode, an in-game sea-chart tracker,
and a standalone Android app. Plan and decisions: `PROJECT_PLAN.md`. Public docs site: `docs/` (mkdocs).
Developer docs index: `docs/dev/README.md`.

## Layout

- `wwrando.py` — CLI entry point (`--noui`, `--aptww`, `--clean-iso`, `--output-folder`, `--tracker`).
- `android_run.py` — headless Termux shim driving `WWRandomizer` over the loopback bridge; also
  `--sync-models <models_dir> <manifest.json>` for run.sh model sync (zip-slip-safe, skip/prune).
- `android_options_schema.py` — generates `android/app/src/main/assets/options_schema.json` (committed); `--check` fails on a stale file.
- `randomizer.py`, `tweaks.py`, `aptww.py` — randomizer core, game patching, `.aptww` (Archipelago) loader.
- `options/`, `logic/`, `randomizers/` — option definitions, logic files, offline item fill.
- `wwr_ui/` — Qt GUI; `offline_options.py` builds offline widgets; `inventory.py` is pure data imported
  by `randomizer.py` (bundled into the Android app; the rest of `wwr_ui/` is Qt/GUI-only and is not).
- `tracker/` — patch-time tracker data: `locations.py`, `entrances.py`, `charts.py`, `items.py`,
  `stages.py`, `dungeons.py`, `logic_compiler.py`, `serialize.py`.
- `asm/` — custom game code: `asm/patches/` (tracker.asm and others), `asm/tracker/` (C runtime, host
  build via `make -C asm/tracker host`), `asm/patch_diffs/` (committed assembled results).
- `gclib/` — git submodule (LagoLunatic/gclib); optional C speedups have pure-Python fallbacks.
- `android/` — standalone Gradle project (Kotlin/Compose, `io.github.thesword1.wwrando`); debug APK built
  from same-commit Python sources; Termux bridge under `android/app/src/main/java/.../data/`.
  Rail/settings data: `data/OptionsSchema.kt` (org.json parse of the schema asset), `data/SettingsLogic.kt`
  (pure diff/merge/validation), `data/SettingsStore.kt` (`filesDir/settings/` current.json + presets +
  `customize.json`; presets cover Logic + Tweaks + Starting items only), `data/RailSections.kt`
  (pure rail section layout), `data/OptionDependencies.kt` (desktop hide/sanitize rules),
  `data/StartingItemsLogic.kt` (item picker counts + health label), `data/SelfCheckLogic.kt` (startup
  self-check aggregation), `data/SeedNameGenerator.kt` (desktop seed-name mirror);
  `ui/AppScaffold.kt` (navigation rail) hosts `ui/HomeScreen.kt`, `ui/LogicScreen.kt`,
  `ui/TweaksScreen.kt`, `ui/StartingItemsScreen.kt`, `ui/CustomizeScreen.kt` (Advanced is a placeholder
  until 6c); shared widgets in `ui/OptionWidgets.kt`. Setup decision: `data/SetupLogic.kt` (commit-based install check).
  History: `data/HistoryStore.kt` (`filesDir/history.jsonl`, capped at 100), `ui/HistoryScreen.kt` +
  `ui/HistoryViewModel.kt`.
- Customize (6b): `data/ModelStore.kt` (`filesDir/models/<name>.zip`, SAF import/delete, zip reads),
  `data/ModelZip.kt` (pure import plan/validation), `data/ModelMetadata.kt` (SnakeYAML metadata parse,
  old-format/tab fixes, `link/` asset for Link), `data/ColorLogic.kt` (pure ports of gclib
  `color_exchange`/`hsv_shift_color`), `data/CustomizeLogic.kt` (pure get_color/set_color/preset/randomize
  mirror), `data/CustomizeStore.kt` (`customize.json`, kept out of presets, merged into the run diff);
  `ui/CustomizeViewModel.kt` + `ui/CustomizeScreen.kt` + `ui/PreviewRenderer.kt` (debounced preview).
  Bridge also serves `GET /models` and `GET /models/<name>.zip`; run.sh syncs them via
  `android_run.py --sync-models` before each run; setup.sh symlinks `~/wwrando/models` into each release.
  Kotlin colour fixtures: `android/tools/gen_color_fixtures.py` (one-shot) ->
  `android/app/src/test/resources/color_fixtures.json`.
- `test/` — pytest suite; `test/fixtures/aptww/` `.aptww` fixtures; `test/tracker_c_host.py` builds the
  tracker C runtime for host unit tests; `test_android_*` cover the shim, run.sh, and schema generator.
- `tools/` — `devkitppc/` (assembler container), `dolphin/` (Dolphin automation harness),
  `aptww_fixtures/`, `parity/` (Archipelago parity helpers).
- `data/`, `seedgen/`, `wwlib/`, `models/`, `assets/`, `keys/` — game data, seed generation, libs,
  custom models, UI assets, build keys.
- `.github/workflows/` — `test.yml` (pytest), `android.yml` (debug APK), `release.yml` (tag builds),
  `asm.yml` (patch diff reproducibility), `publish-site.yml` (mkdocs site).
- `scripts/test-quiet.sh` — quiet test wrapper; the only supported way to run the full suite locally.

## Key docs

- `docs/android-app-plan.md` — Android app plan; §9 lists the PR-sized milestones.
- `docs/dev/README.md` — "Where things are", test commands, workflow conventions.
- `docs/dev/tracker-runtime.md`, `docs/dev/memory-map.md`, `docs/dev/toolchain.md` — tracker/dev details.
- `CHANGELOG.md` — per-version feature log.

## Conventions

- Python 3.12 via uv; with GCC 16 the gclib C speedups need
  `CFLAGS="-std=gnu17 -fgnu89-inline"` (see `docs/dev/toolchain.md`).
- Tests: CI runs `pytest test -m "not saving" -q`; markers `saving`, `dolphin`, `slow` in `pytest.ini`.
- Trunk-based: one squash-merged PR per change into `master`; CHANGELOG entry per feature.
- Never commit ISOs, extracted game files, `.env`, `.claude/test.log`, or build keys.
