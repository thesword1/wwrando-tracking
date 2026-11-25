#!/usr/bin/env python3
"""Headless shim the Android app runs inside Termux.

This file lives in this repository (not in the Android app) so the Gradle copy task bundles it with
the same-commit Python tree. It drives WWRandomizer directly, streaming ``PROGRESS done/max desc``
lines and a final ``{"ok": ...}`` status to the app's loopback bridge instead of printing to a tty.
It intentionally does NOT use wwrando.run_no_ui: the app needs each ``randomize()`` yield, so the
generator is iterated here.

The Android app has no Termux imagequant package, and the custom-model path in
gclib/gclib/texture_utils.py imports it unconditionally. A Pillow-quantize stub with the same
``quantize_pil_image`` signature is registered before gclib is imported (no gclib changes).
"""

import inspect
import json
import os
import shutil
import sys
import time
import traceback
import types
import typing
import urllib.request
import zipfile
from enum import StrEnum

# Match wwrando.py: put the bundled gclib submodule on sys.path before any randomizer import.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gclib"))


def make_imagequant_stub():
  """Return a module-like object with gclib's ``imagequant.quantize_pil_image`` signature."""
  from PIL import Image

  def quantize_pil_image(image, dithering_level=1.0, max_colors=256, min_quality=0, max_quality=100):
    # Quantize the RGBA image to <= max_colors palette entries. Pillow keeps fully transparent
    # pixels transparent; alpha fringing is the known "worse alpha" tradeoff of this fallback.
    dither = Image.Dither.FLOYDSTEINBERG if dithering_level > 0 else Image.Dither.NONE
    return image.convert("RGBA").quantize(
      colors=max_colors,
      method=Image.Quantize.FASTOCTREE,
      dither=dither,
    )

  stub = types.ModuleType("imagequant")
  stub.quantize_pil_image = quantize_pil_image
  return stub


def install_imagequant_stub():
  if "imagequant" not in sys.modules:
    sys.modules["imagequant"] = make_imagequant_stub()


class SettingsError(ValueError):
  """A value from --settings-json could not be applied to an option."""


def _is_enum_type(tp):
  return inspect.isclass(tp) and issubclass(tp, StrEnum)


def _convert_settings_value(field, value):
  """Validate/convert one JSON settings value. Returns None when the field is not editable."""
  name = field.name
  tp = field.type
  origin = typing.get_origin(tp)
  args = typing.get_args(tp)

  if tp is bool:
    if not isinstance(value, bool):
      raise SettingsError("bad value for %s: expected true or false" % name)
    return value
  if _is_enum_type(tp):
    if not isinstance(value, str) or value not in [member.value for member in tp]:
      raise SettingsError("bad value for %s: unknown choice %r" % (name, value))
    return tp(value)
  if tp is int:
    if isinstance(value, bool) or not isinstance(value, int):
      raise SettingsError("bad value for %s: expected an integer" % name)
    if field.minimum is not None and value < field.minimum:
      raise SettingsError("bad value for %s: %d below minimum %d" % (name, value, field.minimum))
    if field.maximum is not None and value > field.maximum:
      raise SettingsError("bad value for %s: %d above maximum %d" % (name, value, field.maximum))
    return value
  if tp is str:
    if not isinstance(value, str):
      raise SettingsError("bad value for %s: expected a string" % name)
    return value
  if origin is dict:
    # custom_colors: {color name: [r, g, b]}. Validated structurally here; the
    # randomizer applies only colors whose names are valid for the selected model.
    if not isinstance(value, dict):
      raise SettingsError("bad value for %s: expected an object" % name)
    for key, color in value.items():
      if not isinstance(key, str):
        raise SettingsError("bad value for %s: color names must be strings" % name)
      if not isinstance(color, list) or len(color) != 3 or \
          not all(isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255 for channel in color):
        raise SettingsError("bad value for %s: color %r must be [r, g, b]" % (name, key))
    return value
  if origin is list and args == (str,):
    if field.choices is None:
      return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
      raise SettingsError("bad value for %s: expected a list of strings" % name)
    unknown = [item for item in value if item not in field.choices]
    if unknown:
      raise SettingsError("bad value for %s: unknown choices %r" % (name, unknown))
    return value
  return None


def apply_settings_json(options, path):
  """Apply a {name: value} settings diff on top of the current options. Unknown names are ignored."""
  if not path:
    return
  with open(path, encoding="utf-8") as f:
    data = json.load(f)
  if not isinstance(data, dict):
    raise SettingsError("settings JSON must be an object")
  by_name = options.by_name()
  for name, value in data.items():
    if value is None:
      continue
    field = by_name.get(name)
    if field is None:
      continue
    converted = _convert_settings_value(field, value)
    if converted is None:
      continue
    options[name] = converted


