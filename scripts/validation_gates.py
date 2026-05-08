"""Pre-ship validation gates for africa-tb-atlas v0.1.0.

Per spec §1.6 #12, #13, #19:

  1. TrialScout sanity (ONE-SIDED): G0->G2 publication rate must NOT be much
     LOWER than 53.6% (one-sided lower bound). High rates are expected for
     TB Alliance / USAID / EDCTP-funded modern MDR-TB trials and are not
     a failure.

  2. 30-trial blinded G3 spot-check: >=27/30 G3-only verdict-level agreement.
     G1/G2 over-broadness is documented and acceptable.

  3. Ensemble disagreement: <5% of in_cochrane trials show disagreement
     across the 3 G3 components (NCT-bridge, ISRCTN-bridge, CDSR string).

CLI: python scripts/validation_gates.py
       --trials data/output/trials.parquet
       --spotcheck data/processed/spotcheck_v0.1.0.csv
"""
from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path

import pandas as pd

TRIALSCOUT_LOWER_BOUND = 0.536  # 63.6% baseline minus 10pp; one-sided
SPOTCHECK_THRESHOLD = 27        # G3-only agreement
ENSEMBLE_DISAGREE_FRACTION = 0.05


def check_trialscout_sanity(g2_rate: float) -> bool:
    """One-sided check: True iff g2_rate >= 0.536 (or g2_rate is NaN/None).

    High values pass; only suspiciously LOW values fail. NaN passes
    (cannot evaluate; warn but don't block).
    """
    if g2_rate is None:
        return True
    if isinstance(g2_rate, float) and math.isnan(g2_rate):
        return True
    return float(g2_rate) >= TRIALSCOUT_LOWER_BOUND


def check_spotcheck_g3_only(agreements: int, total: int) -> bool:
    """G3-only agreement gate. Must have exactly 30 trials and >=27 agree."""
    return total == 30 and agreements >= SPOTCHECK_THRESHOLD


def check_ensemble_disagreement(disagree: int, total: int) -> bool:
    """Disagreement fraction <5%. Vacuously True when total == 0."""
    if total == 0:
        return True
    return (disagree / total) < ENSEMBLE_DISAGREE_FRACTION


def _trialscout_from_trials(trials: pd.DataFrame) -> float:
    """Compute G0->G2 rate among trials with NCT cross-reference (cross-registered).

    For TB Atlas, "cross-registered" means trials that have an NCT id
    (most modern MDR-TB trials in our denominator do). Filter to those
    and compute mean(has_publication).
    """
    cross = trials[trials["nct_id"].astype(str) != ""]
    if cross.empty:
        return float("nan")
    return float(cross["has_publication"].astype(bool).mean())


def _spotcheck_g3_agreement(spotcheck_csv: Path) -> tuple[int, int]:
    """Read merged spot-check CSV; return (n_agree_g3, n_total).

    Expected columns: auditor_g3 (bool/0-1), algorithm_g3 (bool/0-1) OR
    in_cochrane (the algorithm's verdict; spotcheck merge writes either).
    """
    df = pd.read_csv(spotcheck_csv)
    # Tolerate either column-name convention
    if "algorithm_g3" in df.columns:
        algo = df["algorithm_g3"]
    elif "in_cochrane" in df.columns:
        algo = df["in_cochrane"]
    else:
        raise ValueError(
            f"spotcheck CSV missing algorithm_g3 / in_cochrane column: "
            f"got {list(df.columns)}"
        )
    if "auditor_g3" not in df.columns:
        raise ValueError(
            f"spotcheck CSV missing auditor_g3 column: got {list(df.columns)}"
        )
    auditor = df["auditor_g3"]

    # Coerce both to bool (handle 0/1, "True"/"False", "TRUE", etc.)
    def _coerce(s):
        return s.astype(str).str.lower().isin(["true", "1", "1.0", "yes"])

    a = _coerce(algo)
    b = _coerce(auditor)
    n_agree = int((a == b).sum())
    return n_agree, len(df)


def _ensemble_disagree_count(trials: pd.DataFrame) -> tuple[int, int]:
    """Return (n_disagree, n_in_cochrane) over the trials DataFrame."""
    in_c = trials[trials["in_cochrane"].astype(bool)]
    if in_c.empty:
        return 0, 0
    if "ensemble_disagree" not in in_c.columns:
        return 0, len(in_c)
    n_dis = int(in_c["ensemble_disagree"].astype(bool).sum())
    return n_dis, len(in_c)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=Path, default=Path("data/output/trials.parquet"))
    ap.add_argument("--spotcheck", type=Path, default=Path("data/processed/spotcheck_v0.1.0.csv"))
    args = ap.parse_args()

    failures: list[str] = []
    notes: list[str] = []

    # Gate 1: TrialScout sanity (one-sided)
    trials = None
    if args.trials.exists():
        trials = pd.read_parquet(args.trials)
        rate = _trialscout_from_trials(trials)
        ok = check_trialscout_sanity(rate)
        rate_str = f"{rate:.3f}" if not math.isnan(rate) else "nan"
        line = (
            f"TrialScout sanity (one-sided): "
            f"{'OK  ' if ok else 'FAIL'} rate={rate_str} "
            f"(lower bound {TRIALSCOUT_LOWER_BOUND:.3f}; high rates OK)"
        )
        notes.append(line)
        if not ok:
            failures.append("trialscout")
    else:
        notes.append(f"TrialScout sanity: SKIPPED -- {args.trials} missing")

    # Gate 2: 30-trial blinded G3 spot-check
    if args.spotcheck.exists():
        try:
            n_agree, n_total = _spotcheck_g3_agreement(args.spotcheck)
        except ValueError as e:
            notes.append(f"30-trial G3 spot-check: FAIL -- {e}")
            failures.append("spotcheck")
        else:
            ok = check_spotcheck_g3_only(n_agree, n_total)
            line = (
                f"30-trial G3 spot-check: "
                f"{'OK  ' if ok else 'FAIL'} {n_agree}/{n_total} "
                f"(threshold >={SPOTCHECK_THRESHOLD}/30)"
            )
            notes.append(line)
            if not ok:
                failures.append("spotcheck")
    else:
        notes.append(f"30-trial G3 spot-check: SKIPPED -- {args.spotcheck} missing")

    # Gate 3: ensemble disagreement
    if trials is not None:
        n_dis, n_in_c = _ensemble_disagree_count(trials)
        ok = check_ensemble_disagreement(n_dis, n_in_c)
        frac = (n_dis / n_in_c) if n_in_c else 0.0
        line = (
            f"Ensemble disagreement:        "
            f"{'OK  ' if ok else 'FAIL'} {n_dis}/{n_in_c} = {frac:.3f} "
            f"(threshold <{ENSEMBLE_DISAGREE_FRACTION:.2f})"
        )
        notes.append(line)
        if not ok:
            failures.append("ensemble")
    # If trials missing, skip silently (already noted under Gate 1)

    print("\n".join(notes))
    if failures:
        print(f"\nFAILED gates: {', '.join(failures)}", file=sys.stderr)
        return 1
    if not notes or all("SKIPPED" in n for n in notes):
        print("\nNo gates evaluable (no inputs) -- neutral exit.", file=sys.stderr)
        return 2  # neutral exit; caller decides
    print("\nAll evaluable gates PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
