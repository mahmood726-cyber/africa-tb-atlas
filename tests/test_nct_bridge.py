"""Test nct_bridge module: NCT, ISRCTN, EUCTR extraction."""
from tb_atlas.nct_bridge import (
    extract_nct, extract_isrctn, extract_euctr, is_tier0_invisible,
)


def test_extract_nct_from_text():
    """NCT IDs are 8-digit format."""
    assert extract_nct("see NCT04207112 for details") == "NCT04207112"


def test_extract_nct_returns_none_on_no_match():
    """Missing NCT returns None."""
    assert extract_nct("no id here") is None
    assert extract_nct(None) is None
    assert extract_nct("") is None


def test_extract_isrctn():
    """ISRCTN IDs are 8-digit format."""
    assert extract_isrctn("ISRCTN26973455") == "ISRCTN26973455"
    assert extract_isrctn("registered as ISRCTN12345678 in UK") == "ISRCTN12345678"


def test_extract_isrctn_returns_none_on_no_match():
    """Missing ISRCTN returns None."""
    assert extract_isrctn("no id here") is None
    assert extract_isrctn(None) is None


def test_extract_euctr():
    """EUCTR IDs follow format EUCTR####-######-##."""
    assert extract_euctr("EUCTR2018-001234-56") == "EUCTR2018-001234-56"
    assert extract_euctr("see EUCTR2020-005678-90 for details") == "EUCTR2020-005678-90"


def test_extract_euctr_returns_none_on_no_match():
    """Missing EUCTR returns None."""
    assert extract_euctr("no euctr here") is None


def test_all_three_extractors_independent_on_one_string():
    """Multiple IDs in one string — each extractor finds its own."""
    s = "Cross-registered as NCT04207112 and ISRCTN26973455"
    assert extract_nct(s) == "NCT04207112"
    assert extract_isrctn(s) == "ISRCTN26973455"
    assert extract_euctr(s) is None


def test_is_tier0_invisible():
    """Tier0: trials with no NCT cross-reference."""
    assert is_tier0_invisible(None) is True
    assert is_tier0_invisible("") is True
    assert is_tier0_invisible("NCT12345678") is False
