#!/usr/bin/env bash
# Runs asm/assemble.py inside a pinned devkitPPC container (podman or docker).
# Regenerates asm/patch_diffs/*.txt and asm/custom_symbols.txt in the repo this script lives in.
# Extra arguments are passed through to assemble.py.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
image="${WWRANDO_DEVKITPPC_IMAGE:-localhost/wwrando-devkitppc:latest}"

if command -v podman >/dev/null 2>&1; then
  engine=podman
  # Keep the host user's uid so regenerated files aren't owned by root.
  run_args=(--userns=keep-id)
elif command -v docker >/dev/null 2>&1; then
  engine=docker
  run_args=(--user "$(id -u):$(id -g)")
else
  echo "Neither podman nor docker is installed." >&2
  exit 1
fi

if [ ! -f "$repo_root/gclib/gclib/fs_helpers.py" ]; then
  echo "The gclib submodule is missing. Run: git submodule update --init" >&2
  exit 1
fi

# Rebuilding is a no-op (layer cache) when the Containerfile hasn't changed.
"$engine" build --quiet -t "$image" -f "$script_dir/Containerfile" "$script_dir" >/dev/null

exec "$engine" run --rm "${run_args[@]}" \
  --security-opt label=disable \
  -v "$repo_root:/src" -w /src \
  -e PYTHONDONTWRITEBYTECODE=1 \
  "$image" python3 asm/assemble.py "$@"
