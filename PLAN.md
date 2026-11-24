# PLAN — Android: real run (roadmap #3)

Context: docs/android-app-plan.md §3–§5, §9 item 3. Builds on roadmap #2 (PRs #44–#47):
`data/LoopbackBridge.kt` (127.0.0.1, random port + token), `setup.sh`, `android_run.py`, RUN_COMMAND
stdin runner. Outputs list, spoiler viewer and Dolphin launch are NOT in this PR (roadmap #4).

**Deviation from android-app-plan.md §4:** no shared storage and no `termux-setup-storage`. Both the
ISO in and the outputs out go over the loopback bridge, so Termux needs no storage permission and the
app needs none beyond its SAF grants. Update §4 of the plan doc to match.

## Design
1. **ISO pick (SAF).** "Pick clean ISO" -> `ACTION_OPEN_DOCUMENT` (`*/*`; GameCube ISOs have no
   reliable MIME type), `takePersistableUriPermission`. Store URI + display name + size +
   last-modified in a small `data/RandoPrefs.kt` (SharedPreferences). On pick, compute the MD5 in the
   app (coroutine on IO, progress bar, cancellable) and compare to `CLEAN_ISO_MD5` in Kotlin
   (`d8e4d45af2032a081a0f446384e9261b`, copied from `randomizer.py:CLEAN_WIND_WAKER_ISO_MD5`).
   Store the verified flag keyed on (uri, size, lastModified); show a badge (verified / wrong ISO /
   unreadable). Run button disabled unless verified. A Python test asserts the Kotlin constant
   matches `randomizer.py` (simple regex over both files).
2. **Output folder (SAF).** "Pick output folder" -> `ACTION_OPEN_DOCUMENT_TREE`, persist the grant,
   store the tree URI. Run button disabled without it. Each run writes into a new subfolder
   `<seed-hash-or-seed>_<yyyyMMdd-HHmmss>` (created with `DocumentsContract.createDocument`).
3. **Bridge endpoints (extend LoopbackBridge, keep it < 400 lines; split request routing into
   `data/BridgeRoutes.kt` if needed).** All token-checked as today.
   - `GET /iso` streams the picked ISO from `ContentResolver.openInputStream` with
     `Content-Length` = stored size.
   - `POST /output?name=<file>` streams the body into a new document in the run's output subfolder.
     `name` must match `^[A-Za-z0-9._ -]{1,128}$` and contain no `/` (403 otherwise); MIME
     `application/octet-stream`. On a short body or I/O error delete the partial document and
     return 500.
4. **run.sh** (new bundled asset next to setup.sh, sent on stdin, same conventions: args, `STEP`
   lines, POST /done JSON on failure with the stderr tail, shellcheck clean). Args: port, token,
   iso size, iso md5, run args (seed/permalink/autoseed, tracker flag) passed as one quoted string
   or positional args — pick one and document it.
   a. Free-space check with `df -k ~` : need iso size (if not cached) + 1.6 GB; else /done
      `{"ok":false,"step":"space","error":"need X MB, have Y MB"}`.
   b. ISO cache: `~/wwrando/input/clean.iso` + `clean.iso.md5`. If the md5 file equals the passed
      md5 and the file size matches, report `SKIP iso-cached`; else `curl -fsS` /iso to
      `clean.iso.part`, verify size and `md5sum`, then `mv` into place.
   c. Run `~/wwrando/venv/bin/python ~/wwrando/current/android_run.py --clean-iso
      ~/wwrando/input/clean.iso --output-folder ~/wwrando/out/<jobid> <run args>` (no `--dry`).
      android_run.py keeps posting PROGRESS; it must NOT post /done on success when run under
      run.sh — add `--no-done` (or have run.sh own /done; choose one, keep the dry-run path working).
   d. Upload every regular file in the out dir (ISO, spoiler/non-spoiler logs) via POST /output,
      reporting `STEP upload <name>`; then `rm -rf` the out dir.
   e. POST /done with the result JSON (seed, permalink, seed hash, uploaded file names).
   f. `trap` on EXIT/TERM: remove `clean.iso.part` and the out dir on any failure.
5. **Foreground service** `service/RandoRunService.kt`: `foregroundServiceType="dataSync"`
   (`FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_DATA_SYNC` permissions; targetSdk 36). Owns the
   bridge and the RUN_COMMAND job for a real run so it survives the activity going to background.
   Notification channel "Randomizer run": determinate progress from PROGRESS/STEP events, text =
   current step, actions Cancel; on finish a completion notification (ok: seed hash; fail: error).
   Request `POST_NOTIFICATIONS` before the first run (denial must not block the run). The
   ViewModel observes the service's state via a process-wide `StateFlow` (e.g. `RunState` object in
   the service file), not binding. Dry run may stay in the ViewModel.
6. **Cancel.** Notification action and in-app button both: RUN_COMMAND `pkill -f run.sh;
   pkill -f android_run.py; pkill -f 'curl.*127.0.0.1'`, close the bridge, delete any partial
   output document, mark state cancelled, `stopSelf`. run.sh's trap cleans the Termux side.
7. **UI** (new composables in `ui/`, keep HomeScreen < 400 lines; split into `ui/RunSection.kt`):
   ISO card (name, size, MD5 badge, Pick/Change), output-folder card, Run section (seed field
   blank = autoseed, tracker toggle default on, "Randomize" button, progress + step text, Cancel,
   result: seed hash, permalink, output subfolder name).

