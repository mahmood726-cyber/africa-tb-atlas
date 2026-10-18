"""Data-frame boundary regressions, reusing identifiers from stored fixtures."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tb_atlas.results_posting import has_results_posted
from tb_atlas.trial_dedup import dedup_trials

FIXTURES = Path(__file__).parent / "fixtures"
IDS = pd.read_csv(FIXTURES / "aact_micro" / "studies.txt", sep="|")["nct_id"].tolist()


def test_dedup_accepts_filtered_nonpositional_index():
    aact = pd.DataFrame({"nct_id": [IDS[0]], "brief_title": ["source record"]}, index=[25])
    ictrp = pd.DataFrame({"nct_id": [IDS[0]]}, index=[90])
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 1
    assert out.iloc[0]["brief_title"] == "source record"
    assert log.iloc[0]["decision"] == "merged_nct"
    assert aact.index.tolist() == [25]


def test_dedup_drops_only_matching_row_when_labels_repeat():
    aact = pd.DataFrame({"nct_id": [IDS[0]]})
    ictrp = pd.DataFrame({"nct_id": [IDS[0], IDS[1]]}, index=[7, 7])
    out, log = dedup_trials(aact, ictrp)
    assert out["nct_id"].tolist() == IDS[:2]
    assert len(log) == 2


@pytest.mark.parametrize("missing", [None, np.nan, pd.NA])
def test_missing_ids_do_not_match_each_other(missing):
    aact = pd.DataFrame({"nct_id": [missing]})
    ictrp = pd.DataFrame({"nct_id": [missing]})
    out, log = dedup_trials(aact, ictrp)
    assert len(out) == 2
    assert log.iloc[0]["decision"] == "kept_ictrp_only"
    assert log.iloc[0]["trial_id"] == ""


@pytest.mark.parametrize("source,field", [("aact", "results_first_posted_date"), ("ictrp", "result_url")])
@pytest.mark.parametrize("missing", [None, np.nan, pd.NA, pd.NaT, "", "   ", "None", "NaN", "NaT", "<NA>"])
def test_missing_results_never_count_as_posted(source, field, missing):
    assert has_results_posted(pd.Series({"source": source, field: missing})) is False
