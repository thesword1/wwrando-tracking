#!/bin/sh
# WW Randomizer first-run setup, piped into Termux over RUN_COMMAND.
# Usage: setup.sh <bridge-port> <bridge-token> <archive-sha256>
# The app's loopback bridge streams the bundled source archive over GET /tree and receives
# STEP/PROGRESS lines and the final /done status over localhost (no shared storage needed).
set -u

PORT="${1:?}"
TOKEN="${2:?}"
HASH="${3:?}"
BASE="http://127.0.0.1:${PORT}"
WW="$HOME/wwrando"
RELEASES="$WW/releases"
DEST="$RELEASES/$HASH"
VENV="$WW/venv"
WORK="$WW/work"
LOG="$WW/setup.log"
TOTAL=5
STEP=0

post() {
  # $1 = endpoint; body comes from stdin. Best-effort: never fail the setup because of reporting.
  curl -fsS --data-binary @- "$BASE/$1?t=$TOKEN" >/dev/null 2>&1 || true
}

progress() { printf '%s\n' "$1" | post progress; }

step() {
  STEP=$((STEP + 1))
  progress "STEP $STEP/$TOTAL $1"
}

escape_json() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n' ' '
}

fail() {
  tail_text=$(tail -n 20 "$LOG" 2>/dev/null | escape_json)
  { printf '{"ok":false,"step":%s,"error":"%s"}' "$STEP" "$1: $tail_text" | post done; } || true
  exit 1
}

finish() {
  { printf '{"ok":true,"step":%s,"hash":"%s"}' "$STEP" "$HASH" | post done; } || true
  exit 0
}

mkdir -p "$WW" "$RELEASES" "$WORK" 2>"$LOG" || fail "mkdir failed"

# Idempotency: when this exact bundle is already installed and its venv imports work, skip everything.
if [ -f "$WW/installed.sha256" ] && [ "$(cat "$WW/installed.sha256" 2>/dev/null)" = "$HASH" ] && \
   [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import ruamel.yaml, appdirs, certifi, tqdm, PIL, numpy' >>"$LOG" 2>&1; then
  progress "SKIP up-to-date"
  finish
fi

# 1. Termux packages, skipping the ones that are already present.
step "Installing packages"
PACKAGES=""
command -v curl >/dev/null 2>&1 || PACKAGES="$PACKAGES curl"
if command -v python >/dev/null 2>&1 && python -c 'import sys' >>"$LOG" 2>&1; then :; else
  PACKAGES="$PACKAGES python"
fi
if command -v python >/dev/null 2>&1 && python -c 'import numpy' >>"$LOG" 2>&1; then :; else
  PACKAGES="$PACKAGES python-numpy"
fi
if command -v python >/dev/null 2>&1 && python -c 'import PIL' >>"$LOG" 2>&1; then :; else
  PACKAGES="$PACKAGES python-pillow"
fi
if [ -n "$PACKAGES" ]; then
  pkg install -y $PACKAGES >>"$LOG" 2>&1 || fail "pkg install failed"
fi

# 2. Fetch the same-commit source archive straight from the app's loopback bridge.
step "Downloading randomizer"
curl -fsS "$BASE/tree?t=$TOKEN" -o "$DEST.tar.gz" >>"$LOG" 2>&1 || fail "download failed"

# 3. Extract into a hash-named release directory so old releases stay until cleanup.
step "Extracting randomizer"
rm -rf "$DEST"
mkdir -p "$DEST"
tar -xzf "$DEST.tar.gz" -C "$DEST" >>"$LOG" 2>&1 || fail "extract failed"

# 4. Venv with system site-packages (Termux numpy/pillow) plus the pure-Python pins.
step "Creating Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python -m venv --system-site-packages "$VENV" >>"$LOG" 2>&1 || fail "venv failed"
fi
"$VENV/bin/pip" install --quiet "ruamel.yaml~=0.19.1" "appdirs==1.4.4" "certifi==2026.2.25" "tqdm>=4.67.1" >>"$LOG" 2>&1 || fail "pip install failed"

# 5. Atomically point "current" at the new release and record the installed hash.
step "Finishing install"
ln -s "$DEST" "$WW/current.new"
mv -f "$WW/current.new" "$WW/current"
printf '%s' "$HASH" > "$WW/installed.sha256"

finish
