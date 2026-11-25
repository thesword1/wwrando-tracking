#!/bin/sh
# WW Randomizer real run, piped into Termux over RUN_COMMAND by the app's foreground service.
# Usage: run.sh <bridge-port> <bridge-token> <iso-size> <iso-md5> <seed> <tracker-flag> <permalink>
# Copies the picked ISO over GET /iso (cached under ~/wwrando/input), runs android_run.py in the
# installed venv with --no-done, uploads every produced file via POST /output, and owns the final
# /done so the app never has to guess the run result from the process exit code alone.
set -u

PORT="${1:?}"
TOKEN="${2:?}"
ISO_SIZE="${3:?}"
ISO_MD5="${4:?}"
SEED="${5:-}"
TRACKER="${6:-}"
PERMALINK_IN="${7:-}"

BASE="http://127.0.0.1:${PORT}"
WW="$HOME/wwrando"
INPUT_DIR="$WW/input"
ISO_CACHE="$INPUT_DIR/clean.iso"
ISO_MD5_FILE="$INPUT_DIR/clean.iso.md5"
ISO_PART="$INPUT_DIR/clean.iso.part"
OUT_BASE="$WW/out"
OUT_DIR="$OUT_BASE/run_$$"
RUN_DIR="$WW/run"
SETTINGS_FILE="$RUN_DIR/settings.json"
LOG="$WW/run.log"
PY="$WW/venv/bin/python"
STEP=0
RESULT_JSON=""
SEED_NAME=""
PERMALINK=""
SEED_HASH=""
SUBFOLDER=""

# Each run starts with a fresh log so a failure can never report a previous run's stale tail.
: > "$LOG"

post() {
  curl -fsS --data-binary @- "$BASE/$1?t=$TOKEN" >/dev/null 2>&1 || true
}

progress() { printf '%s\n' "$1" | post progress; }

step() {
  STEP=$((STEP + 1))
  progress "STEP $STEP/5 $1"
}

fail() {
  step_name="$1"
  message="$2"
  tail_text=$(tail -n 20 "$LOG" 2>/dev/null || true)
  "$PY" -c 'import json,sys
d = {"ok": False, "step": sys.argv[1], "error": sys.argv[2] + ": " + sys.argv[3]}
print(json.dumps(d))' "$step_name" "$message" "$tail_text" | post "done" || true
  exit 1
}

# The randomizer step posts its own error JSON to stdout under --no-done, so prefer that error
# field over the log tail (which is now fresh anyway) and only fall back to the tail when it is absent.
fail_run() {
  run_error=$(json_field error)
  if [ -n "$run_error" ]; then
    run_message="$run_error"
  else
    run_tail=$(tail -n 20 "$LOG" 2>/dev/null || true)
    run_message="randomizer failed: $run_tail"
  fi
  "$PY" -c 'import json,sys
d = {"ok": False, "step": "run", "error": sys.argv[1]}
print(json.dumps(d))' "$run_message" | post "done" || true
  exit 1
}

finish() {
  "$PY" -c 'import json,sys
d = {"ok": True, "step": sys.argv[1], "seed": sys.argv[2], "permalink": sys.argv[3], "seed_hash": sys.argv[4], "output_folder": sys.argv[5]}
print(json.dumps(d))' "$STEP" "$SEED_NAME" "$PERMALINK" "$SEED_HASH" "$SUBFOLDER" | post "done" || true
  exit 0
}

sanitize() {
  printf '%s' "$1" | sed -e 's/[^A-Za-z0-9._ -]/_/g'
}

urlencode() {
  printf '%s' "$1" | sed \
    -e 's/%/%25/g' \
    -e 's/ /%20/g' \
    -e 's/!/%21/g' \
    -e 's/#/%23/g' \
    -e 's/\$/%24/g' \
    -e 's/&/%26/g' \
    -e "s/'/%27/g" \
    -e 's/(/%28/g' \
    -e 's/)/%29/g' \
    -e 's/\*/%2A/g' \
    -e 's/+/%2B/g' \
    -e 's/,/%2C/g' \
    -e 's/\//%2F/g' \
    -e 's/:/%3A/g' \
    -e 's/;/%3B/g' \
    -e 's/=/%3D/g' \
    -e 's/?/%3F/g' \
    -e 's/@/%40/g' \
    -e 's/\[/%5B/g' \
    -e 's/\]/%5D/g'
}

is_cached() {
  [ -f "$ISO_CACHE" ] && [ -f "$ISO_MD5_FILE" ] && \
    [ "$(cat "$ISO_MD5_FILE" 2>/dev/null)" = "$ISO_MD5" ] && \
    [ "$(stat -c %s "$ISO_CACHE" 2>/dev/null)" = "$ISO_SIZE" ]
}

