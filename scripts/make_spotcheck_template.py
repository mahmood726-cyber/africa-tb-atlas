"""Generate a 30-trial BLINDED spot-check sample from trials.parquet.

Per spec §4.4: stratified sampling, seed=20260507, 10 africa-recruiting +
20 non-Africa. Auditor receives this CSV with NO algorithm verdicts.

Usage:
    python scripts/make_spotcheck_template.py \\
        --trials data/output/trials.parquet \\
        --out data/processed/spotcheck_v0.1.0_blinded.csv
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_SEED = 20260507
DEFAULT_N_AFRICA = 10
DEFAULT_N_NON_AFRICA = 20

# Columns the auditor sees (no algorithm verdicts):
BLINDED_COLUMNS = [
    "trial_id", "nct_id", "isrctn_id", "brief_title",
    "lead_sponsor", "africa_recruiting", "drug_class",
]


def _trial_id(row) -> str:
    """Stable identifier: NCT > ISRCTN > EUCTR > title-hash."""
    for k in ("nct_id", "isrctn_id", "euctr_id"):
        v = row.get(k, "")
        if v:
            return str(v)
    return f"title:{str(row.get('brief_title', ''))[:40]}"


def make_template(
    trials: pd.DataFrame,
    *,
    seed: int = DEFAULT_SEED,
    n_africa: int = DEFAULT_N_AFRICA,
    n_non_africa: int = DEFAULT_N_NON_AFRICA,
) -> pd.DataFrame:
    """Stratified sample of trials DataFrame.

    Returns a DataFrame with BLINDED_COLUMNS only — no algorithm verdicts.
    Each row has a stable ``trial_id`` for joining with auditor output.
    """
    if "africa_recruiting" not in trials.columns:
        raise ValueError("trials must have africa_recruiting column")

    africa = trials[trials["africa_recruiting"].astype(bool)]
    non_africa = trials[~trials["africa_recruiting"].astype(bool)]

    n_a = min(n_africa, len(africa))
    n_na = min(n_non_africa, len(non_africa))

    sampled_africa = africa.sample(n=n_a, random_state=seed)
    sampled_non_africa = non_africa.sample(n=n_na, random_state=seed + 1)

    sample = pd.concat([sampled_africa, sampled_non_africa], ignore_index=True)
    sample = sample.copy()

    # Build trial_id from the stable identifier logic
    sample["trial_id"] = sample.apply(_trial_id, axis=1)

    # Ensure all expected columns exist (fill defaults for optional registry IDs)
    for col in BLINDED_COLUMNS:
        if col not in sample.columns:
            sample[col] = ""

    return sample[BLINDED_COLUMNS].reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=Path, required=True,
                    help="Path to trials.parquet")
    ap.add_argument("--out", type=Path, required=True,
                    help="Output blinded CSV "
                         "(e.g., data/processed/spotcheck_v0.1.0_blinded.csv)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--n-africa", type=int, default=DEFAULT_N_AFRICA)
    ap.add_argument("--n-non-africa", type=int, default=DEFAULT_N_NON_AFRICA)
    args = ap.parse_args()

    if not args.trials.exists():
        print(f"FAIL: trials not found: {args.trials}", file=sys.stderr)
        return 1

    trials = pd.read_parquet(args.trials)
    sample = make_template(
        trials,
        seed=args.seed,
        n_africa=args.n_africa,
        n_non_africa=args.n_non_africa,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(args.out, index=False)

    n_africa_out = int(sample["africa_recruiting"].astype(bool).sum())
    n_non_africa_out = int((~sample["africa_recruiting"].astype(bool)).sum())
    print(f"OK: wrote {len(sample)} blinded rows to {args.out}")
    print(f"     columns: {list(sample.columns)}")
    print(f"     africa_recruiting True:  {n_africa_out}")
    print(f"     africa_recruiting False: {n_non_africa_out}")
    print()
    print("NEXT STEPS (for Task 32b blinded auditor subagent):")
    print(f"  1. Share {args.out} with the blinded subagent.")
    print("  2. Subagent fills auditor_g3 (True/False), auditor_evidence_url, auditor_notes.")
    print("  3. Save auditor output as data/processed/spotcheck_v0.1.0_auditor.csv.")
    print("  4. Run: python scripts/merge_spotcheck.py --blinded <this file> \\")
    print("              --auditor data/processed/spotcheck_v0.1.0_auditor.csv \\")
    print("              --trials <trials.parquet> \\")
    print("              --out data/processed/spotcheck_v0.1.0.csv")
    print("  5. Run: python scripts/validation_gates.py")
    print("  6. Threshold: >=27/30 G3-only agreement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
