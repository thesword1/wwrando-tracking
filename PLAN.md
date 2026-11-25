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

## 5c Design — Android UI cleanup (user feedback after 5b device test)

Dropped from the Android UI (record this in `docs/android-app-plan.md` and CHANGELOG): seed field,
permalink field, Share/Copy (run result, outputs list, history), "Use permalink". Runs always autoseed.
Backend stays: `run.sh` `<seed>`/`<permalink>` args and `android_run.py --permalink` (tests keep passing),
the app just always sends empty values. Remove Kotlin that becomes unused (Permalink.kt/ShareActions.kt
and their tests) rather than leaving dead code.

1. **Home**: ISO/output pickers, settings card, setup status, Randomize, outputs list, History. No seed,
   permalink or tracker controls.
2. **Tracker** toggle moves to the Settings screen (an "App" group at the top), persisted with the other
   settings in `SettingsStore` (not part of presets' randomizer options unless that is simpler; say which in
   the PR). The settings card summary may mention "tracker on".
3. **System back**: Android back (gesture/button) from Settings, History, Logs viewer and any other
   sub-screen returns to the previous screen (Compose `BackHandler` or nav back stack); only Home exits.
4. **Automatic setup**: no "First-run setup"/"Run setup" button. On app start and on resume, if Termux
   setup is missing or the installed bundle's build commit differs from the APK's `build_commit.txt`,
   the app starts setup itself (at most one at a time) and shows a status card: Setting up (step text) /
   Ready / Failed: <error> + "Retry" (Retry is the only setup button, and only on failure). Randomize is
   disabled until Ready. Missing RUN_COMMAND permission keeps the existing guidance card.
   History records nothing for setup.

Tests: Kotlin unit test for the setup-needed decision (missing / commit mismatch / current) and for
tracker persistence; existing Python tests unchanged and green.

Acceptance (device): fresh APK install -> app runs setup by itself and shows Ready; Home shows no seed,
permalink or tracker; tracker toggle in Settings survives restart and still produces the tracker output;
back gesture from Settings/History/Logs returns to Home; back on Home exits.

## 5d Design — starting items, custom player models and colors (spec, implement after 5c)

Currently skipped by `android_options_schema.py`: `starting_gear`, `randomized_gear`, `custom_player_model`,
`custom_color_preset`, `custom_colors` (`randomize_enemies` stays skipped).
1. **Starting items**: schema emits `starting_gear` as an item-list type with the same allowed items and
   per-item max counts (progressive items) the desktop UI uses; mirror how the desktop UI keeps
   `randomized_gear` consistent (find it in the desktop UI code, don't guess). Settings screen: a
   "Starting items" sub-screen with +/- counts per item; diff/presets/`--settings-json` carry the list.
2. **Custom models**: Settings "Player model" sub-screen: "Import model (.zip)" via SAF; the app keeps
   zips in `filesDir/models/<name>.zip`, reads `metadata.txt` + `color_masks/` names from the zip in
   Kotlin to list the model's color presets and custom color names. Bridge route `GET /models` (name +
   md5 list) and `GET /models/<name>.zip`; `run.sh` syncs changed zips into persistent `~/wwrando/models/`
   (Python zipfile, not `unzip`), and setup links `~/wwrando/current/models` to it so upgrades keep models.
   Model/preset/custom colors (hex editor per color name) go through `--settings-json`. Default Link and
   its presets work with no import.
Acceptance (device): start with e.g. Grappling Hook + 2 heart containers -> spoiler log shows them;
import a model zip, pick it + a color preset, run -> Dolphin shows the model; preset save/load keeps both.

## 6 Design — Android UI redesign (user spec 2026-11-25, after 5c device test; supersedes 5c's tracker/"App" group and 5d's UI parts)

Model the shell on GameHub Manager (local clone `/media/storage/y700-tools/gamehub-manager`, read-only
reference): a **left navigation rail** with sections, in this order:

