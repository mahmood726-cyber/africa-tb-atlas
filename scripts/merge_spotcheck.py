"""Merge blinded sample + auditor verdicts + algorithm verdicts.

Inputs:
  --blinded   CSV from make_spotcheck_template (no algorithm verdicts)
  --auditor   CSV from blinded subagent; required cols: trial_id, auditor_g3
              optional: auditor_evidence_url, auditor_notes
  --trials    trials.parquet (algorithm output; provides in_cochrane verdict)

Output:
  Merged CSV with columns:
      trial_id, nct_id, isrctn_id, brief_title, lead_sponsor,
      africa_recruiting, drug_class,
      auditor_g3, [auditor_evidence_url], [auditor_notes],
      algorithm_g3, agree_g3

Usage:
    python scripts/merge_spotcheck.py \\
        --blinded data/processed/spotcheck_v0.1.0_blinded.csv \\
        --auditor data/processed/spotcheck_v0.1.0_auditor.csv \\
        --trials  data/output/trials.parquet \\
        --out     data/processed/spotcheck_v0.1.0.csv
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd


def _trial_id(row) -> str:
    """Same stable identifier logic as make_spotcheck_template."""
    for k in ("nct_id", "isrctn_id", "euctr_id"):
        v = row.get(k, "")
        if v:
            return str(v)
    return f"title:{str(row.get('brief_title', ''))[:40]}"


def merge(
    blinded: pd.DataFrame,
    auditor: pd.DataFrame,
    trials: pd.DataFrame,
) -> pd.DataFrame:
    """Join the three inputs on trial_id and compute agree_g3."""
    # Validate auditor columns
    required_auditor_cols = {"trial_id", "auditor_g3"}
    if not required_auditor_cols.issubset(auditor.columns):
        missing = required_auditor_cols - set(auditor.columns)
        raise ValueError(f"auditor CSV missing columns: {missing}")

    # Compute trial_id on trials the same way make_spotcheck_template does
    trials = trials.copy()
    trials["trial_id"] = trials.apply(_trial_id, axis=1)

    # Resolve algorithm G3 column (in_cochrane or algorithm_g3)
    if "in_cochrane" in trials.columns:
        trials["algorithm_g3"] = trials["in_cochrane"].astype(bool)
    elif "algorithm_g3" in trials.columns:
        trials["algorithm_g3"] = trials["algorithm_g3"].astype(bool)
    else:
        raise ValueError(
            "trials.parquet missing in_cochrane / algorithm_g3 column"
        )

    # Collect optional auditor columns
    optional_auditor_cols = [
        c for c in ("auditor_evidence_url", "auditor_notes")
        if c in auditor.columns
    ]
    auditor_keep = ["trial_id", "auditor_g3"] + optional_auditor_cols

    # Join blinded + auditor
    merged = blinded.merge(
        auditor[auditor_keep],
        on="trial_id",
        how="left",
    )
    # Join with algorithm verdicts
    merged = merged.merge(
        trials[["trial_id", "algorithm_g3"]],
        on="trial_id",
        how="left",
    )

    # Coerce booleans for comparison
    def _coerce(s: pd.Series) -> pd.Series:
        return s.astype(str).str.lower().isin(["true", "1", "1.0", "yes"])

    merged["_aud_bool"] = _coerce(merged["auditor_g3"])
    merged["_alg_bool"] = _coerce(merged["algorithm_g3"])
    merged["agree_g3"] = merged["_aud_bool"] == merged["_alg_bool"]
    merged = merged.drop(columns=["_aud_bool", "_alg_bool"])

    return merged.reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blinded", type=Path, required=True,
                    help="Blinded CSV from make_spotcheck_template")
    ap.add_argument("--auditor", type=Path, required=True,
                    help="Auditor CSV (trial_id + auditor_g3 required)")
    ap.add_argument("--trials", type=Path, required=True,
                    help="trials.parquet with algorithm in_cochrane column")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output merged CSV for validation_gates --spotcheck")
    args = ap.parse_args()

    for p, label in [
        (args.blinded, "blinded"),
        (args.auditor, "auditor"),
        (args.trials, "trials"),
    ]:
        if not p.exists():
            print(f"FAIL: {label} input not found: {p}", file=sys.stderr)
            return 1

    blinded = pd.read_csv(args.blinded)
    auditor = pd.read_csv(args.auditor)
    trials = pd.read_parquet(args.trials)

    merged = merge(blinded, auditor, trials)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.out, index=False)

    n_agree = int(merged["agree_g3"].sum())
    n_total = len(merged)
    pct = 100 * n_agree / n_total if n_total else 0
    print(f"OK: merged {n_total} rows to {args.out}")
    print(f"     G3 agreement: {n_agree}/{n_total} ({pct:.0f}%) "
          f"— threshold for v0.1.0 release: >=27/30 (90%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
