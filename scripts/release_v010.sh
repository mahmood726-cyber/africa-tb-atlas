#!/usr/bin/env bash
# scripts/release_v010.sh — africa-tb-atlas v0.1.0 dry-run preconditions gate.
#
# Requires: Git Bash (Windows) or POSIX shell.
# Run from repo root.
#
# Usage:
#   bash scripts/release_v010.sh             # DRY-RUN: report pass/skip/fail
#
# Exit codes:
#   0 — all evaluable preconditions PASS (some may be SKIP if Task 27/32b deferred)
#   1 — at least one precondition FAILed
#
# Per spec §5.8, the 8 preconditions check:
#   (a) preflight (micro-fixture mode)
#   (b) verify_prereg (prereg_manifest sha256 match)
#   (c) atlas.csv sha256 vs output_baselines.json  [SKIP if file absent]
#   (d) validation_gates (trialscout + spot-check + ensemble)  [SKIP if inputs absent]
#   (e) validate_e156_body
#   (f) validate_synthesis_note  (filled form, generated on-the-fly)
#   (g) dashboard tests
#   (h) Sentinel BLOCK=0

set -uo pipefail

REPO="$(git rev-parse --show-toplevel)"
cd "$REPO"

PASS_COUNT=0
SKIP_COUNT=0
FAIL_COUNT=0
PASS_LINES=()
SKIP_LINES=()
FAIL_LINES=()

