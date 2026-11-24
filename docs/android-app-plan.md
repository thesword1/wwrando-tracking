# Android randomizer app plan (Wind Waker Randomizer for Android)

A standalone Android app, `io.github.thesword1.wwrando`, that lives in this repository next to the
Linux and Windows builds. A native Kotlin/Compose UI drives the desktop randomizer's existing headless
CLI inside Termux. It never downloads game files and never bundles a game: the user supplies their own
Wind Waker GameCube ISO.

## 1. Runtime choice: Termux backend (decision made)

- Bundle this repository's own Python sources in the APK as assets. They are copied at build time from
  the *same commit the build is on* (plus the gclib submodule) — never fetched from a tag and never
  committed twice. On first run the app installs them into Termux by piping the source tree over
  `RUN_COMMAND` stdin, using the `RandoScriptInstaller`/`RandoCommandRunner` classes under
  `android/app/src/main/java/io/github/thesword1/wwrando/data/`.
- Run the CLI in Termux with `python ~/wwrando/wwrando.py --noui ...` via the same RUN_COMMAND
  foreground-service intent. RUN_COMMAND returns stdout only at exit, so progress is streamed back
  through a file the app polls (see section 4).
- Chaquopy (embedded CPython) is the later fallback if Termux becomes a hard limit (no Termux
  installed, memory, Play policy). Mentioned here only; not built now.

## 2. Runtime dependencies (this repo @ the build commit + gclib submodule)

`requirements.txt` pins QtPy, PySide6, ruamel.yaml, pillow, appdirs, certifi, tqdm, plus
`gclib/requirements.txt` (imagequant, numpy, pillow, cffi/pycparser) and the optional
`gclib[speedups]` git deps (pyfastbti, pyfasttextureutils, pyfastyaz0yay0).

| Dep | Kind | Android (Termux) |
|---|---|---|
| QtPy, PySide6/PyQt5 | GUI | CUT. Also cut Qt modules in `wwr_ui/` (`randomizer_window`, `cosmetic_tab`, `offline_options`, `qt_init`, `uic/`). KEEP pure-data `wwr_ui/inventory.py` (imported by `randomizer.py`); drop `wwr_ui/update_checker.py`. |
| ruamel.yaml | pure Python (optional `ruamel.yaml.clib` C speedup) | pip install; speedup optional |
| pillow | C extension | `pkg install python-pillow` or pip wheel |
| numpy | C extension | `pkg install python-numpy` or pip wheel |
| cffi, pycparser | C / pure | pip install (needed by imagequant) |
| imagequant | cffi -> libimagequant C | No Termux pkg/wheel. Used only for palettized RGBA textures (custom models/skins). Fallback: patch gclib to lazy-import it and use Pillow `quantize()` (worse alpha; fine for v1). |
| pyfastbti / pyfasttextureutils / pyfastyaz0yay0 | optional C speedups | SKIP: gclib guards them with `try: import ... except ImportError` and has pure-Python fallbacks (slower, correct). |
| appdirs, certifi, tqdm | pure Python | pip install |

Termux ships Python 3.14 while the project pins 3.12; the runtime path has no 3.12-only syntax, but
first-run setup installs exact pins via pip in a venv to avoid Termux pkg drift, falling back to `pkg`
for numpy/pillow where pip wheels fail.

## 3. Driving the randomizer headless

Existing entry point: `wwrando.py --noui`. v1 command:
`python ~/wwrando/wwrando.py --noui --permalink <p>|--seed <s>|--autoseed --clean-iso <iso> --output-folder <dir> [--tracker] [--nologs]`.
`run_no_ui()` loads `settings.txt` first, then applies permalink/seed/ISO/output overrides, so the same
path also drives presets.

Minimum API the bundled shim uses (no new GUI code):
- `randomizer.WWRandomizer(seed, clean_iso_path, randomized_output_folder, options, ...)`.
- `rando.randomize()` is a generator yielding `(description, progress_completed)`; total from
  `get_max_progress_length()`. A thin bundled shim prints each yield as a progress line instead of
  `randomize_all()` silently consuming it.
- `randomizer.py:verify_correct_clean_iso_md5` already rejects a non-vanilla NA ISO (the well-known
  vanilla NA ISO MD5), so the app just surfaces that error.
- Cancel: no in-process cancel; v1 kills the Termux command, and `randomizer.py` already deletes the
  half-written output ISO on error.

## 4. Android I/O

