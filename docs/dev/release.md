# Building and releasing

Developer notes for the Linux and Windows release builds. macOS builds aren't maintained in this fork (upstream's
multi-platform workflow, `.github/workflows/python-app.yml`, is kept but only runs when started by hand).

## Building locally

From a source checkout with the Python 3.12 environment from `toolchain.md` (`requirements_full.txt` includes
PyInstaller):

```sh
git submodule update --init
python -m PyInstaller --log-level=WARN wwrando.spec
python build.py
```

PyInstaller writes a one-file executable, `dist/wwrando-tracking` (`dist/wwrando-tracking.exe` on Windows, with
`assets/icon.ico` as its icon). `build.py` moves it into `dist/wwrando-<version>-<platform>/` together with
`README.txt`, `LICENSE.txt` and `models/About Custom Models.txt`, and packs that folder into
`dist/wwrando-<version>-linux-x64.tar.gz` or `dist/wwrando-<version>-windows-x64.zip`. `<version>` is `version.txt`.

The same commands work on Windows (Python 3.12 and the MSVC build tools for gclib's native speedups; the GitHub
`windows-latest` runner has both). The executable is a console program with PyInstaller's `hide_console="hide-early"`:
started from Explorer, its console window is hidden at once, so only the GUI shows; started from a terminal, `--version`,
`--help` and `--noui` print there as on Linux.

The data files the randomizer reads at runtime (`asm/*.txt|rel|plf`, `asm/patch_diffs/`, `assets/`, `data/`,
`logic/*.txt`, `seedgen/*.txt`, `wwr_ui/*.ui`, `version.txt`) are listed in `wwrando.spec`'s `datas`. Python packages
(`tracker/`, `randomizers/`, ...) are found by PyInstaller's import analysis. A new kind of data file needs a new
`datas` entry and a matching path in the release workflow's bundle check.

The executable unpacks itself into a temporary folder on every start, so it takes a few seconds to open. Like
upstream's frozen builds, it keeps `settings.txt` and looks for custom models (`models/`) in the current working
directory, so start it from its own folder.

The executable only runs on systems with a glibc at least as new as the one it was built on. A build made on a
current Fedora/Nobara won't start on older distros; the release workflow builds on Ubuntu 22.04 for that reason.

Quick check of a Linux build:

```sh
cd dist/wwrando-*-linux-x64
./wwrando-tracking --version
./wwrando-tracking                       # GUI
./wwrando-tracking --noui --autoseed --clean-iso /path/to/vanilla.iso --output-folder /path/to/out
```

## Release workflow

`.github/workflows/release.yml` builds Linux (Ubuntu 22.04) and Windows (`windows-latest`) in parallel. Each build job:

1. writes the version into `version.txt` (the tag without the leading `v`, or the `version` input / `version.txt` for
   a manual run),
2. builds with PyInstaller and `build.py`,
3. checks that every runtime data file tracked by git is inside the executable (`pyi-archive_viewer --list`),
4. smoke-tests the executable: `--version` prints the version, `--help` works, two dry randomizations without an ISO
   (an offline seed with `--noui --dry --autoseed`, and `--dry --aptww test/fixtures/aptww/defaults.aptww`) finish
   and write logs, and the GUI is still running after 30 s with `QT_QPA_PLATFORM=offscreen`,
5. uploads the archive as a workflow artifact (`wwrando-<version>-linux-x64` / `wwrando-<version>-windows-x64`).

- **Tag push `v*`** (for example `v2.5.2-tracking.2`): after both builds pass, a final job downloads both artifacts
  and creates a GitHub Release for the tag with the `.tar.gz` and the `.zip` attached.
- **Manual run** (`workflow_dispatch`, optional `version` input): the builds and tests only, no release.

The version is part of every permalink, so a seed generated with a release can only be reproduced by the same release.
(Source checkouts add the commit to the version.) Unlike upstream's build, the workflow doesn't write a seed key
(`keys/seed_key.py`). No ISO or game files are part of the build or the release.

To release:

```sh
git tag v2.5.2-tracking.1 origin/master
git push origin v2.5.2-tracking.1
gh run watch --repo thesword1/wwrando-tracking   # pick the Release run
```
