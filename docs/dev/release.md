# Building and releasing

Developer notes for the Linux release build. Windows and macOS builds aren't maintained in this fork (upstream's
multi-platform workflow, `.github/workflows/python-app.yml`, is kept but only runs when started by hand).

## Building locally

From a source checkout with the Python 3.12 environment from `toolchain.md` (`requirements_full.txt` includes
PyInstaller):

```sh
git submodule update --init
python -m PyInstaller --log-level=WARN wwrando.spec
python build.py
```

PyInstaller writes a one-file executable, `dist/wwrando-tracking`. `build.py` moves it into
`dist/wwrando-<version>-linux-x64/` together with `README.txt`, `LICENSE.txt` and `models/About Custom Models.txt`,
and packs that folder into `dist/wwrando-<version>-linux-x64.tar.gz`. `<version>` is `version.txt`.

The executable unpacks itself into a temporary folder on every start, so it takes a few seconds to open. Like
upstream's frozen builds, it keeps `settings.txt` and looks for custom models (`models/`) in the current working
directory, so start it from its own folder.

The executable only runs on systems with a glibc at least as new as the one it was built on. A build made on a
current Fedora/Nobara won't start on older distros; the release workflow builds on Ubuntu 22.04 for that reason.

Quick check of a build:

```sh
cd dist/wwrando-*-linux-x64
./wwrando-tracking --version
./wwrando-tracking                       # GUI
./wwrando-tracking --noui --autoseed --clean-iso /path/to/vanilla.iso --output-folder /path/to/out
```

## Release workflow

`.github/workflows/release.yml` runs on Ubuntu 22.04:

- **Tag push `v*`** (for example `v2.5.2-tracking.1`): writes the tag without the leading `v` into `version.txt`,
  builds with PyInstaller and `build.py`, smoke-tests the executable (`--version`, `--help`, and the GUI staying up
  for 30 s with `QT_QPA_PLATFORM=offscreen`), uploads the tarball as a workflow artifact and creates a GitHub Release
  for the tag with the tarball attached.
- **Manual run** (`workflow_dispatch`, optional `version` input, default `version.txt`): the same build and smoke test,
  uploaded as a workflow artifact only. No release is created.

The version is part of every permalink, so a seed generated with a release can only be reproduced by the same release.
(Source checkouts add the commit to the version.) Unlike upstream's build, the workflow doesn't write a seed key
(`keys/seed_key.py`). No ISO or game files are part of the build or the release.

To release:

```sh
git tag v2.5.2-tracking.1 origin/master
git push origin v2.5.2-tracking.1
gh run watch --repo thesword1/wwrando-tracking   # pick the Release run
```