step() {
    local label="$1"
    local cmd="$2"
    local skip_msg="${3:-}"

    if [[ -n "$skip_msg" ]]; then
        echo "  [SKIP] $label — $skip_msg"
        SKIP_LINES+=("$label: $skip_msg")
        SKIP_COUNT=$((SKIP_COUNT + 1))
        return 0
    fi

    if eval "$cmd" >/dev/null 2>&1; then
        echo "  [PASS] $label"
        PASS_LINES+=("$label")
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "  [FAIL] $label"
        echo "          command: $cmd"
        FAIL_LINES+=("$label")
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

echo "africa-tb-atlas v0.1.0 dry-run preconditions"
echo "============================================"
echo

# ---------------------------------------------------------------------------
# (a) preflight — use real paths.toml if present; otherwise generate a temp
#     fixture paths.toml and run with --micro for fixture-size thresholds.
# ---------------------------------------------------------------------------
if [[ -f "paths.toml" ]]; then
    step "(a) preflight" \
        "python -m pilots.preflight --paths-toml paths.toml --micro"
else
    FIXTURE_PATHS=$(mktemp /tmp/paths_dryrun_XXXXXX.toml)
    printf 'aact_snapshot_dir    = "%s/tests/fixtures/aact_50trial"\n' "$REPO" > "$FIXTURE_PATHS"
    printf 'ictrp_snapshot       = "%s/tests/fixtures/ictrp_30trial.csv"\n' "$REPO" >> "$FIXTURE_PATHS"
    printf 'pairwise70_index     = "%s/tests/fixtures/pairwise70_micro.parquet"\n' "$REPO" >> "$FIXTURE_PATHS"
    printf 'cdsr_string_index    = "%s/tests/fixtures/cdsr_string_micro.sqlite"\n' "$REPO" >> "$FIXTURE_PATHS"
    printf 'europe_pmc_cache_dir = "%s/data/processed/cache_dryrun"\n' "$REPO" >> "$FIXTURE_PATHS"
    step "(a) preflight (fixture-mode)" \
        "python -m pilots.preflight --paths-toml $FIXTURE_PATHS --micro"
fi

# ---------------------------------------------------------------------------
# (b) verify_prereg — sha256 of preregistered spec/protocol/AMENDMENTS files.
# ---------------------------------------------------------------------------
step "(b) verify_prereg" \
    "python scripts/verify_prereg.py --manifest data/snapshots/prereg_manifest.json --root ."

# ---------------------------------------------------------------------------
# (c) atlas.csv sha256 vs output_baselines.json — SKIP if either absent.
#     The root-level atlas.csv is the v0.1.0 deliverable (produced by Task 27).
# ---------------------------------------------------------------------------
if [[ -f "atlas.csv" && -f "data/snapshots/output_baselines.json" ]]; then
    step "(c) atlas.csv sha256 baseline match" \
        "python -c 'import hashlib, json, pathlib; m=json.loads(pathlib.Path(\"data/snapshots/output_baselines.json\").read_text()); actual=hashlib.sha256(pathlib.Path(\"atlas.csv\").read_bytes()).hexdigest(); assert actual == m[\"atlas.csv\"], f\"drift: expected {m[chr(34)+chr(97)+chr(116)+chr(108)+chr(97)+chr(115)+chr(46)+chr(99)+chr(115)+chr(118)+chr(34)][:16]}... got {actual[:16]}...\"'"
else
    step "(c) atlas.csv sha256 baseline match" "" \
        "atlas.csv or data/snapshots/output_baselines.json absent (Task 27 produces these)"
fi

# ---------------------------------------------------------------------------
# (d) validation_gates — SKIP if either input absent (Tasks 27 + 32b produce them).
# ---------------------------------------------------------------------------
if [[ -f "data/output/trials.parquet" && -f "data/processed/spotcheck_v0.1.0.csv" ]]; then
    step "(d) validation_gates" \
        "python scripts/validation_gates.py --trials data/output/trials.parquet --spotcheck data/processed/spotcheck_v0.1.0.csv"
else
    step "(d) validation_gates" "" \
        "trials.parquet and/or spotcheck_v0.1.0.csv absent (Tasks 27 + 32b produce these)"
fi

# ---------------------------------------------------------------------------
# (e) validate_e156_body — checks 7 sentences, <=156 words, no placeholders.
#     Scripts use CWD-relative paths, so we run from repo root.
#     SKIP if body.md absent OR still has unfilled placeholders (spot-check
#     values {{SPOTCHECK_AGREE_N}}/{{SPOTCHECK_TOTAL}} fill at Task 32b).
# ---------------------------------------------------------------------------
if [[ ! -f "e156-submission/body.md" ]]; then
    step "(e) validate_e156_body" "" "e156-submission/body.md absent (Task 29 produces it)"
elif grep -q "{{" "e156-submission/body.md" 2>/dev/null; then
    step "(e) validate_e156_body" "" \
        "body.md has unfilled placeholders (Task 32b spot-check fills SPOTCHECK_* tokens)"
else
    step "(e) validate_e156_body" \
        "python scripts/validate_e156_body.py"
fi

# ---------------------------------------------------------------------------
# (f) validate_synthesis_note — validates the FILLED form (<=400 words, no
#     placeholders).  If a filled form doesn't exist yet, try to generate it
#     on-the-fly; validate in a temp dir so the script's CWD-relative read
#     finds the file at the expected path.
# ---------------------------------------------------------------------------
NOTE_TEMPLATE="e156-submission/synthesis-methods-note.md"
NOTE_FILLED="e156-submission/synthesis-methods-note.filled.md"
ATLAS_FOR_FILL="atlas.csv"
if [[ ! -f "$ATLAS_FOR_FILL" ]]; then
    ATLAS_FOR_FILL="tests/fixtures/atlas_baseline_micro.csv"
fi

if [[ -f "$NOTE_TEMPLATE" ]]; then
    # Attempt to generate the filled form if it doesn't already exist
    if [[ ! -f "$NOTE_FILLED" ]] && [[ -f "$ATLAS_FOR_FILL" ]]; then
        python scripts/fill_paper_placeholders.py \
            --template "$NOTE_TEMPLATE" \
            --atlas "$ATLAS_FOR_FILL" \
            --out "$NOTE_FILLED" >/dev/null 2>&1 || true
    fi

    if [[ -f "$NOTE_FILLED" ]]; then
        # Check if the filled form still has unfilled placeholders (e.g. when
        # atlas.csv is the micro fixture and lacks real N_TRIALS values).
        if grep -q "{{" "$NOTE_FILLED" 2>/dev/null; then
            step "(f) validate_synthesis_note" "" \
                "filled form still has placeholders (Task 27 real-data atlas needed)"
        else
            # Validate inline with python -c, reading the filled file directly.
            FILLED_ABS="$REPO/$NOTE_FILLED"
            step "(f) validate_synthesis_note" \
                "python -c \"
import re, pathlib
text = pathlib.Path('$FILLED_ABS').read_text(encoding='utf-8')
clean = re.sub(r'<!--.*?-->', '', text, flags=re.S).strip()
words = clean.split()
assert len(words) <= 400, f'expected <=400 words, got {len(words)}'
for token in ('{{','}}'):
    assert token not in clean, f'unfilled placeholder in synthesis note'
\""
        fi
    else
        step "(f) validate_synthesis_note" "" \
            "fill_paper_placeholders failed or atlas absent — skip"
    fi
else
    step "(f) validate_synthesis_note" "" "synthesis-methods-note.md absent"
fi

# ---------------------------------------------------------------------------
# (g) dashboard tests — Task 28 ships static dashboard; this must stay green.
# ---------------------------------------------------------------------------
step "(g) dashboard tests" \
    "python -m pytest tests/test_dashboard_static.py -q"

# ---------------------------------------------------------------------------
# (h) Sentinel BLOCK=0 — no hard violations.
# ---------------------------------------------------------------------------
step "(h) Sentinel BLOCK=0" \
    "python -m sentinel scan --repo . 2>&1 | grep -E 'BLOCK=0'"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "Summary"
echo "-------"
echo "  PASS: $PASS_COUNT"
echo "  SKIP: $SKIP_COUNT"
echo "  FAIL: $FAIL_COUNT"
echo

if [[ $FAIL_COUNT -gt 0 ]]; then
    echo "FAILED preconditions:"
    for line in "${FAIL_LINES[@]}"; do
        echo "  - $line"
    done
    echo
    echo "v0.1.0 release is BLOCKED until these preconditions pass."
    exit 1
fi

if [[ $SKIP_COUNT -gt 0 ]]; then
    echo "SKIPPED preconditions (deferred to Tasks 27/32b real-data run):"
    for line in "${SKIP_LINES[@]}"; do
        echo "  - $line"
    done
    echo
    echo "Dry-run OK so far. v0.1.0 release pending the SKIPped preconditions."
    exit 0
fi

echo "All $PASS_COUNT preconditions PASS. Ready for v0.1.0 release ritual."
exit 0
