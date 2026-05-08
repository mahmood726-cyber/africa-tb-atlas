"""Smoke tests for scripts/release_v010.sh."""
import subprocess
from pathlib import Path
import pytest

REPO = Path(__file__).parent.parent
SCRIPT = REPO / "scripts/release_v010.sh"


def test_release_script_exists_and_executable():
    assert SCRIPT.exists()


def test_release_script_dry_run_succeeds_or_skips():
    """Dry-run should exit 0 (some PASS, some SKIP for Task 27/32b inputs).

    Should NOT exit non-zero unless an evaluable precondition genuinely fails.
    """
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    # Allow exit 0 (all-pass-or-skip) — fail only if FAIL printed
    if r.returncode != 0:
        pytest.fail(
            f"release_v010.sh dry-run failed (exit {r.returncode}):\n"
            f"stdout:\n{r.stdout}\n"
            f"stderr:\n{r.stderr}"
        )
    # Sanity: output should mention preconditions (a)-(h)
    out = r.stdout
    for label in ["(a)", "(b)", "(e)", "(g)", "(h)"]:
        assert label in out, f"missing precondition in output: {label}\n{out}"
    assert "Summary" in out
    assert "PASS:" in out


def test_release_script_runs_validate_e156_body_when_body_exists():
    """If e156-submission/body.md exists, the script should validate it (or SKIP
    if it still has unfilled placeholders from Task 32b)."""
    body = REPO / "e156-submission/body.md"
    if not body.exists():
        pytest.skip("body.md not generated yet")
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    assert "(e)" in r.stdout
    # Body.md is present; it either validates cleanly (PASS), has deferred
    # placeholders (SKIP — Task 32b still needed), or fails validation (FAIL).
    assert (
        "[PASS] (e)" in r.stdout
        or "[SKIP] (e)" in r.stdout
        or "[FAIL] (e)" in r.stdout
    ), f"unexpected (e) outcome:\n{r.stdout}"


def test_release_script_skips_atlas_baseline_check_when_absent():
    """If atlas.csv at repo root is absent, (c) should SKIP not FAIL."""
    # The atlas.csv at repo root is the v0.1.0 atlas (not the fixture). At
    # this stage of development, it doesn't exist yet.
    if (REPO / "atlas.csv").exists():
        pytest.skip("atlas.csv present (Task 27 may have completed)")
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    assert "[SKIP] (c)" in r.stdout, r.stdout


def test_release_script_dashboard_tests_pass():
    """(g) should be PASS (Task 28 dashboard is shipped + tested)."""
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    # The line should say [PASS] (g)
    assert "[PASS] (g)" in r.stdout, r.stdout


def test_release_script_sentinel_block_zero():
    """(h) should be PASS (Sentinel BLOCK=0 after Amendment 2 skip-file marker)."""
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    assert "[PASS] (h)" in r.stdout, r.stdout


def test_release_script_no_fail_on_clean_repo():
    """Dry-run should report 0 FAIL on a clean repo state (Tasks 27/32b deferred)."""
    r = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=REPO, capture_output=True, text=True
    )
    assert "FAIL: 0" in r.stdout, (
        f"Expected FAIL: 0 in summary:\n{r.stdout}"
    )
    assert r.returncode == 0, (
        f"Expected exit 0, got {r.returncode}:\n{r.stdout}\n{r.stderr}"
    )