def _safe_extract_zip(zip_path, dest_dir):
  """Extract a normalized model zip into dest_dir, rejecting zip-slip entries."""
  os.makedirs(dest_dir, exist_ok=True)
  with zipfile.ZipFile(zip_path) as zf:
    for info in zf.infolist():
      name = info.filename
      if name.startswith("/") or name.startswith("\\") or os.path.isabs(name):
        raise ValueError("absolute path in model zip: %r" % name)
      if name != "/" and "\\" in name:
        raise ValueError("backslash path in model zip: %r" % name)
      norm = os.path.normpath(name)
      if norm == ".." or norm.startswith(".." + os.sep):
        raise ValueError("path escape in model zip: %r" % name)
      # Normalized model zips contain only regular files and directories.
      mode = (info.external_attr >> 16) & 0o170000
      if mode == 0o120000:
        raise ValueError("symlink in model zip: %r" % name)
      target = os.path.join(dest_dir, name)
      if info.is_dir():
        os.makedirs(target, exist_ok=True)
        continue
      os.makedirs(os.path.dirname(target), exist_ok=True)
      with zf.open(info) as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)


def _valid_model_dir_name(name):
  if not name or name in ("Link", "Random", "Random (exclude Link)"):
    return False
  if "/" in name or "\\" in name or ".." in name or os.path.isabs(name):
    return False
  return True


def sync_models(models_dir, manifest_path):
  """Apply the model manifest produced by run.sh into models_dir.

  manifest_path is a JSON array of {"name": str, "md5": str, "path": str}; "path" is
  the local zip for changed models and "" when the installed copy already matches.
  Each changed model is extracted zip-slip-safe into <name>.tmp and renamed over
  <name>/, then <name>/.md5 records the zip md5. Model dirs absent from the manifest
  are deleted. Returns the number of models that ended up installed.
  """
  with open(manifest_path, encoding="utf-8") as f:
    manifest = json.load(f)
  if not isinstance(manifest, list):
    raise ValueError("model manifest must be a JSON array")

  os.makedirs(models_dir, exist_ok=True)
  kept_names = set()
  for entry in manifest:
    if not isinstance(entry, dict):
      raise ValueError("model manifest entries must be objects")
    name = entry.get("name")
    md5 = entry.get("md5") or ""
    zip_path = entry.get("path") or ""
    if not _valid_model_dir_name(name):
      raise ValueError("invalid model name in manifest: %r" % (name,))
    kept_names.add(name)

    target = os.path.join(models_dir, name)
    md5_file = os.path.join(target, ".md5")
    if os.path.isfile(md5_file):
      with open(md5_file, encoding="utf-8") as f:
        if f.read().strip() == md5:
          continue

    if not zip_path or not os.path.isfile(zip_path):
      raise ValueError("no zip for changed model %r" % (name,))

    tmp_dir = os.path.join(models_dir, name + ".tmp")
    if os.path.exists(tmp_dir):
      shutil.rmtree(tmp_dir, ignore_errors=True)
    _safe_extract_zip(zip_path, tmp_dir)
    if os.path.exists(target):
      shutil.rmtree(target, ignore_errors=True)
    os.rename(tmp_dir, target)
    with open(md5_file, "w", encoding="utf-8") as f:
      f.write(md5)

  # Prune model dirs that are no longer present in the manifest (plus any stale .tmp).
  for entry in os.listdir(models_dir):
    path = os.path.join(models_dir, entry)
    if entry.endswith(".tmp") and os.path.isdir(path):
      shutil.rmtree(path, ignore_errors=True)
      continue
    if os.path.isdir(path) and entry not in kept_names:
      shutil.rmtree(path, ignore_errors=True)

  return len(kept_names)


def _post(port, token, path, body):
  url = "http://127.0.0.1:%d/%s?t=%s" % (port, path, token)
  data = body if isinstance(body, bytes) else body.encode("utf-8")
  req = urllib.request.Request(url, data=data, method="POST")
  req.add_header("Content-Type", "text/plain; charset=utf-8")
  try:
    with urllib.request.urlopen(req, timeout=10) as resp:
      resp.read()
  except Exception:
    # Progress reporting is best-effort; a closed bridge must not kill the randomizer run.
    pass


def _post_json(port, token, path, payload):
  _post(port, token, path, json.dumps(payload))


