# Developer documentation

Notes for working on wwrando-tracking. They aren't part of the public site (`docs/dev/` is excluded in `mkdocs.yml`).
For what the project is and how to use it, see the top-level [README](../../README.md); for the plan and the decisions
behind it, [`PROJECT_PLAN.md`](../../PROJECT_PLAN.md).

| Document | Contents |
|---|---|
| [toolchain.md](toolchain.md) | Python 3.12 environment (uv, the `CFLAGS` quirk for gclib's speedups) and devkitPPC for reassembling the custom ASM/C patches (`tools/devkitppc/assemble.sh`) |
| [dolphin-harness.md](dolphin-harness.md) | `tools/dolphin/`: booting an ISO in flatpak Dolphin, scripted controller input, RAM access, screenshots and savestates |
| [memory-map.md](memory-map.md) | Verified NTSC-U addresses the tracker uses: save layout and the free reserve area, inventory, item get path, sea chart menu input and drawing |
| [tracker-runtime.md](tracker-runtime.md) | The in-game tracker: patch-time tables, C runtime layout, hooks, sea chart UI, save data, detection, logic evaluation, sizes and tests |
| [release.md](release.md) | Building the Linux executable with PyInstaller and the tag-triggered release workflow |

## Where things are

| Path | What |
|---|---|
| `wwrando.py`, `randomizer.py`, `tweaks.py` | Command line, randomizer, patching |
| `aptww.py` | `.aptww` (Archipelago) file loader and the options that stay local in Archipelago mode |
| `options/`, `logic/`, `randomizers/` | Options, logic files and the offline fill |
| `wwr_ui/` | Qt GUI (`offline_options.py` builds the offline option widgets) |
| `tracker/` | Tracker data at patch time: locations, entrances, charts, item map, logic compiler, table serializer |
| `asm/patches/`, `asm/tracker/` | Custom game code; `asm/patch_diffs/` holds the committed assembled results |
| `test/` | pytest suite; `test/fixtures/aptww/` has `.aptww` fixtures (`tools/aptww_fixtures/` regenerates them) |
| `tools/` | `devkitppc/` (assembler container), `dolphin/` (harness), `aptww_fixtures/`, `parity/` (Archipelago parity helpers) |

## Tests

```sh
WW_RANDO_OUTPUT_DIR=/tmp/wwrando-out QT_QPA_PLATFORM=offscreen pytest test -m "not saving" -q
```

Markers (`pytest.ini`): `saving` tests read and write game files and need a vanilla ISO; `dolphin` tests also launch
flatpak Dolphin (`WW_ISO_PATH=/path/to/iso pytest -m dolphin`); `slow` runs long seed matrices. CI (`test.yml`) runs
`-m "not saving"` on Ubuntu, and `asm.yml` checks that the committed patch diffs are reproducible.

## Workflow

Trunk-based: short-lived `feature/`, `fix/`, `docs/`, `ci/`, `chore/` or `tooling/` branches, one squash-merged PR each
into `master`, with a `CHANGELOG.md` entry per feature. Never commit a Wind Waker ISO or any extracted game files.
