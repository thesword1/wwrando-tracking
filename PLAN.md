# PLAN — Android: outputs list, log viewer, Play in Dolphin (roadmap #4)

Earlier specs (#2, #3, gclib Py 3.14, output-dir fixes) are done; see git history of this file.

## Goal

After a run, the app lists every generated seed in the picked SAF output tree, shows its spoiler /
non-spoiler logs in-app, deletes old seeds, and launches the ISO in Dolphin through a granted
`content://` URI. No change to the Python side or `run.sh` is needed.

## Design

1. **Run metadata** (`service/RandoRunService.kt`, `finishRun`): on a successful, non-cancelled
   run, write `wwrando-run.json` into the run's subfolder via the existing SAF sink (add a
   `writeMeta(json: String)` to the sink, same folder as the uploads). Fields: `seed`, `seed_hash`,
   `permalink`, `tracker` (bool), `created` (ISO-8601 local time), `app_commit` (the
   `build_commit.txt` asset). A failure to write it is logged, never fails the run.
2. **Outputs repository** (new `data/OutputsRepo.kt`, pure SAF, no DB):
   - `list(treeUri): List<SeedOutput>` — query children of the tree root
     (`DocumentsContract.buildChildDocumentsUriUsingTree`), keep directories, and per directory query
     its children once. `SeedOutput(folderUri, folderName, isoUri?, isoSize, logs: List<LogFile>,
     meta: RunMeta?, modified)`. ISO = first child ending `.iso` (case-insensitive); logs = `*.txt`
     (label: "Spoiler log" if the name contains `- Spoiler Log`, "Non-spoiler log" if
     `Non-Spoiler`, else the file name). `meta` parsed from `wwrando-run.json` if present; folders
     without it (older runs) still list, using the folder name as the title. Folders with neither
     an ISO nor logs are skipped. Sort newest first by `meta.created`, else folder `modified`.
   - `readText(uri, maxBytes = 2 MiB): String` for the viewer (truncate with a note past the cap).
   - `delete(folderUri)` (`DocumentsContract.deleteDocument` on the folder) and
     `deleteOlderThanNewest(keep: Int = 1)`.
   - All calls run on `Dispatchers.IO`; SAF exceptions become a `Result` failure, not a crash.
3. **Dolphin launcher** (new `data/DolphinLauncher.kt`):
   - Packages tried in order: `org.dolphinemu.dolphinemu`, `org.dolphinemu.mmjr`
     (add both to `<queries>` in `AndroidManifest.xml`). `isInstalled()` via `PackageManager`.
   - Launch: explicit `Intent(Intent.ACTION_MAIN)`, component
     `<pkg>/org.dolphinemu.dolphinemu.ui.main.MainActivity`, extra `"AutoStartFile"` = the ISO
     `content://` URI string, `setData(isoUri)` too, flags
     `FLAG_GRANT_READ_URI_PERMISSION | FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TASK`, plus
     `ClipData.newRawUri("iso", isoUri)` so the grant applies.
   - Fallback if no known package or `ActivityNotFoundException`: `ACTION_VIEW` on the URI
     (`application/octet-stream`, read grant) via `Intent.createChooser`; if that also fails, return
     an error string the UI shows ("Dolphin not found").
4. **UI** (new `ui/OutputsSection.kt`, wired into `HomeScreen.kt` below the run section):
   - Shown when an output folder is granted. Header "Generated seeds (N)" + Refresh. Auto-refresh
     when `RunState` becomes `Done`.
   - One card per seed: title = seed hash (or folder name), subtitle = seed + date + ISO size
     (MB); buttons **Play**, **Logs**, **Copy permalink** (only if meta has one), **Delete**
     (confirm dialog).
   - **Delete old** in the header: confirm dialog "Delete all but the newest seed?".
   - **Logs** opens a full-screen dialog: tabs per log file, monospace selectable text in a
     scrollable column, loaded lazily via `readText`.
   - Errors (SAF revoked, Dolphin missing) show as a one-line message in the section, no crash.
   - Keep each new Kotlin file under ~250 lines; state lives in `RandoViewModel` or a small
     `OutputsViewModel` if `RandoViewModel.kt` would pass ~300 lines.
5. **Minor fix in the same PR** (`ui/RunSection.kt`): the Randomize button must not move when
   result text appears (button above the result/status text, or a fixed result slot).

## Tests

- JVM unit tests (`android/app/src/test/`) for the pure parts: log labelling, ISO/log picking from a
  child list, `RunMeta` JSON parse (missing/extra fields), sort order, and the Dolphin intent spec
  (package, component, extra, flags) built by a pure function so it needs no device.
- CI (`android.yml`) stays green: `assembleDebug` + unit tests (add the test task if missing).

## Acceptance criteria

- `scripts/test-quiet.sh` and the Android CI workflow pass; no change under the Python tree.
- A new run writes `wwrando-run.json`; the list shows it at the top after the run finishes.
- Older seed folders without metadata still list (the device has 3 such folders).
- Logs viewer shows the spoiler log text; Delete and Delete old remove folders after confirmation.
- Play launches Dolphin with the ISO (device check by Opus; DeepSeek only builds).
- Randomize button position is stable across idle / running / done states.