0. **Startup / Self-Check.** On launch show only a loading indicator while setup/self-check runs (no
   other page content). Afterwards the top of Home has a **Self-Check** card: either a list of what
   failed (Termux missing, RUN_COMMAND denied, setup failed: <error>, ISO not verified, output folder
   not picked, ...) each with its fix action, or a single "Everything is OK" row with a green check.
   Setup must not need the network once it has succeeded online once (no pip/curl to the internet on
   a current bundle); self-check must pass offline.
1. **Home**: preset selector at the top (load/switch, "Save preset" after setting things up, delete);
   ISO path; output folder path; seed text box with a "New seed" button (random seed name the same way
   the desktop randomizer makes one); Randomize; outputs list; History entry point.
2. **Logic**: all logic groups — Progression locations, Modes, Difficulty, Entrance randomizer, Other
   randomizers — plus number of starting Triforce shards (as on desktop). An **Advanced settings**
   expandable at the bottom for less-used logic settings, matching the desktop's advanced options.
3. **Tweaks**: Meta, In-game tracker (the tracker toggle lives ONLY here, remove the "App" group),
   Convenience tweaks, Hints.
4. **Starting items**: whole screen listing the current starting items (empty by default; nothing
   starts unless added) with add (picker/dropdown of allowed items, counts for progressive items) and
   remove. Heart pieces and heart containers are added through this picker (mapped to the
   randomizer's starting PoH/HC count options). Remove the "random extra starting items" option and
   the separate heart piece/container controls from the UI; send 0 for the extra-items option.
5. **Customize** (6b): as close as possible to the desktop Player Customization tab — rendered model
   preview (preview image with color masks applied, recoloured live), "Import model (.zip)", model
   selection, casual clothes switch, custom voice and custom items toggles, color preset select/save,
   "Randomize colors (orderly)" and "(chaotic)" like desktop, and a color picker for every color.
   Model import/sync as in 5d item 2.
6. **Advanced** (6c): About (version, build commit, links) and **Permalink**: show the permalink for
   the current settings and allow pasting one, which loads its settings into Logic/Tweaks/Starting
   items (decode via Termux `android_run.py`, e.g. a `--decode-permalink` mode returning settings
   JSON over the bridge, so Kotlin needs no permalink codec). Seed field on Home is filled from it.

**Presets** (Home): cover Logic + Tweaks + Starting items only. NOT the permalink, the seed, or any
Customize setting. Customize settings (model, colors, toggles) persist on their own across runs and
app restarts. Seed stays across restarts but is not in presets.

Desktop UI source to mirror: `wwr_ui/randomizer_window.ui`, `wwr_ui/` (CosmeticTab), the option
groups in `options/wwrando_options.py`. Read them; don't guess labels or groupings.

Milestones: **6a** = rail shell, startup loading + Self-Check, Home, Logic, Tweaks, Starting items,
preset scope. **6b** = Customize (+ 5d item 2 model import). **6c** = Advanced/About/permalink.
Tests: Kotlin unit tests for self-check aggregation, preset scope (excludes seed/customize),
starting-items mapping (hearts -> PoH/HC, progressive counts), extra-items forced 0; Python test
for any new android_run.py mode. scripts/test-quiet.sh green.
Acceptance (device, per milestone): sections/rail as above on the Y700; offline self-check OK;
preset save/load restores Logic/Tweaks/Starting items and leaves seed + Customize untouched;
starting items empty by default and spoiler log matches what was added.

## 6a decisions (2026-11-25)

1. **Hints**: keep all 10 hint options (hoho/fishmen/korl, num_item/location/barren/path_hints,
   cryptic, prioritize_remote, hint_importance) in their own "Hints" section on the Tweaks screen.
   Defaults unchanged.
2. **Option dependencies**: copy the desktop rules from
   `wwr_ui/randomizer_window.py ensure_valid_combination_of_options()`, but HIDE dependent options
   instead of greying them out, and put each dependent option directly under its parent.
   - `required_bosses` only when `progression_dungeons`; `num_required_bosses` / `included_dungeons` /
     `excluded_dungeons` appear right below it only when it is on.
   - `randomize_secret_cave_inner_entrances` only when both `progression_puzzle_secret_caves` and
     `progression_combat_secret_caves` are on.
   - `mix_entrances` only when a dungeon-type and a non-dungeon entrance option are both on.
   - `prioritize_remote_hints` only when `num_location_hints > 0`.
   - A hidden option sends its default (false for toggles, as desktop unchecks them).
   - Sword mode `Swordless` / `No Starting Sword` / `Swords Optional` removes `Hurricane Spin` /
     `Progressive Sword` from the starting-items picker and the current list.
   - Unit-test these rules.
3. **Starting items screen**: KEEP the desktop "Starting Health and Items" number options
   (`starting_hcs` default 3, `starting_pohs` default 0, `num_extra_starting_items` default 0) plus a
   current-health label like desktop. Do NOT route hearts through the picker. The item picker uses
   exactly `wwr_ui/inventory.py` `INVENTORY_ITEMS` (progressive items countable up to their count
   there); starting + randomized must always equal `INVENTORY_ITEMS` like desktop.
4. **No .aptww/Archipelago anything.** `randomize_enemies` goes into Logic > Advanced settings with a
   visible warning that it can produce unbeatable/broken seeds (it is hidden+unbeatable on desktop).
5. **Color scheme**: copy GameHub Manager's dark palette (primary `#4FA3FF`, background `#101216`,
   surface `#161A21`, surfaceContainer `#1B2029`, outline `#3A4250`, error `#FF6B6B`); dark-only, no
   white backgrounds (rail, cards, dialogs, loading screen).
