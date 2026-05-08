"""Regression: re-running the pipeline must produce byte-identical atlas.csv."""
import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
BASELINE = REPO / "tests/fixtures/atlas_baseline_micro.csv"


def _make_paths_toml(tmp_path: Path) -> Path:
    """Create a paths.toml pointing at the 50-trial fixture set."""
    cfg = tmp_path / "paths.toml"
    cfg.write_text(
        f'aact_snapshot_dir = "{(REPO / "tests/fixtures/aact_50trial").as_posix()}"\n'
        f'ictrp_snapshot = "{(REPO / "tests/fixtures/ictrp_30trial.csv").as_posix()}"\n'
        f'pairwise70_index = "{(REPO / "tests/fixtures/pairwise70_micro.parquet").as_posix()}"\n'
        f'cdsr_string_index = "{(REPO / "tests/fixtures/cdsr_string_micro.sqlite").as_posix()}"\n'
        f'europe_pmc_cache_dir = "{(tmp_path / "cache").as_posix()}"\n'
    )
    return cfg


def test_atlas_baseline_present():
    """Sanity: the baseline CSV exists and is non-empty."""
    assert BASELINE.exists(), f"baseline missing: {BASELINE}"
    assert BASELINE.stat().st_size > 0


def test_atlas_csv_byte_identical_to_baseline(tmp_path):
    """Re-running the pipeline against the same fixtures + same n_bootstrap
    must produce byte-identical atlas.csv (modulo line endings).
    """
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    subprocess.check_call(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg), "--out-dir", str(out_dir),
         "--micro", "--no-network", "--n-bootstrap", "100"],
        cwd=REPO,
    )
    actual_bytes = (out_dir / "atlas.csv").read_bytes()
    expected_bytes = BASELINE.read_bytes()

    # Normalize line endings (CRLF on Windows, LF on Unix; baseline may have either)
    actual_normalized = actual_bytes.replace(b"\r\n", b"\n")
    expected_normalized = expected_bytes.replace(b"\r\n", b"\n")

    actual_sha = hashlib.sha256(actual_normalized).hexdigest()
    expected_sha = hashlib.sha256(expected_normalized).hexdigest()
    assert actual_sha == expected_sha, (
        f"atlas.csv drift!\n"
        f"  expected sha256={expected_sha[:16]}...\n"
        f"  actual sha256  ={actual_sha[:16]}...\n"
        f"Baseline at: {BASELINE}\n"
        f"Actual at:   {out_dir / 'atlas.csv'}\n"
        "If pipeline changes are intentional, regenerate the baseline:\n"
        "  python -m pilots.run_all --paths-toml <fixture-cfg> --out-dir /tmp/x --micro --no-network --n-bootstrap 100\n"
        "  cp /tmp/x/atlas.csv tests/fixtures/atlas_baseline_micro.csv"
    )
