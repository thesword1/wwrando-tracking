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
