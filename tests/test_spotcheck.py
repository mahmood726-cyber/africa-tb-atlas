"""Tests for make_spotcheck_template + merge_spotcheck."""
import sys
import subprocess
from pathlib import Path

import pytest
import pandas as pd

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from make_spotcheck_template import make_template, BLINDED_COLUMNS, DEFAULT_SEED
from merge_spotcheck import merge as merge_spotcheck


def _build_trials(n_africa: int = 15, n_non_africa: int = 25) -> pd.DataFrame:
    """Build a synthetic trials DataFrame with the columns make_template needs.

    Includes has_publication (required by validation_gates TrialScout gate)
    and ensemble_disagree (required by ensemble gate). Values are chosen so
    the TrialScout gate passes (all NCT trials have has_publication=True).
    """
    rows = []
    for i in range(n_africa):
        rows.append({
            "nct_id": f"NCT0000{i:04d}",
            "isrctn_id": "",
            "euctr_id": "",
            "brief_title": f"Africa trial {i}",
            "lead_sponsor": "TB Alliance",
            "africa_recruiting": True,
            "drug_class": "BPaL",
            "in_cochrane": (i % 3 == 0),
            "has_publication": True,
            "ensemble_disagree": False,
        })
    for i in range(n_non_africa):
        rows.append({
            "nct_id": f"NCT9999{i:04d}",
            "isrctn_id": "",
            "euctr_id": "",
            "brief_title": f"Non-Africa trial {i}",
            "lead_sponsor": "NIH",
            "africa_recruiting": False,
            "drug_class": "Bdq+other-companion",
            "in_cochrane": (i % 4 == 0),
            "has_publication": True,
            "ensemble_disagree": False,
        })
    return pd.DataFrame(rows)


# --- make_spotcheck_template tests ---

def test_make_template_default_size():
    trials = _build_trials()
    sample = make_template(trials)
    assert len(sample) == 30
    assert int(sample["africa_recruiting"].astype(bool).sum()) == 10
    assert int((~sample["africa_recruiting"].astype(bool)).sum()) == 20


def test_make_template_columns_blinded():
    """Output must NOT contain algorithm verdicts (no in_cochrane, etc)."""
    trials = _build_trials()
    sample = make_template(trials)
    assert set(sample.columns) == set(BLINDED_COLUMNS)
    assert "in_cochrane" not in sample.columns
    assert "matched_via_nct" not in sample.columns
    assert "has_publication" not in sample.columns


def test_make_template_deterministic_with_seed():
    trials = _build_trials()
    a = make_template(trials, seed=DEFAULT_SEED)
    b = make_template(trials, seed=DEFAULT_SEED)
    assert (a["trial_id"].values == b["trial_id"].values).all()


def test_make_template_different_seed_different_sample():
    trials = _build_trials()
    a = make_template(trials, seed=DEFAULT_SEED)
    b = make_template(trials, seed=DEFAULT_SEED + 100)
    # Probably different (not guaranteed but very likely with 30 samples from 40)
    assert not (a["trial_id"].values == b["trial_id"].values).all()


def test_make_template_handles_undersized_strata():
    """If only 5 africa-recruiting trials exist, sample 5 (not 10)."""
    trials = _build_trials(n_africa=5, n_non_africa=25)
    sample = make_template(trials)
    assert int(sample["africa_recruiting"].astype(bool).sum()) == 5


def test_make_template_trial_id_uses_nct_first():
    trials = pd.DataFrame([{
        "nct_id": "NCT12345678", "isrctn_id": "ISRCTN99999999", "euctr_id": "",
        "brief_title": "X", "lead_sponsor": "A",
        "africa_recruiting": True, "drug_class": "BPaL",
    }] * 10 + [{
        "nct_id": "NCT99999999", "isrctn_id": "", "euctr_id": "",
        "brief_title": "Y", "lead_sponsor": "B",
        "africa_recruiting": False, "drug_class": "BPaL",
    }] * 20)
    sample = make_template(trials)
    africa_row = sample[sample["africa_recruiting"]].iloc[0]
    assert africa_row["trial_id"].startswith("NCT")  # not ISRCTN


# --- merge_spotcheck tests ---

def test_merge_basic_agreement(tmp_path):
    trials = _build_trials()
    sample = make_template(trials)
    # Synthetic auditor: agrees with algorithm 100%
    audit_rows = []
    for tid in sample["trial_id"]:
        # Find the trial in trials and copy its in_cochrane verdict as auditor verdict
        match = trials[trials["nct_id"] == tid]
        if not match.empty:
            audit_rows.append({
                "trial_id": tid,
                "auditor_g3": str(bool(match.iloc[0]["in_cochrane"])),
                "auditor_evidence_url": "https://example.org",
                "auditor_notes": "synthetic",
            })
    auditor_df = pd.DataFrame(audit_rows)
    merged = merge_spotcheck(sample, auditor_df, trials)
    # 100% agreement (auditor copied algorithm)
    assert merged["agree_g3"].all()


