"""Phase B: compose intervention/condition/date/population filters + dedup
to produce the trial denominator.

Returns (denominator_df, audit_df). The audit_df has columns
{source, trial_id, included, reason} and records every row's verdict.
"""
from __future__ import annotations
import pandas as pd

from .intervention_filter import contains_target_drug
from .condition_filter import is_drug_resistant_tb
from .date_filter import is_modern_era
from .population_filter import is_adult_or_adolescent
from .trial_dedup import dedup_trials


def _filter_one_source(df: pd.DataFrame, source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    audit_rows = []
    keep = []
    for i, r in df.iterrows():
        trial_id = r.get("nct_id") or r.get("isrctn_id") or r.get("euctr_id") or ""

        if not contains_target_drug(r["interventions"]):
            audit_rows.append({"source": source, "trial_id": trial_id,
                               "included": False, "reason": "no_target_drug"})
            continue

        # Per spec §1.6 #3: include MDR/pre-XDR/XDR/RR-TB trials, AND
        # DS-TB trials whose regimen contains a target drug. The intervention
        # filter has already passed, so DS-TB is ALSO included at this point.
        # We enforce condition matching only as a sanity check: trials with
        # condition unrelated to TB (e.g., HIV-only) should be dropped.
        # However, brief_title may also signal TB; for v0.1.0 we keep this
        # gate permissive — if condition list includes TB-like or any
        # tuberculosis term, allow; if condition is non-TB AND DR-TB rules
        # don't match, drop with reason 'wrong_condition'.
        cond_text = " | ".join(str(c) for c in (r.get("conditions") or [])).lower()
        is_dr = is_drug_resistant_tb(r["conditions"])
        is_any_tb = "tuberculos" in cond_text or r"\btb\b" in cond_text
        if not (is_dr or is_any_tb):
            audit_rows.append({"source": source, "trial_id": trial_id,
                               "included": False, "reason": "wrong_condition"})
            continue

        if not is_modern_era(r["start_date"]):
            audit_rows.append({"source": source, "trial_id": trial_id,
                               "included": False, "reason": "pre_2012"})
            continue

        if not is_adult_or_adolescent(r["brief_title"]):
            audit_rows.append({"source": source, "trial_id": trial_id,
                               "included": False, "reason": "pediatric"})
            continue

        keep.append(i)
        audit_rows.append({"source": source, "trial_id": trial_id,
                           "included": True, "reason": ""})

    return df.loc[keep].copy(), pd.DataFrame(audit_rows)


def build_denominator(aact: pd.DataFrame, ictrp: pd.DataFrame
                      ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Phase B chain: filter both sources, then dedup AACT∪ICTRP.

    Returns (denominator_df, audit_df).

    audit_df columns: source ∈ {aact, ictrp, dedup}, trial_id, included, reason.
    The 'dedup' rows record decisions from trial_dedup (merged_nct, etc).
    """
    aact_kept, aact_audit = _filter_one_source(aact, "aact")
    ictrp_kept, ictrp_audit = _filter_one_source(ictrp, "ictrp")

    # AACT may not have nct_id/isrctn_id/euctr_id columns yet (it does only
    # have nct_id from aact_loader). Add isrctn_id and euctr_id as empty for
    # dedup compatibility.
    if "isrctn_id" not in aact_kept.columns:
        aact_kept = aact_kept.assign(isrctn_id="")
    if "euctr_id" not in aact_kept.columns:
        aact_kept = aact_kept.assign(euctr_id="")

    denom, dedup_log = dedup_trials(aact_kept, ictrp_kept)

    # Convert dedup_log to audit shape.
    # For ICTRP rows with no extractable IDs (e.g. ChiCTR trials), dedup_log
    # records an empty trial_id. Fall back to brief_title so the audit row is
    # identifiable and the invariant (trial_id != "") is preserved.
    if len(dedup_log) > 0:
        dedup_audit = dedup_log.copy()
        # Fill empty trial_id from the denominator's brief_title (ICTRP-only rows)
        # by matching on position: dedup_log rows are in the same order as the
        # ICTRP rows that survived filtering.
        if "" in dedup_audit["trial_id"].values:
            ictrp_only_titles = (
                ictrp_kept
                .reset_index(drop=True)["brief_title"]
                .tolist()
            )
            new_ids = []
            ictrp_idx = 0
            for tid in dedup_audit["trial_id"]:
                if tid == "" and ictrp_idx < len(ictrp_only_titles):
                    new_ids.append(ictrp_only_titles[ictrp_idx])
                else:
                    new_ids.append(tid)
                ictrp_idx += 1
            dedup_audit["trial_id"] = new_ids

        dedup_audit = dedup_audit.assign(source="dedup", included=True, reason="")
        dedup_audit = dedup_audit[["source", "trial_id", "included", "reason"]]
    else:
        dedup_audit = pd.DataFrame(columns=["source", "trial_id", "included", "reason"])

    audit = pd.concat([aact_audit, ictrp_audit, dedup_audit], ignore_index=True)
    return denom, audit