json_field() {
  printf '%s' "$RESULT_JSON" | "$PY" -c 'import json,sys
raw = sys.stdin.read().strip()
if not raw:
    print("")
else:
    lines = raw.splitlines()
    try:
        d = json.loads(lines[-1])
    except Exception:
        d = {}
    print(d.get(sys.argv[1], "") or "")' "$1" 2>/dev/null || true
}

trap 'rm -f "$ISO_PART"; rm -rf "$OUT_DIR"' EXIT TERM INT HUP

if [ ! -x "$PY" ]; then
  fail "venv" "python venv missing, run setup first"
fi

mkdir -p "$INPUT_DIR" "$OUT_BASE" "$OUT_DIR" "$RUN_DIR" 2>>"$LOG" || fail "space" "mkdir failed"

# 1. Free space: the ISO (when not already cached) plus 1.6 GB for the randomized output and venv.
cached=0
if is_cached; then
  cached=1
fi
need_kb=1677721
if [ "$cached" -eq 0 ]; then
  need_kb=$((need_kb + ISO_SIZE / 1024))
fi
avail_kb=$(df -k ~ | awk 'NR == 2 {print $4}')
if [ "$avail_kb" -lt "$need_kb" ]; then
  need_mb=$((need_kb / 1024))
  have_mb=$((avail_kb / 1024))
  fail "space" "need ${need_mb} MB, have ${have_mb} MB"
fi

step "Copying ISO"
if [ "$cached" -eq 1 ]; then
  progress "SKIP iso-cached"
else
  curl -fsS "$BASE/iso?t=$TOKEN" -o "$ISO_PART" >>"$LOG" 2>&1 || fail "iso" "ISO download failed"
  [ "$(stat -c %s "$ISO_PART" 2>/dev/null)" = "$ISO_SIZE" ] || fail "iso" "ISO size mismatch"
  actual_md5=$(md5sum "$ISO_PART" | awk '{print $1}')
  [ "$actual_md5" = "$ISO_MD5" ] || fail "iso" "ISO md5 mismatch"
  mv "$ISO_PART" "$ISO_CACHE" || fail "iso" "ISO move failed"
  printf '%s' "$ISO_MD5" > "$ISO_MD5_FILE" || fail "iso" "md5 write failed"
fi

# 1b. Fetch the app's current settings diff (GET /settings) so the device run matches the settings screen.
step "Settings"
curl -fsS "$BASE/settings?t=$TOKEN" -o "$SETTINGS_FILE" >>"$LOG" 2>&1 || fail "settings" "settings fetch failed"

# 2. Randomize without /done: android_run.py --no-done prints the result JSON to stdout instead.
step "Randomizing"
if [ -n "$PERMALINK_IN" ]; then
  case "$PERMALINK_IN" in
    *[!A-Za-z0-9+/=]*) fail "permalink" "bad permalink characters" ;;
  esac
  permalink_len=${#PERMALINK_IN}
  if [ "$permalink_len" -lt 4 ] || [ "$permalink_len" -gt 2000 ]; then
    fail "permalink" "bad permalink length"
  fi
fi
set -- "$PY" "$WW/current/android_run.py" --clean-iso "$ISO_CACHE" --output-folder "$OUT_DIR" \
  --port "$PORT" --token "$TOKEN" --no-done --settings-json "$SETTINGS_FILE"
if [ -n "$PERMALINK_IN" ]; then
  set -- "$@" --permalink "$PERMALINK_IN"
elif [ -n "$SEED" ]; then
  set -- "$@" --seed "$SEED"
else
  set -- "$@" --autoseed
fi
if [ "$TRACKER" = "1" ]; then
  set -- "$@" --tracker
fi
RESULT_JSON=$("$@" 2>>"$LOG") || fail_run

SEED_NAME=$(json_field seed)
PERMALINK=$(json_field permalink)
SEED_HASH=$(json_field seed_hash)
BASE_NAME="$SEED_HASH"
if [ -z "$BASE_NAME" ]; then BASE_NAME="$SEED_NAME"; fi
if [ -z "$BASE_NAME" ]; then BASE_NAME="run"; fi
SUBFOLDER="$(sanitize "$BASE_NAME")_$(date +%Y%m%d-%H%M%S)"

# 3. Upload every regular file the randomizer wrote (ISO plus spoiler/non-spoiler logs).
step "Uploading"
for file in "$OUT_DIR"/*; do
  [ -f "$file" ] || continue
  name=$(sanitize "$(basename "$file")")
  progress "STEP 4/5 Upload $name"
  encoded_name=$(urlencode "$name")
  encoded_dir=$(urlencode "$SUBFOLDER")
  curl -fsS --data-binary @"$file" "$BASE/output?t=$TOKEN&name=$encoded_name&dir=$encoded_dir" \
    >>"$LOG" 2>&1 || fail "upload" "upload failed for $name"
done

step "Finishing"
rm -rf "$OUT_DIR"
finish
