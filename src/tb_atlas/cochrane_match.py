"""Cochrane-MA match (G3): union of three components.

Per spec §1.6 #9:
  in_cochrane = (NCT-bridge in Pairwise70) OR
                (ISRCTN-bridge in Pairwise70) OR
                (CDSR string-index title match)

Per-component flags tracked separately for audit. Ensemble disagreement
(any component disagreeing with another) computed as a pre-ship gate.
"""
from __future__ import annotations
from typing import Optional

import pandas as pd


def _normalise_pairwise70(p70) -> pd.DataFrame:
    """Pairwise70 may be a DataFrame OR a dict-like; coerce to DataFrame.

    Required columns: review_id, nct_id, isrctn_id (with empty strings for
    absent IDs). PACTR's parquet has columns 'nct' and 'review_id'; we
    normalise here.
    """
    if isinstance(p70, pd.DataFrame):
        df = p70.copy()
        # PACTR uses 'nct' column name; normalize to 'nct_id'.
        if "nct" in df.columns and "nct_id" not in df.columns:
            df = df.rename(columns={"nct": "nct_id"})
        # Ensure isrctn_id column exists (empty if absent in source).
        if "isrctn_id" not in df.columns:
            df["isrctn_id"] = ""
        return df
    # If passed a list of records or dict, wrap.
    return pd.DataFrame(p70)


def _nct_bridge_match(nct: Optional[str], p70: pd.DataFrame) -> tuple[bool, list[str]]:
    if not nct:
        return False, []
    hits = p70[p70["nct_id"].astype(str) == nct]
    if hits.empty:
        return False, []
    return True, sorted(set(hits["review_id"].astype(str)))


def _isrctn_bridge_match(isrctn: Optional[str], p70: pd.DataFrame) -> tuple[bool, list[str]]:
    if not isrctn:
        return False, []
    hits = p70[p70["isrctn_id"].astype(str) == isrctn]
    if hits.empty:
        return False, []
    return True, sorted(set(hits["review_id"].astype(str)))


def _cdsr_string_match(brief_title: str, cdsr_strings) -> tuple[bool, list[str]]:
    """Match a brief_title against per-review study-list strings.

    cdsr_strings is a dict {review_id: list[str]} — for each review, a list
    of study-list strings (typically of the form "Author 2019; trial name").
    Match if `brief_title` is a substring (case-insensitive) of any string
    in any review.
    """
    if not brief_title or not cdsr_strings:
        return False, []
    title_lower = brief_title.lower().strip()
    if len(title_lower) < 5:  # Don't match on overly-short titles
        return False, []
    matches = []
    for rid, strings in (cdsr_strings.items() if isinstance(cdsr_strings, dict) else []):
        for s in strings:
            if title_lower in s.lower():
                matches.append(rid)
                break
    return (len(matches) > 0), sorted(set(matches))


def match_trial(row, pairwise70, cdsr_strings) -> dict:
    """Run all three G3 components on a trial row; return verdict dict.

    Args:
        row: a pandas Series with at least nct_id, isrctn_id, brief_title.
        pairwise70: DataFrame with review_id, nct_id, [isrctn_id] columns.
        cdsr_strings: dict {review_id: list[str]} of study-list strings.

    Returns:
        dict with keys:
          in_cochrane (bool, the union),
          matched_via_nct (bool),
          matched_via_isrctn (bool),
          matched_via_cdsr_string (bool),
          ensemble_disagree (bool — at least one component disagrees with another),
          review_ids (sorted list of all matched review IDs across components).
    """
    p70 = _normalise_pairwise70(pairwise70)
    nct = row.get("nct_id", "") or ""
    isrctn = row.get("isrctn_id", "") or ""
    title = row.get("brief_title", "") or ""

    via_nct, rids_nct = _nct_bridge_match(nct, p70)
    via_isrctn, rids_isrctn = _isrctn_bridge_match(isrctn, p70)
    via_cdsr, rids_cdsr = _cdsr_string_match(title, cdsr_strings)

    in_cochrane = via_nct or via_isrctn or via_cdsr
    components = (via_nct, via_isrctn, via_cdsr)
    # Ensemble disagrees if at least one component is True AND at least one is False
    # AND the False one had data to work with (non-empty input field).
    runnable = (
        bool(nct),
        bool(isrctn),
        bool(title and len(title.strip()) >= 5),
    )
    runnable_results = [r for r, run in zip(components, runnable) if run]
    ensemble_disagree = (
        any(runnable_results) and not all(runnable_results)
    ) if len(runnable_results) >= 2 else False

    all_review_ids = sorted(set(rids_nct + rids_isrctn + rids_cdsr))

    return {
        "in_cochrane": in_cochrane,
        "matched_via_nct": via_nct,
        "matched_via_isrctn": via_isrctn,
        "matched_via_cdsr_string": via_cdsr,
        "ensemble_disagree": ensemble_disagree,
        "review_ids": all_review_ids,
    }
