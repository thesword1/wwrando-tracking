#!/usr/bin/env bash
# Quiet test wrapper: runs the same pytest command as CI and reports one line.
# All pytest output goes to .claude/test.log (gitignored).
set -u

cd "$(dirname "$0")/.." || exit 1

LOG=".claude/test.log"
mkdir -p .claude

pytest test -m "not saving" -q > "$LOG" 2>&1
status=$?

passed=$(grep -Eo '[0-9]+ passed' "$LOG" | grep -Eo '[0-9]+' | head -n 1)
failed=$(grep -Eo '[0-9]+ failed' "$LOG" | grep -Eo '[0-9]+' | head -n 1)
passed=${passed:-0}
failed=${failed:-0}

if [ "$status" -eq 0 ]; then
  echo "TESTS PASS (${passed})"
  exit 0
fi

echo "TESTS FAIL (${failed}/$((passed + failed)))"
grep -E '^(FAILED|ERROR) ' "$LOG" | head -n 20
echo "see .claude/test.log"
exit 1
