"""Dedup AACT and ICTRP trial DataFrames by ID priority NCT > ISRCTN > EUCTR.

When a trial appears in both sources, AACT wins (more comprehensive metadata).
Logs every dedup decision to a returned DataFrame for audit (saved to
data/processed/dedup_log.csv by the orchestrator).

If the same trial has secondary IDs that map two records to incompatible
primaries (e.g., AACT NCT01 has ISRCTN01 but ICTRP has the SAME ISRCTN01
mapped to a DIFFERENT NCT99) — that is a data-integrity error, not a normal
case — raise DedupConflictError. Manual reconciliation required.
"""
from __future__ import annotations
import pandas as pd


class DedupConflictError(Exception):
    """Raised when secondary IDs map two records to incompatible primaries."""


_ID_PRIORITY = ("nct_id", "isrctn_id", "euctr_id")


def _build_id_index(df: pd.DataFrame) -> dict:
    """Build {(id_kind, id_value) -> row_index} for O(1) lookups across all 3 ID kinds."""
    idx = {}
    for i, r in df.iterrows():
        for kind in _ID_PRIORITY:
            v = r.get(kind, "")
            if v:
                idx[(kind, v)] = i
    return idx


def dedup_trials(aact: pd.DataFrame, ictrp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Dedup AACT∪ICTRP. AACT rows always kept; ICTRP rows kept only if no
    matching AACT row.

    Returns:
        (deduped_df, dedup_log_df)

    Conflict semantics:
        If ICTRP row R has nct_id="A" and isrctn_id="B"; AACT has row with
        nct_id="A" and isrctn_id="C" (i.e. same NCT but different ISRCTN),
        raise DedupConflictError. The dedup cannot pick a winner without
        manual review.
    """
    aact = aact.copy()
    ictrp = ictrp.copy()
    if "source" not in aact.columns:
        aact["source"] = "aact"
    if "source" not in ictrp.columns:
        ictrp["source"] = "ictrp"

    aact_idx = _build_id_index(aact)
    log_rows = []
    drop_ictrp = set()

    for j, r in ictrp.iterrows():
        match = None
        for kind in _ID_PRIORITY:
            v = r.get(kind, "")
            if v and (kind, v) in aact_idx:
                match = (kind, v, aact_idx[(kind, v)])
                break

        if match is None:
            log_rows.append({
                "trial_id": (r.get("nct_id") or r.get("isrctn_id") or r.get("euctr_id")),
                "decision": "kept_ictrp_only",
                "via": "",
            })
            continue

        kind, v, ai = match
        # Conflict check: do any of AACT row's other IDs disagree with ICTRP row's other IDs?
        for other in _ID_PRIORITY:
            if other == kind:
                continue
            av = aact.iloc[ai].get(other, "")
            iv = r.get(other, "")
            if av and iv and av != iv:
                raise DedupConflictError(
                    f"ID conflict: AACT row {ai} {kind}={v} has {other}={av} "
                    f"but ICTRP row {j} same {kind}={v} has {other}={iv}"
                )

        log_rows.append({
            "trial_id": v,
            "decision": f"merged_{kind.replace('_id', '')}",
            "via": kind,
        })
        drop_ictrp.add(j)

    out = pd.concat([aact, ictrp.drop(index=drop_ictrp)], ignore_index=True)
    log = pd.DataFrame(log_rows)
    return out, log
