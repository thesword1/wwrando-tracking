#!/usr/bin/env python3
"""Generate Kotlin parity fixtures for the Android Customize preview.

Runs the repo's own gclib texture code (pure-Python path) and writes
``android/app/src/test/resources/color_fixtures.json``. The Kotlin unit test
``ColorLogicTest`` reads this committed file and asserts its ports of
``hsv_shift_color`` and the ``color_exchange`` per-pixel transform match these
values exactly, so the Android preview cannot drift from the desktop recoloring.

This is a one-shot generator: the JSON is committed and only regenerated when the
Python color code changes.
"""

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import android_run  # noqa: E402  (installs the imagequant stub)
from PIL import Image  # noqa: E402
from gclib import texture_utils as tu  # noqa: E402

android_run.install_imagequant_stub()
# Force the pure-Python path so the fixtures describe exactly the code the Kotlin
# port mirrors (the C speedup has identical semantics but we pin the Python path).
tu.PY_FAST_TEXTURE_UTILS_INSTALLED = False

OUTPUT = os.path.join(
    REPO_ROOT,
    "android",
    "app",
    "src",
    "test",
    "resources",
    "color_fixtures.json",
)


def hsv_shift_cases():
    cases = []
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
        (0, 0, 0),
        (128, 128, 128),
        (255, 239, 16),
        (247, 219, 156),
        (90, 178, 74),
        (247, 73, 99),
        (120, 60, 30),
        (16, 20, 24),
        (255, 0, 255, 255),  # RGBA form, alpha preserved
    ]
    for color in colors:
        for h_shift in (-359, -180, -1, 0, 1, 90, 180, 359):
            for v_shift in (-40, -10, 0, 10, 40):
                cases.append(
                    {
                        "color": list(color),
                        "h": h_shift,
                        "v": v_shift,
                        "expect": list(tu.hsv_shift_color(color, h_shift, v_shift)),
                    }
                )
    return cases


def exchange_case(base, replacement, pixel):
    image = Image.new("RGBA", (1, 1))
    image.putpixel((0, 0), pixel)
    out = tu.color_exchange(
        image, base, replacement, mask_path=None, validate_mask_colors=False
    )
    return list(out.getpixel((0, 0)))


def exchange_cases():
    cases = []
    bases = [
        (255, 239, 16),
        (255, 255, 255),
        (0, 0, 0),
        (90, 178, 74),
    ]
    replacements = [
        (0, 0, 255),
        (255, 0, 0),
        (16, 20, 24),
        (247, 219, 156),
    ]
    pixels = [
        (255, 0, 0, 255),
        (120, 60, 30, 255),
        (0, 0, 0, 255),
        (255, 255, 255, 255),
        (200, 200, 200, 128),
        (128, 128, 128, 255),
        (10, 20, 30, 255),
        (250, 240, 230, 255),
    ]
    for base in bases:
        for replacement in replacements:
            for pixel in pixels:
                cases.append(
                    {
                        "base": list(base),
                        "replacement": list(replacement),
                        "pixel": list(pixel),
                        "expect": exchange_case(base, replacement, pixel),
                    }
                )
    return cases


def main():
    fixtures = {
        "hsv_shift": hsv_shift_cases(),
        "color_exchange": exchange_cases(),
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(fixtures, f, indent=1)
        f.write("\n")
    print(f"wrote {OUTPUT} ({len(fixtures['hsv_shift'])} hsv, {len(fixtures['color_exchange'])} exchange)")


if __name__ == "__main__":
    main()
