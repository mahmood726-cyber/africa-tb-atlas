"""End-to-end integration test on the 50+30 fixture."""
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).parent.parent


def _make_paths_toml(tmp_path: Path) -> Path:
    """Build paths.toml pointing at the integration fixtures."""
    cfg = tmp_path / "paths_micro.toml"
    cfg.write_text(
        f'aact_snapshot_dir = "{(REPO / "tests/fixtures/aact_50trial").as_posix()}"\n'
        f'ictrp_snapshot = "{(REPO / "tests/fixtures/ictrp_30trial.csv").as_posix()}"\n'
        f'pairwise70_index = "{(REPO / "tests/fixtures/pairwise70_micro.parquet").as_posix()}"\n'
        f'cdsr_string_index = "{(REPO / "tests/fixtures/cdsr_string_micro.sqlite").as_posix()}"\n'
        f'europe_pmc_cache_dir = "{(tmp_path / "cache").as_posix()}"\n'
    )
    return cfg


def test_run_all_fixture_mode_produces_atlas(tmp_path):
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    r = subprocess.run(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg),
         "--out-dir", str(out_dir),
         "--micro", "--no-network",
         "--n-bootstrap", "100"],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 0, f"stdout: {r.stdout}\nstderr: {r.stderr}"

    trials = out_dir / "trials.parquet"
    atlas = out_dir / "atlas.csv"
    audit = out_dir / "denominator_audit.csv"
    assert trials.exists(), "trials.parquet not created"
    assert atlas.exists(), "atlas.csv not created"
    assert audit.exists(), "denominator_audit.csv not created"


def test_atlas_has_expected_strata(tmp_path):
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    subprocess.check_call(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg), "--out-dir", str(out_dir),
         "--micro", "--no-network", "--n-bootstrap", "100"],
        cwd=REPO,
    )
    atlas = pd.read_csv(out_dir / "atlas.csv")
    # Must have rows for all 4 stratifications: binary, site_share_30pct, three_tier, drug_class
    assert "sensitivity" in atlas.columns
    assert set(atlas.sensitivity) >= {"binary_1site", "site_share_30pct",
                                       "three_tier", "drug_class"}


def test_atlas_has_required_metric_columns(tmp_path):
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    subprocess.check_call(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg), "--out-dir", str(out_dir),
         "--micro", "--no-network", "--n-bootstrap", "100"],
        cwd=REPO,
    )
    atlas = pd.read_csv(out_dir / "atlas.csv")
    expected = {"sensitivity", "stratum_key", "stratum_value",
                "n_trials", "n_results_posted", "n_peer_published",
                "n_in_cochrane", "n_invisible",
                "n_participants", "n_participants_in_cochrane",
                "pct_g0_to_g3", "pct_g0_to_g3_pat"}
    missing = expected - set(atlas.columns)
    assert not missing, f"atlas.csv missing columns: {missing}"


def test_atlas_pct_in_valid_range(tmp_path):
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    subprocess.check_call(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg), "--out-dir", str(out_dir),
         "--micro", "--no-network", "--n-bootstrap", "100"],
        cwd=REPO,
    )
    atlas = pd.read_csv(out_dir / "atlas.csv")
    pct = atlas["pct_g0_to_g3"].dropna()
    assert ((pct >= 0) & (pct <= 1)).all(), f"pct out of [0,1]: {pct.tolist()}"
    pct_pat = atlas["pct_g0_to_g3_pat"].dropna()
    assert ((pct_pat >= 0) & (pct_pat <= 1)).all()


def test_atlas_has_drug_class_breakdown(tmp_path):
    cfg = _make_paths_toml(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    subprocess.check_call(
        [sys.executable, "-m", "pilots.run_all",
         "--paths-toml", str(cfg), "--out-dir", str(out_dir),
         "--micro", "--no-network", "--n-bootstrap", "100"],
        cwd=REPO,
    )
    atlas = pd.read_csv(out_dir / "atlas.csv")
    drug_class_rows = atlas[atlas.sensitivity == "drug_class"]
    # At least 3 distinct drug classes should be present (BPaL, BPaLM, Bdq+companion)
    assert len(drug_class_rows) >= 3
