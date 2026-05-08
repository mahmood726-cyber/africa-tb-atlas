import pytest
import pandas as pd
from tb_atlas.cochrane_match import match_trial


@pytest.fixture
def pairwise70_micro():
    return pd.DataFrame([
        {"review_id": "CD012345", "nct_id": "NCT04207112", "isrctn_id": ""},
        {"review_id": "CD012346", "nct_id": "", "isrctn_id": "ISRCTN26973455"},
        {"review_id": "CD012347", "nct_id": "NCT04207112", "isrctn_id": "ISRCTN26973455"},
    ])


@pytest.fixture
def cdsr_micro():
    return {
        "CD012348": ["Smith 2019; BPaL Phase 3 in MDR-TB"],
        "CD012349": ["TB-PRACTECAL bedaquiline pretomanid"],
    }


def test_match_via_nct_alone(pairwise70_micro, cdsr_micro):
    row = pd.Series({"nct_id": "NCT04207112", "isrctn_id": "", "brief_title": "X"})
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["in_cochrane"] is True
    assert out["matched_via_nct"] is True
    assert out["matched_via_isrctn"] is False
    assert "CD012345" in out["review_ids"]


def test_match_via_isrctn_alone(pairwise70_micro, cdsr_micro):
    row = pd.Series({"nct_id": "", "isrctn_id": "ISRCTN26973455", "brief_title": "X"})
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["in_cochrane"] is True
    assert out["matched_via_isrctn"] is True
    assert out["matched_via_nct"] is False


def test_match_via_cdsr_string_only(pairwise70_micro, cdsr_micro):
    row = pd.Series({
        "nct_id": "", "isrctn_id": "",
        "brief_title": "BPaL Phase 3 in MDR-TB",
    })
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["matched_via_cdsr_string"] is True
    assert out["in_cochrane"] is True


def test_no_match(pairwise70_micro, cdsr_micro):
    row = pd.Series({
        "nct_id": "NCT99999999", "isrctn_id": "",
        "brief_title": "Unrelated trial title",
    })
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["in_cochrane"] is False
    assert out["matched_via_nct"] is False
    assert out["matched_via_isrctn"] is False
    assert out["matched_via_cdsr_string"] is False


def test_ensemble_disagreement_logged(pairwise70_micro, cdsr_micro):
    """NCT-bridge says yes; CDSR string says no -> ensemble_disagree=True."""
    row = pd.Series({
        "nct_id": "NCT04207112",  # in pairwise70
        "isrctn_id": "",
        "brief_title": "Title that doesn't match any CDSR string at all whatsoever",
    })
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["matched_via_nct"] is True
    assert out["matched_via_cdsr_string"] is False
    assert out["ensemble_disagree"] is True


def test_match_combines_review_ids_across_components(pairwise70_micro, cdsr_micro):
    """A trial with NCT and ISRCTN both in P70 picks up reviews from BOTH lookups."""
    row = pd.Series({
        "nct_id": "NCT04207112",
        "isrctn_id": "ISRCTN26973455",
        "brief_title": "X",
    })
    out = match_trial(row, pairwise70_micro, cdsr_micro)
    assert out["matched_via_nct"] is True
    assert out["matched_via_isrctn"] is True
    # CD012345 (via NCT), CD012346 (via ISRCTN), CD012347 (via either)
    assert set(out["review_ids"]) == {"CD012345", "CD012346", "CD012347"}


def test_no_disagreement_when_no_inputs():
    """All three component inputs missing -> ensemble_disagree=False."""
    row = pd.Series({"nct_id": "", "isrctn_id": "", "brief_title": ""})
    out = match_trial(row, pd.DataFrame({"review_id": [], "nct_id": [], "isrctn_id": []}), {})
    assert out["in_cochrane"] is False
    assert out["ensemble_disagree"] is False


def test_cdsr_string_match_case_insensitive(pairwise70_micro):
    """Title match should be case-insensitive."""
    cdsr = {"CD012350": ["bpal phase 3 in mdr-tb"]}  # all lowercase
    row = pd.Series({
        "nct_id": "", "isrctn_id": "",
        "brief_title": "BPaL Phase 3 in MDR-TB",  # mixed case
    })
    out = match_trial(row, pairwise70_micro, cdsr)
    assert out["matched_via_cdsr_string"] is True


def test_short_title_does_not_match():
    """Brief titles shorter than 5 chars should NOT trigger CDSR match (false-positive risk)."""
    cdsr = {"CD012351": ["abc xyz"]}
    row = pd.Series({"nct_id": "", "isrctn_id": "", "brief_title": "abc"})
    out = match_trial(row, pd.DataFrame({"review_id": [], "nct_id": [], "isrctn_id": []}), cdsr)
    assert out["matched_via_cdsr_string"] is False


def test_pairwise70_normalisation_handles_nct_column_name():
    """PACTR's parquet uses column name 'nct'; normaliser should rename to 'nct_id'."""
    p70_pactr_format = pd.DataFrame([
        {"review_id": "CD012345", "nct": "NCT04207112"}  # 'nct' not 'nct_id'
    ])
    row = pd.Series({"nct_id": "NCT04207112", "isrctn_id": "", "brief_title": "X"})
    out = match_trial(row, p70_pactr_format, {})
    assert out["matched_via_nct"] is True