- Input ISO (~1.4 GB): pick once via SAF `ACTION_OPEN_DOCUMENT` (`*/*`; GameCube ISOs have no
  reliable MIME type) and persist the URI. The app pre-verifies the MD5 in-app and, on the first
  real run, streams the ISO to Termux over the token-guarded loopback bridge (`GET /iso`); Termux
  caches it under `~/wwrando/input/clean.iso` with a sidecar `.md5` so later runs skip the copy.
  No shared storage and no `termux-setup-storage` are used.
- Output: SAF `ACTION_OPEN_DOCUMENT_TREE`, persisted like the ISO grant. Termux writes the ISO/logs
  to its private `~/wwrando/out/<job>` and uploads each file back over the bridge
  (`POST /output?name=...&dir=...`); the app creates one subfolder
  `<seed-hash-or-seed>_<yyyyMMdd-HHmmss>` in the picked tree per run. The same tree grant later
  builds content:// links for Dolphin (plain `file://` paths fail there, so "Play" sends a granted
  `content://` URI).
- Space: input (1.4 GB) + output ISO (1.4 GB) free; run.sh checks `df -k ~` before starting.
  `gclib/gcm.py` reads and exports file-by-file (unchanged bytes streamed), so peak RAM is the
  largest game file (tens of MB) plus Termux Python, not the whole ISO.
- Long-running work: the app's own `dataSync` foreground service holds a notification with progress,
  owns the bridge and the Termux RUN_COMMAND job, and updates the notification from the bridge's
  STEP/PROGRESS events while randomization runs.

## 5. UI scope v1

- Home: pick/verify clean ISO (MD5 badge), `termux-setup-storage` status, output folder, first-run
  setup progress.
- Randomize: permalink paste + share, seed entry / autoseed, a settings preset (v1 = saved
  `settings.txt` defaults, not full editing), Randomize, progress from the stream.
- Generated ISOs list: seed, permalink, date, size; "Delete old"; "Play" opens Dolphin via the
  granted content:// link.
- Logs: spoiler log and tracker hints viewable in-app.
- Later: settings screens generated from `options/wwrando_options.py` definitions, `.aptww` import,
  in-game tracker bridge.

## 6. Gradle layout

- Standalone Gradle project under `android/` with its own `settings.gradle.kts` and Gradle wrapper; a
  single `:app` module with `namespace`/`applicationId` `io.github.thesword1.wwrando`, minSdk 31 /
  targetSdk 36, and its own launcher label/icon. The app's Kotlin sources and the Termux bridge classes
  live under `android/app/src/`.
- Python sources are not committed twice: a Gradle `Sync` task
  (`copyRandomizerPython` in `android/app/build.gradle.kts`) copies this repo's Python tree — including
  the gclib submodule, but excluding Qt/GUI-only files — into generated assets at build time. Committed
  assets hold only a tiny hello shim under `python/hello.py`, so `assembleDebug` still works without
  the surrounding checkout (the copy task just copies whatever is present).
- CI signs the debug APK with the stable debug key the repo's CI already uses for its debug-signing
  secrets, exposed to Gradle as the `GM_DEBUG_KEYSTORE*` env vars (alias `wwrdebug`, PKCS12). When the
  secret is absent the default Android debug key is used.

## 7. CI

`.github/workflows/android.yml`:
- Checkout with `submodules: recursive` so the gclib submodule is present for the copy task.
- `./gradlew --no-daemon assembleDebug testDebugUnitTest` (run in `android/`), uploads the
  `:app` debug APK as an artifact, signed with the stable debug keystore secret when it exists and
  falling back to the default debug key otherwise.
- Release signing/upload of an Android artifact is intentionally out of scope for now (see the note in
  `.github/workflows/release.yml`).

## 8. Legal

Never bundle or download game files. The APK ships only this repository's open-source randomizer code
(GPL/MIT; check each module's license) and the user supplies their own ISO. No Nintendo assets are
included.

## 9. Milestones (PR-sized steps)

1. (this PR) Plan + standalone `android/` skeleton: hello shim run in Termux via RUN_COMMAND, CI builds
   the debug APK from the in-repo sources and uploads it as an artifact.
2. First-run setup: bundle the copied tree, install into Termux, pin deps via pkg/pip, status screen.
3. Headless run: ISO pick + copy + MD5 verify, run `wwrando.py --noui`, progress file + foreground
   service notification, cancel.
4. Outputs: generated-ISO list, spoiler log / tracker hints viewer, Delete old, Play -> Dolphin
   content:// link.
5. Settings: presets + generated settings screens, permalink share, seed history.
6. Later: `.aptww` import, Chaquopy fallback if Termux limits bite, signed Android release asset.
