"""Tests for scripts/validation_gates.py."""
import sys
import subprocess
from pathlib import Path

import pytest
import pandas as pd

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from validation_gates import (
    check_trialscout_sanity, check_spotcheck_g3_only, check_ensemble_disagreement,
    _trialscout_from_trials, _spotcheck_g3_agreement, _ensemble_disagree_count,
    TRIALSCOUT_LOWER_BOUND, SPOTCHECK_THRESHOLD, ENSEMBLE_DISAGREE_FRACTION,
)


# --- Pure-function gate tests ---

def test_trialscout_sanity_pass_at_baseline():
    assert check_trialscout_sanity(0.636) is True


def test_trialscout_sanity_pass_high():
    """One-sided: high values pass (TB Alliance funding pushes G2 up)."""
    assert check_trialscout_sanity(0.95) is True


def test_trialscout_sanity_pass_at_lower_bound_inclusive():
    """Boundary: 0.536 (53.6%) is inclusive."""
    assert check_trialscout_sanity(0.536) is True


def test_trialscout_sanity_fail_below_lower_bound():
    """Just below 53.6% fails."""
    assert check_trialscout_sanity(0.40) is False


def test_trialscout_sanity_pass_on_nan():
    """NaN cannot evaluate; pass (warn-not-block semantic)."""
    import math
    assert check_trialscout_sanity(float("nan")) is True
    assert check_trialscout_sanity(None) is True


def test_spotcheck_passes_at_27_of_30():
    assert check_spotcheck_g3_only(agreements=27, total=30) is True


def test_spotcheck_passes_at_30_of_30():
    assert check_spotcheck_g3_only(agreements=30, total=30) is True


def test_spotcheck_fails_at_26_of_30():
    assert check_spotcheck_g3_only(agreements=26, total=30) is False


def test_spotcheck_fails_when_n_not_exactly_30():
    """n_total must be EXACTLY 30 — partial cohorts not accepted."""
    assert check_spotcheck_g3_only(agreements=27, total=29) is False
    assert check_spotcheck_g3_only(agreements=28, total=31) is False


def test_ensemble_disagreement_pass_at_4pct():
    assert check_ensemble_disagreement(disagree=4, total=100) is True


def test_ensemble_disagreement_fail_at_5pct():
    """5% is the threshold; fail at exactly 5% (strict <0.05)."""
    assert check_ensemble_disagreement(disagree=5, total=100) is False


def test_ensemble_disagreement_fail_at_6pct():
    assert check_ensemble_disagreement(disagree=6, total=100) is False


def test_ensemble_disagreement_pass_when_zero_in_cochrane():
    """Vacuously True when no trials in Cochrane."""
    assert check_ensemble_disagreement(disagree=0, total=0) is True


# --- Integration helper tests ---

def test_trialscout_from_trials_returns_g2_rate():
    df = pd.DataFrame([
        {"nct_id": "NCT01", "has_publication": True},
        {"nct_id": "NCT02", "has_publication": True},
        {"nct_id": "NCT03", "has_publication": False},
    ])
    rate = _trialscout_from_trials(df)
    assert rate == pytest.approx(2/3)


def test_trialscout_from_trials_skips_no_nct():
    """Trials without NCT id are excluded from cross-registered subset."""
    df = pd.DataFrame([
        {"nct_id": "NCT01", "has_publication": True},
        {"nct_id": "", "has_publication": False},  # excluded
        {"nct_id": "", "has_publication": False},
    ])
    rate = _trialscout_from_trials(df)
    assert rate == pytest.approx(1.0)  # only the NCT01 row counts


def test_trialscout_from_trials_returns_nan_when_no_cross_registered():
    import math
    df = pd.DataFrame([{"nct_id": "", "has_publication": False}])
    rate = _trialscout_from_trials(df)
    assert math.isnan(rate)


def test_spotcheck_g3_agreement_reads_csv(tmp_path):
    csv = tmp_path / "spot.csv"
    csv.write_text(
        "trial_id,auditor_g3,algorithm_g3\n"
        "NCT1,True,True\n"
        "NCT2,False,False\n"
        "NCT3,True,False\n",
        encoding="utf-8",
    )
    n_agree, n_total = _spotcheck_g3_agreement(csv)
    assert n_agree == 2
    assert n_total == 3


def test_spotcheck_g3_agreement_falls_back_to_in_cochrane(tmp_path):
    """If algorithm_g3 column is absent, fall back to in_cochrane."""
    csv = tmp_path / "spot.csv"
    csv.write_text(
        "trial_id,auditor_g3,in_cochrane\n"
        "NCT1,True,True\n"
        "NCT2,False,True\n",
        encoding="utf-8",
    )
    n_agree, n_total = _spotcheck_g3_agreement(csv)
    assert n_agree == 1


def test_spotcheck_raises_on_missing_auditor_column(tmp_path):
    csv = tmp_path / "spot.csv"
    csv.write_text(
        "trial_id,algorithm_g3\nNCT1,True\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        _spotcheck_g3_agreement(csv)


def test_ensemble_disagree_count_basic():
    df = pd.DataFrame([
        {"in_cochrane": True, "ensemble_disagree": False},
        {"in_cochrane": True, "ensemble_disagree": True},
        {"in_cochrane": False, "ensemble_disagree": True},  # excluded (not in_cochrane)
    ])
    n_dis, n_in_c = _ensemble_disagree_count(df)
    assert n_in_c == 2
    assert n_dis == 1


def test_ensemble_disagree_count_no_in_cochrane():
    df = pd.DataFrame([{"in_cochrane": False, "ensemble_disagree": True}])
    n_dis, n_in_c = _ensemble_disagree_count(df)
    assert n_in_c == 0
    assert n_dis == 0


# --- CLI smoke ---

def test_cli_runs_without_inputs_returns_neutral_exit(tmp_path):
    """No trials.parquet or spotcheck.csv -> exit code 2 (neutral)."""
    r = subprocess.run(
        [sys.executable, "scripts/validation_gates.py",
         "--trials", str(tmp_path / "missing.parquet"),
         "--spotcheck", str(tmp_path / "missing.csv")],
        cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 2