def build_randomizer_kwargs(args):
  """Mirror wwrando.run_no_ui's option loading and seed/ISO/output resolution."""
  from options.wwrando_options import Options
  from randomizer import WWRandomizer
  from ruamel.yaml import YAML
  from wwrando_paths import SETTINGS_PATH

  yaml = YAML(typ="safe")
  options = Options()
  settings = {}
  if os.path.isfile(SETTINGS_PATH):
    with open(SETTINGS_PATH) as f:
      settings = yaml.load(f) or {}
  for option_name, option_value in settings.items():
    if option_name not in options.by_name():
      continue
    if option_value is None:
      continue
    options[option_name] = option_value

  # App-supplied settings override settings.txt (and are in turn overridden by --permalink below).
  apply_settings_json(options, getattr(args, "settings_json", None))

  seed = settings.get("seed")
  if args.permalink:
    seed, options = WWRandomizer.decode_permalink(args.permalink, options)
  if args.seed:
    seed = args.seed

  clean_iso_path = (args.clean_iso or settings.get("clean_iso_path") or "").strip() or None
  output_folder = (args.output_folder or settings.get("output_folder") or "").strip() or None

  if args.autoseed or not seed:
    from seedgen import seedgen
    seed = seedgen.make_random_seed_name()

  return {
    "seed": seed,
    "clean_iso_path": clean_iso_path,
    "randomized_output_folder": output_folder,
    "options": options,
    "cmd_line_args": args,
  }


def run(args):
  """Randomize one seed and report progress/result to the bridge. Returns the process exit code."""
  from randomizer import WWRandomizer

  port = args.port
  token = args.token
  try:
    kwargs = build_randomizer_kwargs(args)
  except SettingsError as e:
    _finish(args, {"ok": False, "step": "settings", "error": str(e)})
    return 1
  rando = WWRandomizer(**kwargs)
  max_progress = max(1, rando.get_max_progress_length())

  last_post = 0.0

  def report_progress(completed, description):
    nonlocal last_post
    now = time.monotonic()
    if now - last_post < 0.25:
      return
    last_post = now
    _post(port, token, "progress", "PROGRESS %d/%d %s" % (completed, max_progress, description))

  try:
    for description, completed in rando.randomize():
      report_progress(completed, description)
    result = {
      "ok": True,
      "seed": rando.seed,
      "permalink": rando.permalink,
      "seed_hash": rando.seed_hash,
      "dry_run": bool(rando.dry_run),
      "output_folder": rando.randomized_output_folder,
    }
    if not rando.dry_run:
      output_name = rando.get_output_name()
      result["output_name"] = output_name
      result["output_path"] = os.path.join(rando.randomized_output_folder, output_name + ".iso")
    _finish(args, result)
    return 0
  except Exception:
    _finish(args, {"ok": False, "error": traceback.format_exc()[-4000:]})
    return 1


def _finish(args, result):
  """Report the final status. Under --no-done run.sh owns /done, so the JSON goes to stdout instead."""
  if getattr(args, "no_done", False):
    print(json.dumps(result))
  else:
    _post_json(args.port, args.token, "done", result)


def make_argparser():
  # Reuse wwrando's parser so cmd_line_args always carries every attribute WWRandomizer reads
  # (dry, nologs, tracker, disassemble, exportfolder, bulk, ...), then add the bridge extras.
  from wwrando import make_argparser as wwrando_argparser
  parser = wwrando_argparser()
  parser.add_argument("--port", type=int, help="Loopback bridge port.")
  parser.add_argument("--token", help="Loopback bridge token.")
  parser.add_argument(
    "--settings-json", type=str, metavar="PATH",
    help="Apply a {name: value} settings diff on top of settings.txt (permalink still wins).",
  )
  parser.add_argument(
    "--no-done",
    action="store_true",
    help="Print the final result JSON to stdout instead of POSTing /done (run.sh owns /done).",
  )
  parser.add_argument(
    "--sync-models", nargs=2, metavar=("MODELS_DIR", "MANIFEST"),
    help="Sync custom player models from a run.sh manifest and exit (no randomizer run).",
  )
  return parser


def main(argv=None):
  install_imagequant_stub()
  args = make_argparser().parse_args(argv)
  if args.sync_models:
    try:
      count = sync_models(args.sync_models[0], args.sync_models[1])
    except Exception as e:
      print(json.dumps({"ok": False, "step": "models", "error": str(e)}))
      return 1
    print(json.dumps({"ok": True, "models": count}))
    return 0
  if args.port is None or args.token is None:
    print(json.dumps({"ok": False, "step": "bridge", "error": "--port and --token are required"}))
    return 1
  return run(args)


if __name__ == "__main__":
  sys.exit(main())
