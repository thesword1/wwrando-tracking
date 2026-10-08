# .aptww test fixtures

Dev-only tooling that generates the small `.aptww` files in `test/fixtures/aptww/`. Tests use them to exercise the Archipelago (AP) mode code paths without needing a working Archipelago install.

An `.aptww` is a zip with two entries: `archipelago.json`, which holds AP container metadata (version, player slot and name, game), and `plando`, which is base64-encoded YAML. The YAML has these keys: `Version`, `Seed`, `Slot`, `Name`, `Options`, `Required Bosses`, `Locations`, `Entrances` and `Charts`. The files hold no game data. `generate.py` refuses to write a fixture if the zip contains any other entry.

## Fixtures

Every fixture is a single-player multiworld with the player name `Player`, generated with AP seed `1`.

| Fixture | YAML | Covers |
|---|---|---|
| `defaults.aptww` | `yamls/defaults.yaml` | Every TWW option at its APWorld default. |
| `progression_all.aptww` | `yamls/progression_all.yaml` | All 23 `progression_*` location categories on. |
| `entrance_rando.aptww` | `yamls/entrance_rando.yaml` | Dungeon, secret cave, inner cave, miniboss, boss and fairy fountain entrances randomized; `mix_entrances: mix_pools` (nested); random starting island; combat caves and Savage Labyrinth on. |
| `charts_required_bosses.aptww` | `yamls/charts_required_bosses.yaml` | `randomize_charts` with triforce and treasure chart progression; required bosses mode (3 bosses, DRC included, WT excluded). |
| `keys_swords_tuner.aptww` | `yamls/keys_swords_tuner.yaml` | `randomize_smallkeys: keylunacy`, `randomize_bigkeys: local`, `randomize_mapcompass: any_dungeon`, `sword_mode: swords_optional`, `enable_tuner_logic`, tingle chests, normal obscurity and precision. |

Note: `enable_tuner_logic` affects AP's logic and item classification, but the APWorld does not write it to the `.aptww` `Options`. It is only sent in AP slot data.

## Generated with

- Archipelago **0.6.9**, from the source tree at `Archipelago-main/`. That tree is a source download without git metadata, so no commit hash is available.
- TWW APWorld **3.0.0** (`worlds/tww/__init__.py` `VERSION`, written to each plando's `Version`).
- Python 3.12.

## Regenerating

You need Python 3.11 to 3.13 with Archipelago's core requirements installed. Many other worlds fail to import without their own dependencies, and that is harmless. One way to set it up:

```sh
uv venv -p 3.12 ap-venv
uv pip install -p ap-venv/bin/python PyYAML jellyfish jinja2 schema platformdirs certifi cython orjson typing_extensions colorama websockets bsdiff4 cymem pathspec
ap-venv/bin/python tools/aptww_fixtures/generate.py /path/to/Archipelago
```

The script copies the Archipelago checkout to a temporary folder, because Archipelago writes `host.yaml`, logs and caches into its own directory. It runs `Generate.py` once per YAML with `SKIP_REQUIREMENTS_UPDATE=1`, extracts the `.aptww` from the multiworld zip, and repacks it with fixed timestamps so regenerating produces no diff. The plando contents are deterministic for a given seed, Archipelago version and APWorld version.

Useful flags:
- `--only defaults entrance_rando` regenerates only some fixtures.
- `--seed N` uses a different seed, for example if a YAML fails to generate.
- `--python PATH` runs Archipelago with a different interpreter.

To add a fixture, add a YAML to `yamls/`, regenerate, then add its expected options to `EXPECTED_OPTIONS` in `test/test_aptww_fixtures.py`. If you regenerate with a different Archipelago or APWorld version, update the versions above.