## Acceptance criteria
- `./gradlew assembleDebug testDebugUnitTest` passes in CI; shellcheck clean on run.sh.
- JVM unit tests: /iso serves bytes intact with correct Content-Length; /output rejects bad names
  and bad token (403), writes body intact (use a fake output sink interface so tests need no
  ContentResolver), deletes partial on short body; MD5 helper matches a known vector; RunState
  transitions (idle -> running -> done/failed/cancelled).
- Python: `test/test_android_constants.py` (Kotlin MD5 == randomizer.py); existing
  `test/test_android_run.py` still passes; add a test for the `--no-done` (or chosen) behaviour.
  Via scripts/test-quiet.sh.
- No source file over 400 lines; MainActivity stays a thin host.
- PR body lists device-test steps for the main session: pick wrong file (badge = wrong ISO), pick
  clean ISO (verified), pick output folder on SD, first real run (ISO copied, progress in
  notification, files land in subfolder), second run (`SKIP iso-cached`), cancel mid-randomize
  (no partial files either side), cancel mid-upload, app backgrounded during a run, notification
  permission denied.

# PLAN — gclib: Py 3.14 issubclass on generic aliases (device bug from roadmap #3)

## Problem
Real run on Termux Py 3.14 fails while reading a BFN font:
`gclib/bunfoe.py:429 read_value: elif issubclass(field_type, MappedBool)` ->
`TypeError: issubclass() arg 1 must be a class` (call chain rarc.get_file -> bfn.read -> jchunk.read -> bunfoe.read -> read_field -> read_value).
Cause: Python 3.14 makes `issubclass(list[int], X)` raise TypeError (3.12 returned False). BUNFOE fields typed as
`list[...]`/other GenericAlias reach bare `issubclass(field_type, ...)` calls. CI 3.14 only ran tests that never parse game files.

## Fix (in the gclib fork thesword1/gclib, branch py314-compat, then bump the submodule here)
- Add one helper in gclib/bunfoe.py, e.g. `_issubclass(t, cls) = isinstance(t, type) and issubclass(t, cls)`,
  and use it for every `issubclass(<field type>, ...)` in bunfoe.py (get_byte_size, read_value, write_value,
  bitfield paths, etc.) and any other gclib module doing the same on annotation-derived types (grep `issubclass(`).
- Keep 3.12 behaviour identical. No other gclib changes.
- Regression test (gclib repo or this repo's test suite, whichever runs in CI on 3.14): a small @bunfoe class with a
  `list[u16]`/`FixedStr`-style field plus a MappedBool/Enum field, read from bytes and written back, must pass on 3.12 and 3.14.
- Better: also run a gclib-level parse of a real BFN/RARC from the test ISO locally on 3.14
  (`python3.14` exists; ISO path in PROJECT_PLAN.md, never commit or copy it); report the result, don't add it to CI.

## Acceptance criteria
- gclib fork py314-compat has the fix commit pushed; submodule pointer in this repo updated to it.
- scripts/test-quiet.sh passes; CI green on 3.12 and 3.14 including the new test.
- A full local randomize of the test ISO under python3.14 (with imagequant stubbed as android_run.py does) completes,
  or the next 3.14 failure is reported precisely (file:line, exception).

# PLAN — Android real run: output dir + error reporting (device findings after #50)

Device test on master 99cb17f (Y700, Termux Py 3.14): setup incl. native PyFastYaz0Yay0 build OK; a manual
`android_run.py --no-done` run with an existing output dir succeeds (~40 s, ISO + 2 logs). The app run fails:

1. **Output dir never created.** run.sh sets `OUT_DIR="$OUT_BASE/run_$$"` but only mkdirs `$INPUT_DIR $OUT_BASE`;
   gcm.py open(output_iso, "wb") -> FileNotFoundError. Fix: `mkdir -p "$OUT_DIR"` (fail "space" on error) before randomizing.
2. **Real error hidden, stale error shown.** With `--no-done`, android_run.py prints `{"ok":false,"error":<traceback>}` to
   stdout and exits 1; run.sh's `fail "run"` then shows `tail run.log`, which is appended across runs and holds an old error.
   Fix: (a) truncate run.log at the start of each run (`: > "$LOG"`); (b) on randomizer failure, use the `error`
   field of RESULT_JSON (via json_field) as the message when present, else the log tail.
3. **App keeps the previous run's error** on screen while a new run is in progress / after it. Clear error/result
   state when a run starts.
4. **UI nits:** the "WW Randomizer" title overlaps the status bar (apply status-bar/system-bar insets to the top bar);
   the run status line, error text and the Randomize button are not in the uiautomator dump (check they are plain
   Text/Button nodes with text, not merged/cleared semantics), so device tests can read them.

## Acceptance criteria
- shellcheck-clean run.sh; scripts/test-quiet.sh passes; Android unit tests + assembleDebug pass; CI green.
- Unit/JVM test or a shell-level test for item 2 if feasible (e.g. a fake python printing an error JSON and exiting 1
  -> the done message carries that error, not old log text).
- PR body lists device tests: real run succeeds and uploads to the SAF folder; forced failure shows the new error;
  second run shows no stale error; title clears the status bar.
