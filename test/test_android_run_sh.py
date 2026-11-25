"""Shell-level tests for the bundled real-run script (android/app/src/main/assets/run.sh).

run.sh normally runs inside Termux, but its failure-reporting path can be exercised on the host
with a fake HOME plus fake curl/df/stat/md5sum in PATH. The point is to prove that a failing
randomizer's own error JSON reaches the /done body, and that a stale run.log can never leak into it.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_SH = REPO_ROOT / "android" / "app" / "src" / "main" / "assets" / "run.sh"

ISO_SIZE = 1024
ISO_MD5 = "0123456789abcdef0123456789abcdef"


def _write_fake_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    ww = home / "wwrando"
    (ww / "input").mkdir(parents=True)
    (ww / "out").mkdir()
    (ww / "venv" / "bin").mkdir(parents=True)
    (ww / "current").mkdir(parents=True)

    real_python = sys.executable
    python_shim = ww / "venv" / "bin" / "python"
    python_shim.write_text(f'#!/bin/sh\nexec "{real_python}" "$@"\n', encoding="utf-8")
    python_shim.chmod(0o755)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    curl = bin_dir / "curl"
    curl.write_text(
        f"""#!/bin/sh
out=""
url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) shift; out="$1" ;;
    --data-binary) shift ;;
    http*) url="$1" ;;
  esac
  shift
done
case "$url" in
  */settings*)
    if [ "${{FAIL_SETTINGS:-0}}" = "1" ]; then
      exit 22
    fi
    printf '%s' "${{SETTINGS_JSON:-{{"progression_tingle_chests":true}}}}" > "$out" 2>/dev/null
    ;;
  */iso*)
    head -c {ISO_SIZE} /dev/zero > "$out" 2>/dev/null
    ;;
  */done*)
    cat > "${{CAPTURE_DONE:-/dev/null}}"
    ;;
  *)
    cat > /dev/null
    ;;
esac
exit 0
""",
        encoding="utf-8",
    )
    curl.chmod(0o755)

    stat_shim = bin_dir / "stat"
    stat_shim.write_text(f"#!/bin/sh\nprintf '%d\\n' {ISO_SIZE}\n", encoding="utf-8")
    stat_shim.chmod(0o755)

    md5sum = bin_dir / "md5sum"
    md5sum.write_text(f"#!/bin/sh\nprintf '%s  -\\n' {ISO_MD5}\n", encoding="utf-8")
    md5sum.chmod(0o755)

    df = bin_dir / "df"
    df.write_text(
        "#!/bin/sh\n"
        "echo 'Filesystem 1K-blocks Used Available Use% Mounted on'\n"
        "echo '/dev/fake 100000000 0 99999999 0% /home'\n",
        encoding="utf-8",
    )
    df.chmod(0o755)

    return home, bin_dir


def _run_run_sh(home: Path, bin_dir: Path, capture: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    env["CAPTURE_DONE"] = str(capture)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["sh", str(RUN_SH), "12345", "t" * 32, str(ISO_SIZE), ISO_MD5, "", "1"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_failure_reports_randomizer_error_json_not_stale_log(tmp_path):
    home, bin_dir = _write_fake_home(tmp_path)
    (home / "wwrando" / "run.log").write_text("OLD_ERROR_MARKER\nprevious traceback\n", encoding="utf-8")
    (home / "wwrando" / "current" / "android_run.py").write_text(
        'import json, sys\nprint(json.dumps({"ok": False, "error": "REAL_ERROR_MARKER"}))\nsys.exit(1)\n',
        encoding="utf-8",
    )
    capture = tmp_path / "done.json"

    proc = _run_run_sh(home, bin_dir, capture)

    assert proc.returncode == 1, proc.stderr
    body = capture.read_text(encoding="utf-8")
    assert "REAL_ERROR_MARKER" in body, body
    assert "OLD_ERROR_MARKER" not in body, body


def test_failure_without_error_json_does_not_report_stale_log(tmp_path):
    home, bin_dir = _write_fake_home(tmp_path)
    (home / "wwrando" / "run.log").write_text("OLD_ERROR_MARKER\n", encoding="utf-8")
    (home / "wwrando" / "current" / "android_run.py").write_text(
        "import sys\nsys.exit(1)\n", encoding="utf-8"
    )
    capture = tmp_path / "done.json"

    proc = _run_run_sh(home, bin_dir, capture)

    assert proc.returncode == 1, proc.stderr
    body = capture.read_text(encoding="utf-8")
    assert "OLD_ERROR_MARKER" not in body, body
    assert '"step": "run"' in body, body


def _write_capturing_fake_run(home: Path) -> None:
    (home / "wwrando" / "current" / "android_run.py").write_text(
        'import json, os, sys\n'
        'with open(os.environ["CAPTURE_ARGS"], "w") as f:\n'
        '    f.write(" ".join(sys.argv[1:]) + "\\n")\n'
        'print(json.dumps({"ok": True, "seed": "t", "permalink": "", "seed_hash": "h"}))\n',
        encoding="utf-8",
    )


def test_settings_route_fetched_and_settings_json_passed(tmp_path):
    home, bin_dir = _write_fake_home(tmp_path)
    _write_capturing_fake_run(home)
    capture = tmp_path / "done.json"
    args_file = tmp_path / "args.txt"

    proc = _run_run_sh(home, bin_dir, capture, extra_env={"CAPTURE_ARGS": str(args_file)})

    assert proc.returncode == 0, proc.stderr
    settings_file = home / "wwrando" / "run" / "settings.json"
    assert settings_file.exists(), "run.sh did not fetch /settings"
    assert "progression_tingle_chests" in settings_file.read_text(encoding="utf-8")
    args = args_file.read_text(encoding="utf-8")
    assert "--settings-json" in args, args
    assert str(settings_file) in args, args


def test_settings_fetch_failure_fails_with_step_settings(tmp_path):
    home, bin_dir = _write_fake_home(tmp_path)
    _write_capturing_fake_run(home)
    capture = tmp_path / "done.json"

    proc = _run_run_sh(home, bin_dir, capture, extra_env={"FAIL_SETTINGS": "1"})

    assert proc.returncode == 1, proc.stderr
    body = capture.read_text(encoding="utf-8")
    assert '"step": "settings"' in body, body
    assert "settings fetch failed" in body, body
