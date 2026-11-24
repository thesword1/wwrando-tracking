# PLAN — Android: first-run setup + headless run (roadmap #2)

Context: docs/android-app-plan.md §2–§4, §9 items 2–3. Skeleton (PR #42) already runs a hello shim in
Termux via RUN_COMMAND (`android/app/.../data/RandoCommandRunner.kt`, `RandoScriptInstaller.kt`).
ISO picking (SAF), foreground service and Dolphin launch are NOT in this PR (next milestone).

## Design
1. **Bundle as one archive.** Gradle packs the already-copied tree (`copyRandomizerPython` output)
   into `assets/wwrando.tar.gz` plus `assets/wwrando.sha256` (hash of the archive). Keep the
   existing include/exclude list (no Qt/GUI code).
2. **Loopback bridge (no shared storage).** New `data/LoopbackBridge.kt`: a `ServerSocket` bound to
   127.0.0.1 on a random port, with a random 32-hex token required on every request
   (`?t=<token>` or header). Endpoints: `GET /tree` streams the asset archive; `POST /progress`
   accepts newline-separated progress lines; `POST /done` takes final status JSON. Exposes a
   `Flow<ProgressEvent>`. Closed when the job ends or on cancel. Add INTERNET permission
   (loopback only; document why in the manifest comment).
3. **setup.sh** (bundled asset, sent on stdin, < 16 KB): args port, token, hash. Steps, each
   reporting a `STEP <n>/<total> <label>` line via `curl -fsS --data-binary` to /progress:
   `pkg install -y python python-numpy python-pillow curl` (skip if present), curl /tree to
   `~/wwrando/releases/<hash>.tar.gz`, extract to `~/wwrando/releases/<hash>/`, venv
   `~/wwrando/venv` with `--system-site-packages`, `pip install` the pure-Python pins from
   requirements.txt (ruamel.yaml, appdirs, certifi, tqdm; NOT Qt, NOT imagequant, NOT gclib
   speedups), atomically point `~/wwrando/current` symlink at the release, write
   `~/wwrando/installed.sha256`. Idempotent: if installed hash == bundled hash and venv imports
   work, report `SKIP up-to-date`. Any failure: POST /done `{"ok":false,"step":..,"error":..}`
   with the last 20 lines of stderr.
4. **android_run.py shim** (bundled under the tree, not in wwrando.py): inserts a stub
   `imagequant` module into `sys.modules` (Pillow `quantize()` fallback with the same
   `quantize_pil_image` signature used in `gclib/gclib/texture_utils.py:830`), then builds the
   same args as `wwrando.py --noui` (accepts `--permalink|--seed|--autoseed`, `--clean-iso`,
   `--output-folder`, `--dry`, `--tracker/--no-tracker`, `--nologs`) and iterates
   `rando.randomize()` itself, POSTing `PROGRESS <done>/<max> <description>` lines
   (`get_max_progress_length()`), throttled to <= 4/s. On exception POST /done with the
   traceback tail; on success POST /done with seed, permalink, seed hash, output paths.
   No gclib submodule changes.
5. **RUN_COMMAND permission request.** On launch, if
   `com.termux.permission.RUN_COMMAND` is not granted, request it with
   `ActivityCompat.requestPermissions`; if denied twice, show a card with the Settings intent and
   the `allow-external-apps = true` Termux property hint. Detect Termux missing / too old
   (< 0.118) and show an install hint.
6. **UI** (keep MainActivity small; new composables/files): status card (Termux, permission,
   setup state + step progress bar + log tail), "Run setup" / "Re-run setup", and a "Dry run"
   section: seed text field (blank = autoseed), "Dry run" button streaming PROGRESS into a
   progress bar, result shows seed hash + permalink. "Cancel" kills the job (RUN_COMMAND a
   `pkill -f android_run.py`) and closes the bridge.

## Acceptance criteria
- `./gradlew assembleDebug testDebugUnitTest` passes in CI; APK size noted in the PR.
- Unit tests (JVM): LoopbackBridge rejects bad/missing token (403), serves /tree bytes intact,
  parses STEP/PROGRESS/done lines into events; progress-line parser handles malformed lines.
- Python: `test/test_android_run.py` runs the shim with `--dry --seed test` against a local
  HTTP stub and asserts PROGRESS lines are monotonic and /done reports ok; the imagequant stub
  works without imagequant installed. Passes via scripts/test-quiet.sh.
- `bash -n setup.sh` and shellcheck clean (if shellcheck available).
- No source file over 400 lines; MainActivity stays a thin host.
- PR body lists the device-test steps for the main session (setup from clean Termux, re-run =
  SKIP, dry run with seed, cancel mid-run, permission denied path).

# PLAN — Python 3.14 compat via gclib fork (roadmap #2 follow-up)

Device test: Termux ships only Python 3.14; gclib (submodule, pinned d932252) breaks on 3.13+.
Fork: github.com/thesword1/gclib (exists). Keep the fix minimal and upstreamable; 3.12 behaviour unchanged.

## gclib changes (branch `py314-compat` from d932252, in the fork)
1. `gclib/bunfoe.py:72` `@dataclasses._recursive_repr` (removed in 3.13) -> `@reprlib.recursive_repr()`.
2. `gclib/bunfoe.py:134` `cls.__dict__.get('__annotations__', {})` silently returns `{}` on 3.14
   (PEP 649/749), which would drop every BUNFOE field. Use `inspect.get_annotations(cls)` (own
   annotations only, 3.10+).
3. `gclib/jpa.py:28-34` and `gclib/j3d.py:40-46`: `CHUNK_TYPES` is built from `__annotations__`
   inside the class body (NameError on 3.14). Build it right after the class instead, from
   `inspect.get_annotations(<Class>)`, same dict contents. `type(self).__annotations__`
   (jpa.py:116, j3d.py:119) works on 3.14; switch to `inspect.get_annotations(type(self))` for
   consistency.
4. Grep the whole fork for any other `__annotations__` / `dataclasses._` private use and fix alike
   (`dataclasses._process_class` is fine: same signature on 3.12 and 3.14).
Commit with the noreply identity, push branch `py314-compat` to the fork (remote url
https://github.com/thesword1/gclib.git); do not open an upstream PR.

## wwrando changes (this branch)
- `.gitmodules`: gclib url -> https://github.com/thesword1/gclib.git; bump the submodule to the
  `py314-compat` commit (`git submodule sync`).
- `.github/workflows/test.yml`: run the pytest job on a matrix of Python 3.12 and 3.14.
- `test/test_android_run.py`: no change needed unless 3.14 exposes something.

## Acceptance criteria
- `scripts/test-quiet.sh` passes on 3.12 (repo .venv).
- Same suite passes on 3.14: a uv venv `-p 3.14` with requirements.txt minus Qt (or all of it if it
  installs), `pytest test -m "not saving" -q`. Report both counts.
- `android_run.py --port 9 --token x --dry --seed test --output-folder <tmp>` exits 0 on 3.14 with
  imagequant NOT installed.
- Dry-run spoiler log for `--seed test` is byte-identical between 3.12 and 3.14 (proves no silent
  field loss).
