"""Asserts that Android-side constants stay in sync with the randomizer core.

The Android app pre-verifies the picked clean ISO with its own MD5 constant so the
"Randomize" button can be disabled for a wrong ISO before Termux ever runs. If that
constant drifts from randomizer.py the two would disagree about which ISO is valid.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

KOTLIN_ISO_VERIFY = (
    REPO_ROOT
    / "android/app/src/main/java/io/github/thesword1/wwrando/data/IsoVerify.kt"
)
RANDOMIZER = REPO_ROOT / "randomizer.py"


def test_clean_iso_md5_matches_randomizer():
    kotlin_text = KOTLIN_ISO_VERIFY.read_text(encoding="utf-8")
    match = re.search(r'CLEAN_ISO_MD5\s*=\s*"([0-9a-fA-F]{32})"', kotlin_text)
    assert match, "CLEAN_ISO_MD5 string constant not found in IsoVerify.kt"
    kotlin_md5 = match.group(1).lower()

    randomizer_text = RANDOMIZER.read_text(encoding="utf-8")
    match = re.search(r"CLEAN_WIND_WAKER_ISO_MD5\s*=\s*0x([0-9a-fA-F]{32})", randomizer_text)
    assert match, "CLEAN_WIND_WAKER_ISO_MD5 not found in randomizer.py"
    randomizer_md5 = match.group(1).lower()

    assert kotlin_md5 == randomizer_md5, (
        f"Android CLEAN_ISO_MD5 ({kotlin_md5}) != randomizer.py "
        f"CLEAN_WIND_WAKER_ISO_MD5 ({randomizer_md5})"
    )