6. **Home order** (top to bottom): Self-Check, ISO + output folder, Randomize, Preset, Seed,
   current/generated seeds (outputs list).
7. **Clean ISO + output folder** share one row as two side-by-side compact fields/buttons.
8. **Randomize** is centered, large, primary, clearly the main action.
9. **Startup loading screen**: app icon + "Wind Waker Randomizer" title above the progress indicator.

## 6b design — Customize (2026-11-25; refines 6 item 5 + 5d item 2)

Desktop source to mirror (read, don't guess): `wwr_ui/cosmetic_tab.py` (whole file: get_color/set_color,
preset logic, randomize, install zip, disable_invalid_cosmetic_options), `customizer.py`
get_model_metadata / get_model_preview_image, `gclib/gclib/texture_utils.py` color_exchange (pure-Python
path, `validate_mask_colors=False`) and hsv_shift_color, `wwr_ui/randomizer_window.ui` cosmetic tab labels.

1. **Model storage (Kotlin)**: "Import model (.zip)" via SAF. Validate like desktop install_custom_model_zip
   (single model dir, or a pack with `<top>/models/<name>/`; each needs `Link.arc` + `metadata.txt`).
   Store each model as a normalized zip `filesDir/models/<name>.zip` (entries relative to the model dir;
   packs are split). Re-import of a name replaces it. Reject names `Link`, `Random`, `Random (exclude Link)`,
   names with `/` or `..`, and any entry that is absolute or contains `..` (zip slip). Also "Delete model".
   Kotlin reads metadata.txt, `preview/*.png`, `sound/JaiInit.aaf`+`sound/voice_0.aw` presence straight from
   the zip (java.util.zip.ZipFile); no extraction on the Android side.
2. **Metadata parse**: SnakeYAML (org.yaml:snakeyaml, pinned) after the same old-format and tab regex
   fixes as get_model_metadata; hero/casual_custom_colors, hero/casual_color_presets,
   disable_casual_clothes. Parse error -> model listed with its error, colors hidden.
   Default Link: gradle copies repo `assets/link_metadata.txt` + `assets/link_preview/` into APK assets
   (`link/`) at build time (no checked-in copies).
