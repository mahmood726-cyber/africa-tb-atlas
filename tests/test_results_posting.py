import pandas as pd
import numpy as np
from tb_atlas.results_posting import has_results_posted


def test_aact_trial_with_results_date():
    row = pd.Series({"source": "aact", "results_first_posted_date": "2020-01-01", "result_url": ""})
    assert has_results_posted(row) is True


def test_aact_trial_without_results_date_none():
    row = pd.Series({"source": "aact", "results_first_posted_date": None, "result_url": ""})
    assert has_results_posted(row) is False


def test_aact_trial_without_results_date_nat():
    row = pd.Series({"source": "aact", "results_first_posted_date": pd.NaT, "result_url": ""})
    assert has_results_posted(row) is False


def test_aact_trial_without_results_date_nan():
    row = pd.Series({"source": "aact", "results_first_posted_date": np.nan, "result_url": ""})
    assert has_results_posted(row) is False


def test_aact_trial_empty_string():
    row = pd.Series({"source": "aact", "results_first_posted_date": "", "result_url": ""})
    assert has_results_posted(row) is False


def test_ictrp_trial_with_result_url():
    row = pd.Series({"source": "ictrp", "results_first_posted_date": None,
                     "result_url": "https://example.org/results/abc"})
    assert has_results_posted(row) is True


def test_ictrp_trial_without_result_url():
    row = pd.Series({"source": "ictrp", "results_first_posted_date": None, "result_url": ""})
    assert has_results_posted(row) is False


def test_ictrp_trial_with_whitespace_only_url():
    """Whitespace-only URL should not count as posted."""
    row = pd.Series({"source": "ictrp", "result_url": "   "})
    assert has_results_posted(row) is False


def test_unrecognised_source_returns_false():
    row = pd.Series({"source": "unknown", "results_first_posted_date": "2020-01-01"})
    assert has_results_posted(row) is False


def test_missing_source_returns_false():
    row = pd.Series({"results_first_posted_date": "2020-01-01"})
    assert has_results_posted(row) is False
