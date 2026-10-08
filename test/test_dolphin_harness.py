import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.dolphin import smoke_test

pytestmark = pytest.mark.dolphin

@pytest.mark.skipif(shutil.which("flatpak") is None, reason="flatpak Dolphin is not installed")
@pytest.mark.skipif(not os.environ.get("WW_ISO_PATH"), reason="WW_ISO_PATH is not set")
def test_dolphin_smoke(tmp_path: Path):
  screenshot = smoke_test.run(Path(os.environ["WW_ISO_PATH"]), tmp_path / "dolphin-user")
  assert screenshot.read_bytes().startswith(b"\x89PNG")
