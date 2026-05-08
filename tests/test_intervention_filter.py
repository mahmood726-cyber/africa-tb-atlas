import pytest
from tb_atlas.intervention_filter import (
    matches_target_drug, matches_negative_list, contains_target_drug,
    AmbiguousInterventionError,
    POSITIVE_LIST, NEGATIVE_LIST,
)


# ---------------------------------------------------------------------------
# Positive: should match
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,expected", [
    ("Bedaquiline", "bedaquiline"),
    ("bedaquiline (Sirturo)", "bedaquiline"),
    ("BDQ 400mg", "bedaquiline"),
    ("Sirturo", "bedaquiline"),
    ("TMC-207", "bedaquiline"),
    ("Pretomanid", "pretomanid"),
    ("PA-824", "pretomanid"),
    ("Pa-824", "pretomanid"),
    ("PA 824 200 mg", "pretomanid"),
    ("Dovprela", "pretomanid"),
    ("Linezolid", "linezolid"),
    ("ZYVOX 600mg", "linezolid"),
    ("linezolid (Linox)", "linezolid"),
    ("Linospan tablets", "linezolid"),
    ("U-100766", "linezolid"),
])
def test_matches_target_drug_positive(name, expected):
    assert matches_target_drug(name) == expected


# ---------------------------------------------------------------------------
# Negative: must NOT match (drug-class confusables)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", [
    "TBA-354",
    "TBA 354",
    "PA-1314",
    "TBA-7371",
])
def test_matches_target_drug_negative_confusable(name):
    """The negative list must NOT match these compounds (they are NOT
    bedaquiline / pretomanid / linezolid). matches_negative_list returns
    True; matches_target_drug returns None unless ALSO a positive match."""
    assert matches_negative_list(name) is True
    assert matches_target_drug(name) is None  # negative-only, no positive


# ---------------------------------------------------------------------------
# Unrelated drugs: neither positive nor negative
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", [
    "Rifapentine",
    "Moxifloxacin",
    "Isoniazid",
    "Placebo",
    "Standard of care",
    "Ethambutol",
])
def test_matches_target_drug_unrelated_drugs(name):
    assert matches_target_drug(name) is None
    assert matches_negative_list(name) is False


# ---------------------------------------------------------------------------
# contains_target_drug
# ---------------------------------------------------------------------------
def test_contains_target_drug_on_intervention_list():
    interventions = ["Linezolid", "Moxifloxacin"]
    assert contains_target_drug(interventions) is True


def test_contains_target_drug_returns_false_when_none_match():
    assert contains_target_drug(["Rifapentine", "Isoniazid"]) is False


def test_contains_target_drug_handles_empty_list():
    assert contains_target_drug([]) is False
    assert contains_target_drug(None) is False


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------
def test_strict_mode_raises_on_dual_match():
    """If a free-text intervention contains BOTH a positive and a negative-list pattern."""
    with pytest.raises(AmbiguousInterventionError):
        matches_target_drug("PA-824 / TBA-354 combination", strict=True)


def test_default_mode_does_not_raise_on_dual_match():
    """Default (strict=False) returns the positive match without raising."""
    result = matches_target_drug("PA-824 / TBA-354 combination", strict=False)
    assert result == "pretomanid"


# ---------------------------------------------------------------------------
# Canonical name / case
# ---------------------------------------------------------------------------
def test_returns_canonical_name_lowercase():
    assert matches_target_drug("Sirturo") == "bedaquiline"
    assert matches_target_drug("PA-824") == "pretomanid"
    assert matches_target_drug("Zyvox") == "linezolid"


# ---------------------------------------------------------------------------
# Word boundary
# ---------------------------------------------------------------------------
def test_word_boundary_prevents_substring_match():
    """'bedaquiline-something' should match (bedaquiline is the prefix);
    but 'subbedaquiline' should NOT (no word boundary)."""
    # Positive: word boundary at start, hyphen acts as boundary at end
    assert matches_target_drug("bedaquiline-resistant strain") == "bedaquiline"
    # Negative: prefix without boundary
    assert matches_target_drug("notbedaquiline") is None


# ---------------------------------------------------------------------------
# Structural / invariant checks
# ---------------------------------------------------------------------------
def test_positive_list_keys_are_canonical_names():
    """Sanity: keys in POSITIVE_LIST must be the 3 canonical drug names."""
    assert set(POSITIVE_LIST.keys()) == {"bedaquiline", "pretomanid", "linezolid"}


def test_negative_list_includes_tba_354():
    """Critical: TBA-354 must be in negative list to prevent silent corruption.
    Lessons file: drug-name confusables hazard (spec §2.5)."""
    text_blob = " ".join(NEGATIVE_LIST)
    assert "tba" in text_blob.lower()
    assert "354" in text_blob


# ---------------------------------------------------------------------------
# None / empty input guards
# ---------------------------------------------------------------------------
def test_handles_none_input():
    assert matches_target_drug(None) is None
    assert matches_negative_list(None) is False
    assert matches_target_drug("") is None
