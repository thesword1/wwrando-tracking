# PLAN — Android: settings, presets, permalink share, seed history (roadmap #5)

Earlier specs (#2–#4, gclib Py 3.14, output-dir fixes) are done; see git history of this file.
Two PRs, one branch each: **5a** settings + presets (`feat/android-settings`), then **5b** permalink
paste/share + seed history (`feat/android-history`). Implement only the phase you are asked for.

## Goal

Today every device run uses default `Options()` plus seed/tracker. After #5 the user edits any
randomizer option on a generated settings screen, saves/loads named presets, pastes or shares a
permalink, and sees a history of past runs that survives deleting the output folders.

## 5a Design — options schema, settings screen, presets

1. **Schema generator** `android_options_schema.py` (repo root, next to `android_run.py`):
   `python android_options_schema.py [--check]` writes `android/app/src/main/assets/options_schema.json`
   (committed; `--check` exits 1 if the file is stale). One entry per `Options` field, file order:
   `{name, group, type, default, description, choices?, choice_descriptions?, minimum?, maximum?, permalink}`.
   - `type`: `bool`, `enum` (StrEnum; `choices` = enum values in order), `int` (min/max), `multi`
     (`list[str]` with `choices`). Skip `hidden=True` fields and types outside these four
     (e.g. free `str` like `custom_player_model`, `list[str]` without `choices`); list skipped names in
     a top-level `"skipped"` array.
   - `group`: the nearest preceding `#region <Name>` comment in `options/wwrando_options.py`
     (map field lines via `inspect.getsourcelines(Options)`; fail loudly if a field has no region).
   - `description`: strip HTML tags, `<br>` -> newline, unescape entities. Same for choice descriptions.
   - Output: `json.dumps(..., indent=1, ensure_ascii=False)` + trailing newline, so `--check` is
     byte-stable. Must run on 3.12 and 3.14 with only the repo's normal deps.
2. **Run-time overrides**: `android_run.py --settings-json PATH` (new arg). In
   `build_randomizer_kwargs`, apply after `settings.txt`, before `--permalink` (permalink wins). JSON is
   `{name: value}`; unknown names ignored; enum values converted via the field's type; a bad value
   (wrong type, out of range, unknown choice) raises -> reported as step `settings` failure with the
   option name. Desktop `wwrando.py` unchanged.
3. **Bridge**: new route `GET /settings?t=<token>` returns the current settings JSON (diff vs defaults,
   UTF-8). `run.sh` fetches it after "Copying ISO" into `$WW/run/settings.json` (`curl -fsS`, failure ->
   `fail "settings" ...`) and passes `--settings-json`. Keep `run.sh` shellcheck-clean.
4. **App data** (`data/`):
   - `OptionsSchema.kt`: parse the asset (org.json) into `OptionDef` sealed types; pure, unit-tested.
   - `SettingsStore.kt`: files in `filesDir/settings/`: `current.json` (diff vs schema defaults, only
     non-default values stored) and `presets/<name>.json` (same format). API: `current()`, `set(name,
     value)`, `resetToDefaults()`, `listPresets()`, `savePreset(name)`, `loadPreset(name)`,
     `deletePreset(name)`, `activePresetName()` + `isModified()` (current differs from the loaded preset).
     Preset names: 1–40 chars `[A-Za-z0-9 _-]`, trimmed; built-in read-only "Default" (= empty diff).
     Values not in the schema (stale after an update) are dropped on load. Pure diff/merge/validation
     logic in a testable object without Android types.
5. **UI** (`ui/`): `SettingsScreen.kt` + `SettingsViewModel.kt`. HomeScreen gets a settings card
   ("Preset: <name>[ (modified)] · N changes", button "Edit settings") that opens a full-screen
   settings view (simple state switch in MainActivity/HomeScreen, no navigation library). Screen: preset
   row (dropdown Load, Save as…, Delete, Reset to defaults); one collapsible section per `group`;
   `bool` -> Switch, `enum` -> dropdown, `int` -> stepper (−/+ within min..max), `multi` -> button
   opening a checkbox dialog. Each row shows the label (name with `_` -> spaces, capitalised) and a
   one-line description; tap the row text for the full description dialog. Changes save immediately.
   Settings controls disabled while a run is active. Keep each new file under ~300 lines.

## 5b Design — permalink paste/share, seed history

1. **Permalink in**: RunSection gets an optional "Permalink" field. Non-blank -> run passes it to
   `run.sh` as a new trailing arg (`<permalink>`, may be empty) after validating
   `^[A-Za-z0-9+/=]{4,2000}$` in Kotlin and again in `run.sh`; `run.sh` adds `--permalink`. The seed
   field and settings card show "from permalink" and are ignored while it is set. Decode errors
   (bad permalink, different commit) surface as the normal `randomize` failure text.
2. **Share**: after a successful run and on each outputs-list entry with a permalink: "Share"
   (`ACTION_SEND` text: `Permalink: …\nSeed hash: …\nBuild: <build_commit>`) and "Copy".
3. **History**: `HistoryStore.kt`, `filesDir/history.jsonl`, one JSON object per finished run
   (success or failure; cancel not recorded): `{time, ok, seed, seed_hash, permalink, preset,
   modified, error, folder}`; capped at 100 (oldest dropped). Written by `RandoRunService` on done/fail.
   `HistoryScreen` (opened from HomeScreen "History") lists newest first; per entry: "Use permalink"
   (fills the permalink field and returns), "Share"; "Clear history" at the top (confirm dialog).

## Tests (scripts/test-quiet.sh must stay green; CI also builds the APK)

- 5a Python: `test/test_android_options_schema.py` — `--check` passes on the committed file; every
  non-skipped field present with right type; groups match regions. `test/test_android_run.py` —
  `--settings-json` changes an option (e.g. `progression_tingle_chests`), permalink still wins, bad
  enum value fails with step `settings`. `test/test_android_run_sh.py` — `/settings` fetched and
  `--settings-json` passed; fetch failure -> settings fail.
- 5a Kotlin: `OptionsSchemaTest` (parse a small fixture + the real asset), `SettingsLogicTest`
  (diff vs defaults, preset name validation, stale keys dropped, modified flag), bridge route test in
  `LoopbackBridgeTest`.
- 5b: permalink regex (Kotlin + run.sh test), `HistoryLogicTest` (cap 100, newest first, malformed
  line skipped), run.sh test for `--permalink` passthrough.

## Acceptance criteria

- 5a: CI green (3.12 + 3.14, APK). On device: change e.g. Sword Mode + a hint count, run -> spoiler log
  shows those settings; save preset, reset, load preset -> values restored; settings survive app restart.
- 5b: paste a desktop permalink -> device seed hash matches desktop; Share opens the share sheet;
  history lists runs incl. a failed one and survives deleting outputs; "Use permalink" re-runs same hash.
