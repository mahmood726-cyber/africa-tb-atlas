import pandas as pd
import pytest
from tb_atlas.trial_dedup import dedup_trials, DedupConflictError


def _row(**kw):
    base = dict(nct_id="", isrctn_id="", euctr_id="", brief_title="",
                start_date=pd.NaT, enrollment=None,
                interventions=[], countries=[], conditions=[], lead_sponsor="",
                source="")
    base.update(kw)
    return base


def test_dedup_prefers_aact_over_ictrp_on_nct_match():
    aact = pd.DataFrame([_row(nct_id="NCT01", brief_title="AACT title", source="aact")])
    ictrp = pd.DataFrame([_row(nct_id="NCT01", brief_title="ICTRP title", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert out.iloc[0].brief_title == "AACT title"
    assert (log["decision"] == "merged_nct").any()


def test_dedup_uses_isrctn_when_no_nct():
    aact = pd.DataFrame([_row(isrctn_id="ISRCTN01", brief_title="AACT (rare)", source="aact")])
    ictrp = pd.DataFrame([_row(isrctn_id="ISRCTN01", brief_title="ICTRP", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert (log["decision"] == "merged_isrctn").any()


def test_dedup_uses_euctr_when_no_nct_or_isrctn():
    aact = pd.DataFrame([_row(euctr_id="EUCTR2018-001234-56", brief_title="AACT", source="aact")])
    ictrp = pd.DataFrame([_row(euctr_id="EUCTR2018-001234-56", brief_title="ICTRP", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert (log["decision"] == "merged_euctr").any()


def test_dedup_keeps_distinct_when_no_id_overlap():
    aact = pd.DataFrame([_row(nct_id="NCT01", brief_title="A", source="aact")])
    ictrp = pd.DataFrame([_row(nct_id="NCT02", brief_title="B", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 2
    assert (log["decision"] == "kept_ictrp_only").any()


def test_dedup_raises_on_conflicting_secondary_ids():
    """AACT NCT01 has ISRCTN01; ICTRP NCT01 has ISRCTN99 — ISRCTN disagrees."""
    aact = pd.DataFrame([_row(nct_id="NCT01", isrctn_id="ISRCTN01", source="aact")])
    ictrp = pd.DataFrame([_row(nct_id="NCT01", isrctn_id="ISRCTN99", source="ictrp")])
    with pytest.raises(DedupConflictError):
        dedup_trials(aact, ictrp)


def test_dedup_log_records_all_decisions():
    aact = pd.DataFrame([_row(nct_id="NCT01", source="aact")])
    ictrp = pd.DataFrame([
        _row(nct_id="NCT01", source="ictrp"),
        _row(nct_id="NCT02", source="ictrp"),
    ])
    out, log = dedup_trials(aact, ictrp)
    assert len(log) == 2  # one merge, one kept-ictrp-only
    decisions = set(log["decision"])
    assert "merged_nct" in decisions
    assert "kept_ictrp_only" in decisions


def test_dedup_handles_empty_ictrp():
    aact = pd.DataFrame([_row(nct_id="NCT01", source="aact")])
    ictrp = pd.DataFrame(columns=aact.columns)
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert len(log) == 0


def test_dedup_handles_empty_aact():
    aact = pd.DataFrame(columns=["nct_id", "isrctn_id", "euctr_id", "brief_title",
                                  "start_date", "enrollment", "interventions",
                                  "countries", "conditions", "lead_sponsor", "source"])
    ictrp = pd.DataFrame([_row(nct_id="NCT02", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert (log["decision"] == "kept_ictrp_only").any()


def test_dedup_priority_nct_beats_isrctn_when_both_present():
    """ICTRP row has both NCT and ISRCTN; AACT has only ISRCTN. Match via ISRCTN
    (NCT priority would not find a match, falls through to ISRCTN)."""
    aact = pd.DataFrame([_row(isrctn_id="ISRCTN01", source="aact")])
    ictrp = pd.DataFrame([_row(nct_id="NCT05", isrctn_id="ISRCTN01", source="ictrp")])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert (log["decision"] == "merged_isrctn").any()
