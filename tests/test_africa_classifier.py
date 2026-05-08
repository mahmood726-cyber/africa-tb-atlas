import pytest
from tb_atlas.africa_classifier import (
    classify_africa, AfricaTier, UnknownCountryError, AFRICAN_ALPHA2,
)


def test_binary_one_african_site_makes_recruiting():
    out = classify_africa(["South Africa", "United Kingdom"])
    assert out["africa_recruiting"] is True
    assert out["africa_site_share"] == pytest.approx(0.5)
    assert out["n_african_sites"] == 1
    assert out["n_total_sites"] == 2


def test_no_african_site_not_recruiting():
    out = classify_africa(["United States", "Germany"])
    assert out["africa_recruiting"] is False
    assert out["africa_site_share"] == 0.0
    assert out["africa_tier"] == AfricaTier.NON_AFRICA


def test_majority_african_is_african_led_tier():
    """3 of 5 = 60% -> African-led (>=50% threshold)."""
    out = classify_africa(["South Africa", "Kenya", "Uganda", "United Kingdom", "United States"])
    assert out["africa_tier"] == AfricaTier.AFRICAN_LED
    assert out["africa_site_share"] == pytest.approx(0.6)


def test_minority_african_is_recruiting_tier():
    """1 of 4 = 25% -> African-recruiting (>0% but <50%)."""
    out = classify_africa(["South Africa", "United States", "United Kingdom", "Germany"])
    assert out["africa_tier"] == AfricaTier.AFRICAN_RECRUITING


def test_site_share_30pct_threshold_inclusive():
    """3 of 10 = 30.0% (boundary-inclusive)."""
    countries = ["South Africa", "Kenya", "Uganda"] + ["United States"] * 7
    out = classify_africa(countries)
    assert out["site_share_30pct"] is True
    # And share should be exactly 0.3
    assert out["africa_site_share"] == pytest.approx(0.3)


def test_site_share_below_30pct_false():
    """2 of 10 = 20% -> site_share_30pct False."""
    countries = ["South Africa", "Kenya"] + ["United States"] * 8
    out = classify_africa(countries)
    assert out["site_share_30pct"] is False


def test_unknown_country_raises():
    with pytest.raises(UnknownCountryError):
        classify_africa(["Atlantis"])


def test_handles_drc_vs_republic_of_congo():
    """DRC (CD) and Republic of the Congo (CG) are distinct countries; both African."""
    drc = classify_africa(["Democratic Republic of the Congo"])
    roc = classify_africa(["Republic of the Congo"])
    assert drc["africa_recruiting"] is True
    assert roc["africa_recruiting"] is True


def test_handles_eswatini_and_swaziland_aliases():
    """Both names resolve to SZ."""
    a = classify_africa(["Eswatini"])
    b = classify_africa(["Swaziland"])
    assert a["africa_recruiting"] is True
    assert b["africa_recruiting"] is True


def test_handles_cote_divoire_with_special_char():
    """Both Cote d'Ivoire (with macron) and Cote d'Ivoire should resolve."""
    a = classify_africa(["Côte d'Ivoire"])
    b = classify_africa(["Cote d'Ivoire"])
    assert a["africa_recruiting"] is True
    assert b["africa_recruiting"] is True


def test_empty_country_list_returns_non_africa():
    out = classify_africa([])
    assert out["africa_recruiting"] is False
    assert out["africa_site_share"] == 0.0
    assert out["africa_tier"] == AfricaTier.NON_AFRICA
    assert out["n_total_sites"] == 0


def test_african_alpha2_has_54_codes():
    """Spec §2.5 caveat: 54 African countries hardcoded."""
    assert len(AFRICAN_ALPHA2) == 54


def test_africa_tier_enum_has_three_values():
    assert len(list(AfricaTier)) == 3


def test_case_insensitive_country_names():
    """'south africa' (lowercase) should resolve same as 'South Africa'."""
    a = classify_africa(["south africa"])
    b = classify_africa(["SOUTH AFRICA"])
    c = classify_africa(["South Africa"])
    assert a == b == c


def test_share_dtype_is_float():
    """Pandas downstream expects float, not Fraction or int."""
    out = classify_africa(["South Africa"])
    assert isinstance(out["africa_site_share"], float)
