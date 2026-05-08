import pandas as pd
from tb_atlas.date_filter import is_modern_era, BEDAQUILINE_EUA_DATE


def test_modern_era_after_eua():
    assert is_modern_era(pd.Timestamp("2013-01-01")) is True


def test_modern_era_excludes_2010():
    assert is_modern_era(pd.Timestamp("2010-05-01")) is False


def test_modern_era_boundary_inclusive():
    assert is_modern_era(BEDAQUILINE_EUA_DATE) is True


def test_modern_era_one_day_before_excluded():
    assert is_modern_era(pd.Timestamp("2012-12-27")) is False


def test_modern_era_handles_nat():
    assert is_modern_era(pd.NaT) is False


def test_modern_era_handles_string_input():
    """pd.Timestamp() accepts strings."""
    assert is_modern_era("2018-01-01") is True
    assert is_modern_era("2010-01-01") is False
