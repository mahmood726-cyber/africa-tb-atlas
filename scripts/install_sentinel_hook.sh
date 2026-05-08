#!/usr/bin/env bash
# scripts/install_sentinel_hook.sh
# Per AGENTS.md / portfolio rule: install the Sentinel pre-push rule
# engine for this repo. Project-local rule: any commit touching src/,
# pilots/, or tests/ before .preregistration_commit.txt exists -> BLOCK.
#
# Prerequisite: .preregistration_commit.txt must exist (created at
# preregistration time; anchors spec sha256 + GitHub tag + IA snapshots).
#
# Usage:
#   bash scripts/install_sentinel_hook.sh           # warn mode (default — dev phase)
#   SENTINEL_MODE=block bash scripts/install_sentinel_hook.sh
#
# Note: default is WARN (not block) during the development phase (Tasks 1-33).
# Mode switches to BLOCK at Task 34 release. To switch early:
#   SENTINEL_MODE=block bash scripts/install_sentinel_hook.sh
#
# Preregistration mechanism: GitHub annotated tag + Internet Archive snapshot
# (Bitcoin OTS path was swapped on 2026-05-08; see docs/AMENDMENTS.md §OTS-swap
# and docs/spec.md §4.3)
#
# Manual install fallback (if python -m sentinel is unavailable):
#   python -c "
#   import sys, pathlib
#   sys.path.insert(0, r'C:\\Sentinel')
#   from sentinel import install_hook
#   install_hook.run(repo='.')
#   "
#   Or copy C:\Sentinel\sentinel\hooks\pre-push.tmpl -> .git/hooks/pre-push
#   and make it executable.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"

if [[ ! -f "$REPO/.preregistration_commit.txt" ]]; then
    echo "REFUSING: .preregistration_commit.txt missing — Sentinel install requires the prereg manifest first." >&2
    exit 1
fi

# Default to warn mode during development phase (Tasks 1-33).
# Switch to block at Task 34 release via SENTINEL_MODE=block.
MODE="${SENTINEL_MODE:-warn}"

python -m sentinel install-hook --repo "$REPO" --mode "$MODE"
echo "Sentinel hook installed in $MODE mode; project-local rule armed."
echo "Override per-push: SENTINEL_MODE=block git push"
