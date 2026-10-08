#!/usr/bin/env python3
"""
Dev-only: dump the location category flags of the Archipelago TWW world (worlds/tww/Locations.py, LOCATION_TABLE)
to test/fixtures/apworld_location_flags.json. test/test_offline_parity.py compares them with the randomizer's location
types to check that offline seeds have the same progress locations as the APWorld for every combination of the
progression location options.

Run it with a Python that has Archipelago's core requirements installed (see tools/aptww_fixtures/README.md):
  ap-venv/bin/python tools/parity/dump_apworld_location_flags.py /path/to/Archipelago
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "test" / "fixtures" / "apworld_location_flags.json"


def main():
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("archipelago", type=Path, help="Path to an Archipelago source checkout.")
  parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
  args = parser.parse_args()
  
  sys.path.insert(0, str(args.archipelago.resolve()))
  from worlds.tww.Locations import LOCATION_TABLE, TWWFlag
  from worlds.tww import VERSION
  
  location_flags = {}
  for location_name, data in LOCATION_TABLE.items():
    if data.code is None:
      continue # Events (Defeat Ganondorf).
    location_flags[location_name] = sorted(flag.name for flag in TWWFlag if flag in data.flags)
  
  output = {
    "source": "Archipelago worlds/tww/Locations.py LOCATION_TABLE (MIT license, Archipelago contributors)",
    "apworld_version": list(VERSION),
    "locations": location_flags,
  }
  # One location per line so diffs stay readable.
  lines = ["{"]
  lines.append(f' "source": {json.dumps(output["source"])},')
  lines.append(f' "apworld_version": {json.dumps(output["apworld_version"])},')
  lines.append(' "locations": {')
  entries = [f'  {json.dumps(name)}: {json.dumps(flags)}' for name, flags in location_flags.items()]
  lines.append(",\n".join(entries))
  lines.append(" }")
  lines.append("}")
  args.out.write_text("\n".join(lines) + "\n")
  print(f"Wrote {len(location_flags)} locations to {args.out}")


if __name__ == "__main__":
  main()
