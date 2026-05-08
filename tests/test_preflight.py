"""Tests for pilots/preflight.py."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _make_micro_paths_toml(tmp_path: Path) -> Path:
    """Build a paths.toml pointing at the micro fixtures."""
    cfg = tmp_path / "paths_micro.toml"
    cfg.write_text(
        f'aact_snapshot_dir = "{(REPO / "tests/fixtures/aact_50trial").as_posix()}"\n'
        f'ictrp_snapshot = "{(REPO / "tests/fixtures/ictrp_30trial.csv").as_posix()}"\n'
        f'pairwise70_index = "{(REPO / "tests/fixtures/pairwise70_micro.parquet").as_posix()}"\n'
        f'cdsr_string_index = "{(REPO / "tests/fixtures/cdsr_string_micro.sqlite").as_posix()}"\n'
        f'europe_pmc_cache_dir = "{(tmp_path / "cache").as_posix()}"\n'
    )
    return cfg


def test_preflight_passes_with_micro_fixtures(tmp_path):
    cfg = _make_micro_paths_toml(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "pilots.preflight", "--paths-toml", str(cfg), "--micro"],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"
    assert "OK" in r.stdout


def test_preflight_fails_without_micro_flag_on_small_fixtures(tmp_path):
    """Without --micro, the production thresholds (P70 >=1000, CDSR >=100) trigger fail."""
    cfg = _make_micro_paths_toml(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "pilots.preflight", "--paths-toml", str(cfg)],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 1


def test_preflight_fails_on_missing_paths_toml(tmp_path):
    r = subprocess.run(
        [sys.executable, "-m", "pilots.preflight",
         "--paths-toml", str(tmp_path / "does_not_exist.toml"), "--micro"],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 1
    assert "paths.toml" in (r.stdout + r.stderr).lower()


def test_preflight_fails_on_missing_aact_dir(tmp_path):
    """paths.toml points at a non-existent AACT dir."""
    cfg = tmp_path / "paths.toml"
    fake_aact = tmp_path / "nonexistent_aact"
    cfg.write_text(
        f'aact_snapshot_dir = "{fake_aact.as_posix()}"\n'
        f'ictrp_snapshot = "{(REPO / "tests/fixtures/ictrp_30trial.csv").as_posix()}"\n'
        f'pairwise70_index = "{(REPO / "tests/fixtures/pairwise70_micro.parquet").as_posix()}"\n'
        f'cdsr_string_index = "{(REPO / "tests/fixtures/cdsr_string_micro.sqlite").as_posix()}"\n'
        f'europe_pmc_cache_dir = "{(tmp_path / "cache").as_posix()}"\n'
    )
    r = subprocess.run(
        [sys.executable, "-m", "pilots.preflight", "--paths-toml", str(cfg), "--micro"],
        cwd=REPO, capture_output=True, text=True
    )
    # config.load_paths raises ConfigError for missing aact_snapshot_dir,
    # so preflight exits 1 at the load_paths stage.
    assert r.returncode == 1


def test_preflight_creates_cache_dir(tmp_path):
    """europe_pmc_cache_dir is created on demand by preflight (not a fail condition)."""
    cfg = _make_micro_paths_toml(tmp_path)
    cache_dir = tmp_path / "cache"
    # Initially absent
    if cache_dir.exists():
        cache_dir.rmdir()
    r = subprocess.run(
        [sys.executable, "-m", "pilots.preflight", "--paths-toml", str(cfg), "--micro"],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 0
    assert cache_dir.exists()
