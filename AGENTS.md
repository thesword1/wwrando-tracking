# AGENTS.md

Standing rules for agents working in this repository. Follow these together with the user's own
instructions; nothing here overrides an explicit instruction from the user.

## Boundaries

- Never use `adb` or touch devices. No device automation of any kind.
- Never commit, push, or publish personal data or secrets. The Wind Waker test ISO path is private:
  it lives only in `PROJECT_PLAN.md` and must never be committed, uploaded, or written into any
  version-controlled file. Never bundle, fetch, or upload a game ISO or extracted game files.
- Never merge PRs. Open them and report the PR number and head SHA; a human merges.

## Git and GitHub

- Keep the existing noreply git identity (`TheSword1 <18688032+thesword1@users.noreply.github.com>`);
  do not change it.
- Repo is `thesword1/wwrando-tracking` (a fork of LagoLunatic/wwrando). Always pass
  `--repo thesword1/wwrando-tracking` to `gh`; PR base is `master`.
- End every commit message with `Co-Authored-By: Claude Code <noreply@anthropic.com>`.
- End every PR description with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Trunk-based: short-lived `feature/`, `fix/`, `docs/`, `ci/`, `chore/` or `tooling/` branches, one
  squash-merged PR per change, and a `CHANGELOG.md` entry per feature.

## Tests

- Run tests only through `scripts/test-quiet.sh`, never by calling pytest directly for the full suite.
  It runs `pytest test -m "not saving" -q` exactly as CI does and writes `.claude/test.log`.
- Markers (`pytest.ini`): `saving` tests need a vanilla ISO (never available in CI); `dolphin` tests
  launch flatpak Dolphin; `slow` runs long seed matrices.

## Android

- The Android app lives in `android/` (Gradle/Kotlin). Its Python sources are never committed twice:
  `android/app/build.gradle.kts` copies this repo's same-commit Python tree (plus the gclib submodule,
  minus Qt/GUI-only files) into generated APK assets at build time.
