import pandas as pd
import pytest
from tb_atlas.funnel import compute_funnel, clustered_bootstrap_ci, EmptyFunnelInput


def _trial(nct, africa, lead, enrollment, g1, g2, g3, isrctn=""):
    return dict(
        nct_id=nct, isrctn_id=isrctn, africa_recruiting=africa,
        lead_sponsor=lead, enrollment=enrollment,
        has_results_posted=g1, has_publication=g2, in_cochrane=g3,
    )


def test_compute_funnel_aggregates_per_stratum():
    df = pd.DataFrame([
        _trial("N1", True, "TB Alliance", 100, True, True, True),
        _trial("N2", True, "TB Alliance", 80, True, True, False),
        _trial("N3", False, "NIH", 200, True, False, False),
        _trial("N4", False, "NIH", 50, True, True, True),
    ])
    out = compute_funnel(df, stratify_by="africa_recruiting")
    africa = out[out.africa_recruiting == True].iloc[0]
    assert africa.n_trials == 2
    assert africa.n_in_cochrane == 1
    assert africa.n_participants == 180  # 100 + 80
    assert africa.pct_g0_to_g3 == pytest.approx(0.5)
    assert africa.pct_g0_to_g3_pat == pytest.approx(100/180)


def test_compute_funnel_handles_null_enrollment():
    df = pd.DataFrame([
        _trial("N1", True, "TBA", None, True, True, True),
        _trial("N2", True, "TBA", 100, True, True, True),
    ])
    out = compute_funnel(df, stratify_by="africa_recruiting")
    africa = out[out.africa_recruiting == True].iloc[0]
    assert africa.n_trials == 2  # both kept in trial-weighted
    assert africa.n_participants == 100  # only the non-null in patient-weighted


def test_bootstrap_ci_undefined_when_k_lt_3():
    df = pd.DataFrame([
        _trial("N1", True, "A", 100, True, True, True),
        _trial("N2", True, "B", 100, True, True, False),
    ])
    lo, hi = clustered_bootstrap_ci(
        df.assign(_g3=df.in_cochrane.astype(int)),
        value_col="_g3", cluster_col="lead_sponsor", n_boot=100,
    )
    assert lo is None and hi is None


def test_bootstrap_ci_returns_bounds_when_k_ge_3():
    df = pd.DataFrame([
        _trial(f"N{i}", True, f"S{i%5}", 100, True, True, i % 2 == 0)
        for i in range(20)
    ])
    lo, hi = clustered_bootstrap_ci(
        df.assign(_g3=df.in_cochrane.astype(int)),
        value_col="_g3", cluster_col="lead_sponsor", n_boot=200,
    )
    assert lo is not None and hi is not None
    assert 0 <= lo <= hi <= 1


def test_compute_funnel_empty_raises():
    with pytest.raises(EmptyFunnelInput):
        compute_funnel(pd.DataFrame(), stratify_by="africa_recruiting")


def test_compute_funnel_missing_stratify_column_raises():
    df = pd.DataFrame([_trial("N1", True, "A", 100, True, True, True)])
    with pytest.raises(KeyError):
        compute_funnel(df, stratify_by="nonexistent_column")


def test_compute_funnel_n_invisible_counts_no_nct_no_isrctn():
    df = pd.DataFrame([
        _trial("", True, "TBA", 100, True, True, False, isrctn=""),
        _trial("NCT01", True, "TBA", 100, True, True, True),
        _trial("", True, "TBA", 50, False, False, False, isrctn="ISRCTN01"),  # has ISRCTN, not invisible
    ])
    out = compute_funnel(df, stratify_by="africa_recruiting")
    africa = out[out.africa_recruiting == True].iloc[0]
    assert africa.n_invisible == 1  # only the first row (no NCT, no ISRCTN)


def test_compute_funnel_three_tier_stratification():
    """Stratify by africa_tier (string) — should produce 3 rows."""
    df = pd.DataFrame([
        _trial("N1", True, "A", 100, True, True, True),
        _trial("N2", True, "B", 80, True, True, False),
        _trial("N3", False, "C", 200, True, False, False),
    ])
    df["africa_tier"] = ["African-led", "African-recruiting", "non-Africa"]
    out = compute_funnel(df, stratify_by="africa_tier")
    assert len(out) == 3
    assert set(out.africa_tier) == {"African-led", "African-recruiting", "non-Africa"}


def test_compute_funnel_works_without_isrctn_column():
    """nct_id-only DataFrame (e.g., AACT alone) — n_invisible should still compute."""
    df = pd.DataFrame([
        {"nct_id": "NCT01", "africa_recruiting": True, "lead_sponsor": "A",
         "enrollment": 100, "has_results_posted": True,
         "has_publication": True, "in_cochrane": True},
    ])
    out = compute_funnel(df, stratify_by="africa_recruiting")
    assert out.iloc[0].n_trials == 1


def test_compute_funnel_has_required_output_columns():
    df = pd.DataFrame([_trial("N1", True, "A", 100, True, True, True)])
    out = compute_funnel(df, stratify_by="africa_recruiting")
    expected_cols = {
        "africa_recruiting", "n_trials", "n_results_posted", "n_peer_published",
        "n_in_cochrane", "n_invisible",
        "n_participants", "n_participants_results_posted",
        "n_participants_peer_published", "n_participants_in_cochrane",
        "pct_g0_to_g3", "pct_g0_to_g3_pat",
        "pct_g0_to_g3_ci_lo", "pct_g0_to_g3_ci_hi",
    }
    assert expected_cols.issubset(set(out.columns)), f"missing: {expected_cols - set(out.columns)}"
