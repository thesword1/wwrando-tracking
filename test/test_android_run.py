"""Tests for the bundled Android headless shim (android_run.py).

The shim runs in a subprocess so its imagequant stub insertion cannot leak into the pytest process
and swap gclib's real imagequant for other tests in this suite.
"""

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM = REPO_ROOT / "android_run.py"


class _StubHandler(http.server.BaseHTTPRequestHandler):
    progress_lines = []
    done_bodies = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        if self.path.startswith("/progress"):
            _StubHandler.progress_lines.extend(body.splitlines())
        elif self.path.startswith("/done"):
            _StubHandler.done_bodies.append(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):  # silence request logging
        pass


def _start_stub():
    _StubHandler.progress_lines = []
    _StubHandler.done_bodies = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _parse_progress(line):
    # "PROGRESS <done>/<max> <description>"
    _, fraction, _ = line.split(" ", 2)
    done, _max = fraction.split("/", 1)
    return int(done), int(_max)


def test_imagequant_stub_used_when_real_package_absent():
    code = """
import sys
class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name == "imagequant":
            raise ImportError("no imagequant here")
        return None
sys.meta_path.insert(0, Blocker())
import android_run
android_run.install_imagequant_stub()
import imagequant
from PIL import Image
assert imagequant.__name__ == "imagequant"
img = imagequant.quantize_pil_image(Image.new("RGBA", (8, 8), (255, 0, 0, 255)), max_colors=16)
assert img is not None
print("STUB_OK")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "STUB_OK" in proc.stdout


def test_imagequant_stub_quantizes_and_keeps_transparent_pixels():
    import android_run
    from PIL import Image

    image = Image.new("RGBA", (64, 64))
    px = image.load()
    transparent = set()
    for y in range(64):
        for x in range(64):
            if (x + y) % 7 == 0:
                px[x, y] = (0, 0, 0, 0)
                transparent.add((x, y))
            else:
                px[x, y] = (x * 4 % 256, y * 4 % 256, (x + y) * 3 % 256, 255)

    stub = android_run.make_imagequant_stub()
    for max_colors in (16, 256):
        out = stub.quantize_pil_image(image, max_colors=max_colors).convert("RGBA")
        colors = out.getcolors(64 * 64)
        assert colors is not None
        assert len(colors) <= max_colors
        out_px = out.load()
        assert all(out_px[x, y][3] == 0 for x, y in transparent)


def test_dry_run_reports_monotonic_progress_and_done_ok():
    server = _start_stub()
    outdir = tempfile.mkdtemp(prefix="wwrando-android-run-")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SHIM),
                "--port", str(server.server_address[1]),
                "--token", "a" * 32,
                "--dry",
                "--seed", "test",
                "--output-folder", outdir,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, proc.stderr
    finally:
        server.shutdown()

    progress = [line for line in _StubHandler.progress_lines if line.startswith("PROGRESS ")]
    assert progress, "shim emitted no PROGRESS lines"
    done_values = [_parse_progress(line)[0] for line in progress]
    max_values = [_parse_progress(line)[1] for line in progress]
    assert done_values == sorted(done_values), "PROGRESS values are not monotonic: %r" % done_values
    assert all(max_val > 0 for max_val in max_values)

    assert _StubHandler.done_bodies, "shim did not POST /done"
    done = json.loads(_StubHandler.done_bodies[-1])
    assert done.get("ok") is True
    assert done.get("seed") == "test"
    assert done.get("permalink")
    assert done.get("dry_run") is True


def test_no_done_prints_result_json_to_stdout_instead_of_posting():
    server = _start_stub()
    outdir = tempfile.mkdtemp(prefix="wwrando-android-run-")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(SHIM),
                "--port", str(server.server_address[1]),
                "--token", "a" * 32,
                "--dry",
                "--no-done",
                "--seed", "test",
                "--output-folder", outdir,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, proc.stderr
    finally:
        server.shutdown()

    # The bridge must still get PROGRESS lines, but run.sh owns /done now.
    assert [l for l in _StubHandler.progress_lines if l.startswith("PROGRESS ")], "no PROGRESS lines"
    assert not _StubHandler.done_bodies, "shim posted /done despite --no-done"

    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result.get("ok") is True
    assert result.get("seed") == "test"
    assert result.get("dry_run") is True


def _args(**overrides):
    import argparse

    values = dict(
        port=1,
        token="a" * 32,
        no_done=True,
        seed=None,
        permalink=None,
        autoseed=False,
        clean_iso=None,
        output_folder=None,
        settings_json=None,
        dry=True,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def test_settings_json_changes_an_option():
    import android_run
    from options.wwrando_options import SwordMode

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
        json.dump({"progression_tingle_chests": True, "sword_mode": "Swordless"}, f)
        f.flush()
        kwargs = android_run.build_randomizer_kwargs(_args(settings_json=f.name, seed="test"))

    assert kwargs["options"].progression_tingle_chests is True
    assert kwargs["options"].sword_mode == SwordMode.SWORDLESS


def test_settings_json_applies_customize_str_and_dict_options():
    import android_run

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
        json.dump(
            {
                "custom_player_model": "Some Model",
                "custom_color_preset": "Dark Link",
                "custom_colors": {"Hair": [255, 0, 0], "Eyes": [0, 255, 0]},
                "player_in_casual_clothes": True,
            },
            f,
        )
        f.flush()
        kwargs = android_run.build_randomizer_kwargs(_args(settings_json=f.name, seed="test"))

    assert kwargs["options"].custom_player_model == "Some Model"
    assert kwargs["options"].custom_color_preset == "Dark Link"
    assert kwargs["options"].custom_colors == {"Hair": [255, 0, 0], "Eyes": [0, 255, 0]}
    assert kwargs["options"].player_in_casual_clothes is True


def test_settings_json_rejects_bad_custom_colors_shape():
    import android_run
    from options.wwrando_options import Options

    options = Options()
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
        json.dump({"custom_colors": {"Hair": [255, 0]}}, f)
        f.flush()
        with pytest.raises(android_run.SettingsError, match="must be"):
            android_run.apply_settings_json(options, f.name)



def test_permalink_still_wins_over_settings_json():
    import android_run
    from options.wwrando_options import Options, SwordMode
    from randomizer import WWRandomizer

    base = Options()
    base.progression_tingle_chests = False
    base.sword_mode = SwordMode.START_WITH_SWORD
    permalink = WWRandomizer.encode_permalink("testseed", base)

    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
        json.dump({"progression_tingle_chests": True, "sword_mode": "Swordless"}, f)
        f.flush()
        kwargs = android_run.build_randomizer_kwargs(
            _args(permalink=permalink, settings_json=f.name),
        )

    assert kwargs["options"].progression_tingle_chests is False
    assert kwargs["options"].sword_mode == SwordMode.START_WITH_SWORD


def test_bad_enum_value_fails_with_step_settings():
    outdir = tempfile.mkdtemp(prefix="wwrando-android-run-")
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8") as f:
        json.dump({"sword_mode": "Not A Real Mode"}, f)
        f.flush()
        proc = subprocess.run(
            [
                sys.executable,
                str(SHIM),
                "--port", "1",
                "--token", "a" * 32,
                "--dry",
                "--no-done",
                "--seed", "test",
                "--output-folder", outdir,
                "--settings-json", f.name,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )

    assert proc.returncode == 1, proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result.get("ok") is False
    assert result.get("step") == "settings"
    assert "sword_mode" in result.get("error", "")

