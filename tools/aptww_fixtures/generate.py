#!/usr/bin/env python3
"""
Dev-only: regenerate the .aptww test fixtures in test/fixtures/aptww/.

Each YAML in tools/aptww_fixtures/yamls/ is generated as its own single-player
Archipelago multiworld with a fixed seed, and the resulting .aptww is copied
to test/fixtures/aptww/<yaml name>.aptww. See README.md in this folder.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YAML_DIR = Path(__file__).resolve().parent / "yamls"
DEFAULT_OUT_DIR = REPO_ROOT / "test" / "fixtures" / "aptww"

# The only entries an .aptww is expected to contain. Anything else could be game data and must not be committed.
EXPECTED_ENTRIES = {"archipelago.json", "plando"}

# Fixed timestamp for repacked zip entries so regenerating unchanged fixtures produces no git diff.
ZIP_DATE_TIME = (1980, 1, 1, 0, 0, 0)


def main():
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("archipelago", type=Path, help="Path to an Archipelago source checkout (not modified).")
  parser.add_argument("--python", default=sys.executable,
                      help="Python interpreter with Archipelago's requirements installed (default: this one).")
  parser.add_argument("--seed", type=int, default=1, help="Archipelago seed used for every fixture (default: 1).")
  parser.add_argument("--yamls", type=Path, default=DEFAULT_YAML_DIR, help="Folder of player YAMLs.")
  parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Folder to write the .aptww fixtures to.")
  parser.add_argument("--only", nargs="*", help="Only generate these YAMLs (file stems).")
  args = parser.parse_args()

  ap_dir = args.archipelago.resolve()
  if not (ap_dir / "Generate.py").is_file() or not (ap_dir / "worlds" / "tww").is_dir():
    parser.error(f"{ap_dir} does not look like an Archipelago checkout with the TWW world")

  yaml_paths = sorted(args.yamls.glob("*.yaml"))
  if args.only:
    yaml_paths = [p for p in yaml_paths if p.stem in args.only]
  if not yaml_paths:
    parser.error(f"No YAMLs to generate in {args.yamls}")

  args.out.mkdir(parents=True, exist_ok=True)

  with tempfile.TemporaryDirectory(prefix="aptww_fixtures_") as tmp:
    tmp = Path(tmp)
    # Archipelago writes host.yaml, logs, and caches into its own folder, so run it from a copy.
    ap_copy = tmp / "Archipelago"
    print(f"Copying {ap_dir} -> {ap_copy}")
    shutil.copytree(ap_dir, ap_copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "output", "logs"))

    for yaml_path in yaml_paths:
      generate_fixture(args, ap_copy, yaml_path, tmp / yaml_path.stem)

  print(f"Archipelago version: {read_ap_version(ap_dir)}")
  print(f"TWW APWorld version: {read_tww_version(ap_dir)}")


def generate_fixture(args, ap_copy: Path, yaml_path: Path, work_dir: Path):
  players_dir = work_dir / "players"
  output_dir = work_dir / "output"
  players_dir.mkdir(parents=True)
  output_dir.mkdir()
  shutil.copy(yaml_path, players_dir / yaml_path.name)

  print(f"Generating {yaml_path.name} (seed {args.seed})")
  env = dict(os.environ, SKIP_REQUIREMENTS_UPDATE="1")
  subprocess.run(
    [
      args.python, "Generate.py",
      "--player_files_path", str(players_dir),
      "--outputpath", str(output_dir),
      "--seed", str(args.seed),
      "--spoiler", "0",
    ],
    cwd=ap_copy, env=env, check=True, stdout=subprocess.DEVNULL,
  )

  multiworld_zips = list(output_dir.glob("AP_*.zip"))
  if len(multiworld_zips) != 1:
    raise RuntimeError(f"Expected exactly one multiworld zip in {output_dir}, found {multiworld_zips}")
  with zipfile.ZipFile(multiworld_zips[0]) as multiworld_zip:
    aptww_names = [name for name in multiworld_zip.namelist() if name.endswith(".aptww")]
    if len(aptww_names) != 1:
      raise RuntimeError(f"Expected exactly one .aptww in {multiworld_zips[0]}, found {aptww_names}")
    aptww_bytes = multiworld_zip.read(aptww_names[0])

  raw_path = work_dir / "raw.aptww"
  raw_path.write_bytes(aptww_bytes)
  out_path = args.out / f"{yaml_path.stem}.aptww"
  repack_aptww(raw_path, out_path)
  print(f"  -> {out_path.relative_to(REPO_ROOT) if out_path.is_relative_to(REPO_ROOT) else out_path}")


def repack_aptww(src: Path, dst: Path):
  """Copy the .aptww zip with fixed entry timestamps, refusing anything but the expected entries."""
  with zipfile.ZipFile(src) as zin:
    names = set(zin.namelist())
    if names != EXPECTED_ENTRIES:
      raise RuntimeError(f"{src} has unexpected entries {sorted(names)}; expected {sorted(EXPECTED_ENTRIES)}")
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
      for name in sorted(names):
        info = zipfile.ZipInfo(name, date_time=ZIP_DATE_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        zout.writestr(info, zin.read(name))


def read_ap_version(ap_dir: Path) -> str:
  match = re.search(r'^__version__ = "([^"]+)"', (ap_dir / "Utils.py").read_text(), re.MULTILINE)
  return match.group(1) if match else "unknown"


def read_tww_version(ap_dir: Path) -> str:
  text = (ap_dir / "worlds" / "tww" / "__init__.py").read_text()
  match = re.search(r"^VERSION: .*= \((\d+), (\d+), (\d+)\)", text, re.MULTILINE)
  return ".".join(match.groups()) if match else "unknown"


if __name__ == "__main__":
  main()
