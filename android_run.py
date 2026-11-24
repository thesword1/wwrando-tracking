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

import json
import os
import sys
import time
import traceback
import types
import urllib.request

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
  rando = WWRandomizer(**build_randomizer_kwargs(args))
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
  parser.add_argument("--port", type=int, required=True, help="Loopback bridge port.")
  parser.add_argument("--token", required=True, help="Loopback bridge token.")
  parser.add_argument(
    "--no-done",
    action="store_true",
    help="Print the final result JSON to stdout instead of POSTing /done (run.sh owns /done).",
  )
  return parser


def main(argv=None):
  install_imagequant_stub()
  args = make_argparser().parse_args(argv)
  return run(args)


if __name__ == "__main__":
  sys.exit(main())