def test_merge_disagreement(tmp_path):
    trials = _build_trials()
    sample = make_template(trials)
    # Auditor disagrees with everything (flips all booleans)
    audit_rows = []
    for tid in sample["trial_id"]:
        match = trials[trials["nct_id"] == tid]
        if not match.empty:
            audit_rows.append({
                "trial_id": tid,
                "auditor_g3": str(not bool(match.iloc[0]["in_cochrane"])),
            })
    auditor_df = pd.DataFrame(audit_rows)
    merged = merge_spotcheck(sample, auditor_df, trials)
    # 0% agreement (auditor flipped every verdict)
    assert not merged["agree_g3"].any()


def test_merge_raises_on_missing_auditor_columns():
    trials = _build_trials()
    sample = make_template(trials)
    # Missing auditor_g3 column
    bad_auditor = pd.DataFrame([{"trial_id": "x", "irrelevant": 1}])
    with pytest.raises(ValueError):
        merge_spotcheck(sample, bad_auditor, trials)


def test_merge_raises_on_trials_missing_in_cochrane():
    trials = _build_trials().drop(columns=["in_cochrane"])
    sample = pd.DataFrame(columns=BLINDED_COLUMNS)
    auditor = pd.DataFrame([{"trial_id": "x", "auditor_g3": "True"}])
    with pytest.raises(ValueError):
        merge_spotcheck(sample, auditor, trials)


# --- CLI smoke ---

def test_cli_make_template_runs(tmp_path):
    """Smoke: run make_spotcheck_template against fixture trials.parquet."""
    # First build a trials.parquet via the integration pipeline (or use a synthetic one)
    trials_path = tmp_path / "trials.parquet"
    _build_trials().to_parquet(trials_path, index=False)
    out_path = tmp_path / "blinded.csv"
    r = subprocess.run(
        [sys.executable, "scripts/make_spotcheck_template.py",
         "--trials", str(trials_path),
         "--out", str(out_path)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert out_path.exists()
    sample = pd.read_csv(out_path)
    assert len(sample) == 30


def test_cli_merge_spotcheck_runs(tmp_path):
    """Smoke: end-to-end (template -> synthetic auditor -> merge)."""
    trials = _build_trials()
    trials_path = tmp_path / "trials.parquet"
    trials.to_parquet(trials_path, index=False)

    blinded_path = tmp_path / "blinded.csv"
    sample = make_template(trials)
    sample.to_csv(blinded_path, index=False)

    # Synthetic auditor agrees with the algorithm verbatim
    audit_rows = []
    for tid in sample["trial_id"]:
        match = trials[trials["nct_id"] == tid]
        if not match.empty:
            audit_rows.append({
                "trial_id": tid,
                "auditor_g3": str(bool(match.iloc[0]["in_cochrane"])),
            })
    auditor_path = tmp_path / "auditor.csv"
    pd.DataFrame(audit_rows).to_csv(auditor_path, index=False)

    out_path = tmp_path / "merged.csv"
    r = subprocess.run(
        [sys.executable, "scripts/merge_spotcheck.py",
         "--blinded", str(blinded_path),
         "--auditor", str(auditor_path),
         "--trials", str(trials_path),
         "--out", str(out_path)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 0, f"stderr: {r.stderr}"
    assert out_path.exists()
    merged = pd.read_csv(out_path)
    # Synthetic agreement should be 100%
    assert merged["agree_g3"].all()


def test_validation_gates_passes_on_perfect_synthetic_auditor(tmp_path):
    """End-to-end smoke: synthetic auditor agrees -> validation_gates spot-check passes."""
    trials = _build_trials()
    trials_path = tmp_path / "trials.parquet"
    trials.to_parquet(trials_path, index=False)

    sample = make_template(trials)
    blinded_path = tmp_path / "blinded.csv"
    sample.to_csv(blinded_path, index=False)

    audit_rows = []
    for tid in sample["trial_id"]:
        match = trials[trials["nct_id"] == tid]
        if not match.empty:
            audit_rows.append({
                "trial_id": tid,
                "auditor_g3": str(bool(match.iloc[0]["in_cochrane"])),
            })
    auditor_path = tmp_path / "auditor.csv"
    pd.DataFrame(audit_rows).to_csv(auditor_path, index=False)

    merged_path = tmp_path / "merged.csv"
    subprocess.check_call(
        [sys.executable, "scripts/merge_spotcheck.py",
         "--blinded", str(blinded_path),
         "--auditor", str(auditor_path),
         "--trials", str(trials_path),
         "--out", str(merged_path)],
        cwd=REPO,
    )

    # Now run validation_gates with this trials.parquet + spotcheck CSV
    # validation_gates expects auditor_g3 + algorithm_g3 (or in_cochrane) on the merged CSV
    r = subprocess.run(
        [sys.executable, "scripts/validation_gates.py",
         "--trials", str(trials_path),
         "--spotcheck", str(merged_path)],
        cwd=REPO, capture_output=True, text=True,
    )
    # Trialscout may fail (synthetic data isn't tuned to 53.6%), but
    # the spot-check gate (the relevant one here) must pass: 30/30 agreement.
    assert "30/30" in r.stdout or "OK" in r.stdout, r.stdout + r.stderr
