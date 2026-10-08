# Offline / Archipelago parity

`test/test_offline_parity.py` checks that offline seeds match the Archipelago TWW world (APWorld 3.0.0):

- **Progress locations, per category**: `test/fixtures/apworld_location_flags.json` holds the category flags of every
  APWorld location. A location is a progress location when all of its categories are enabled, both offline and in the
  APWorld, so comparing the options each location needs covers every combination of the 23 `progression_*` options.
- **Progress locations, per option set**: for each `.aptww` fixture (`test/fixtures/aptww/`), the offline progress
  locations computed with the fixture's options, chart mapping and required bosses must equal the plando's Locations.
- **Beatability**: offline seeds generated with each fixture's options. 3 seeds per fixture run in CI; 40 more per
  fixture run with `pytest test/test_offline_parity.py -m slow` (about 2-3 minutes).

Known differences that don't change the progress locations:

- Dungeon items are never placed on bosses offline (the APWorld allows it when boss entrances aren't randomized).
- Offline seeds give every non-progress location a random item. The APWorld only creates its progress locations.
- The APWorld also makes dungeons with priority locations required bosses. There are no priority locations offline.
- `enable_tuner_logic` isn't in `.aptww` files, so the parity tests take it from the fixture YAMLs.

## Regenerating the flag dump

```sh
ap-venv/bin/python tools/parity/dump_apworld_location_flags.py /path/to/Archipelago
```

See `tools/aptww_fixtures/README.md` for setting up `ap-venv`. Errors about other worlds failing to import are harmless.
Archipelago is never needed to run the tests.