3. **Preview**: Kotlin port of color_exchange (only red FF0000FF mask pixels change; HSV int truncation
   exactly like Python colorsys + int()) applied per changed color on `preview_<hero|casual>.png` with
   `preview_<prefix>_<color>.png` masks; skip colors equal to base. Render off the main thread, debounce
   ~150 ms, newest request wins. No preview (placeholder text) for Random or missing preview files.
4. **Customize screen** (desktop order/labels): preview; Player model dropdown (Link, installed models
   sorted, plus Random / Random (exclude Link) only if any are installed); Import model; Delete model;
   "Casual clothes" (off+disabled if disable_casual_clothes); "Disable custom voice" (enabled only if the
   model has both sound files, or Random); "Disable custom items" (disabled for Link); Color preset
   dropdown (Default, Custom, model presets; reserved names ignored); "Save colors…" / "Load colors…" via
   SAF .txt in the desktop YAML format (model_name, colors as 0xRRGGBB, is_casual; load refuses
   uninstalled models, like desktop); "Randomize colors (orderly)" = randomize_all_custom_colors_together,
   "(chaotic)" = randomize_all_custom_colors_separately; per color: swatch -> color picker dialog
   (hue/sat/value sliders + hex field), randomize-one, reset-one. Preset/Custom semantics, model switch and
   hero/casual switch behave exactly like get_color/set_color/update_color_presets_list. Colors hidden for
   Random models.
5. **Persistence**: customize.json holds custom_player_model, player_in_casual_clothes,
   disable_custom_player_voice, disable_custom_player_items, custom_color_preset, custom_colors
   ({name: [r,g,b]}) and goes into `--settings-json` unchanged; still excluded from presets. A stored model
   that no longer exists falls back to Link.
6. **Sync to Termux**: bridge `GET /models` -> `[{"name","md5"}]`, `GET /models/<url-encoded name>.zip`.
   run.sh, before the run: fetch the list, download changed zips to a temp dir, then
   `android_run.py --sync-models <models_dir> <manifest.json>` (manifest = name, md5, local zip path):
   extracts each into `<models_dir>/<name>.tmp` with zipfile (zip-slip checks), renames over
   `<name>/`, writes `<name>/.md5`; deletes model dirs not in the manifest; unchanged md5 = skip.
   setup.sh: `mkdir -p ~/wwrando/models` and make `$DEST/models` a symlink to it (upgrades keep models).
   Offline/no models: list is empty, sync just prunes; self-check unaffected.
Tests: Kotlin — metadata parse (Link asset + an old-format sample), zip import (single, pack, missing
file, zip slip, reserved name), color_exchange + hsv_shift parity against values generated once with the
Python code (fixtures committed), color save/load round trip, customize not in presets. Python —
sync_models (install, skip same md5, replace, prune, zip slip rejected). scripts/test-quiet.sh green, CI APK.
Acceptance (device): Link preview recolors live; import a model zip, pick it + a preset, run -> Dolphin shows
the model; colors/model persist across app restart and are untouched by preset load.

## 6b device-test decisions (2026-11-25)
1. **Reset colors**: add a "Reset to default colors" button (mirror desktop
   reset_color_selectors_to_model_default_colors): current model + hero/casual defaults, preset -> Default.
2. **No .txt color files**: remove "Save colors…/Load colors…" (SAF .txt). Instead "Save as preset" asks for a
   name and stores the current colors as a user color preset in the app (`filesDir/color_presets.json`, keyed by
   model name -> hero|casual -> preset name -> {color: [r,g,b]}), shown in the Color preset dropdown after the
   model's own presets; "Delete preset" for user presets only. Reserved/model preset names are refused; saving an
   existing user preset name overwrites it after a confirm. Selecting a user preset sends
   `custom_color_preset="Custom"` + its colors in `custom_colors` (the randomizer only knows model presets); the
   dropdown keeps showing the user preset name (stored as a UI-only field in customize.json). Editing a color
   switches to Custom as before. User presets are not part of Home presets. Kotlin tests: save/overwrite/delete,
   reserved name refused, selection -> settings diff.
