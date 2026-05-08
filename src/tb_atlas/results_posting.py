"""Gate 1: results posted (CT.gov OR ICTRP).

Source-aware: AACT uses results_first_posted_date; ICTRP uses result_url presence.
Acknowledged over-broad per spec §1.6 #12 (TrialScout-sanity check is one-sided
to compensate for the over-broadness of this gate).
"""
from __future__ import annotations
import pandas as pd


def has_results_posted(row) -> bool:
    """Return True if the trial has results posted via its registry's mechanism.

    AACT trials: results_first_posted_date is non-null.
    ICTRP trials: result_url is non-empty.

    If neither column is present (or row.source is unrecognised), returns False.
    """
    source = row.get("source", "")

    if source == "aact":
        v = row.get("results_first_posted_date")
        if v is None:
            return False
        if isinstance(v, float) and pd.isna(v):
            return False
        s = str(v).strip()
        return bool(s) and s.lower() != "nat" and s.lower() != "none"

    if source == "ictrp":
        url = row.get("result_url", "")
        if isinstance(url, float) and pd.isna(url):
            return False
        return bool(str(url).strip())

    return False
