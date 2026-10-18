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

    if not isinstance(source, str) or source not in {"aact", "ictrp"}:
        return False
    field = "results_first_posted_date" if source == "aact" else "result_url"
    value = row.get(field)
    if value is None or pd.isna(value):
        return False
    return str(value).strip().lower() not in {"", "none", "nan", "nat", "<na>"}
