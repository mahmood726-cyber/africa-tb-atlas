"""Funnel aggregator: per-stratum gate counts + clustered bootstrap CI.

Per spec §1.5 + §1.6 #11:
  - Stratify by `stratify_by` column (africa_recruiting, site_share_30pct,
    africa_tier, or drug_class).
  - For each stratum, count n_trials and sum n_participants (enrollment)
    across each gate (G0 registered, G1 results-posted, G2 peer-published,
    G3 in-Cochrane).
  - Cluster bootstrap CI on G0→G3 rate; cluster = lead_sponsor; undefined
    if k < 3 distinct clusters in the stratum.
  - Patient-weighted twin: pct_g0_to_g3_pat = sum(n_participants where in_cochrane)
    / sum(n_participants in denominator).
  - Trials with null enrollment are dropped from the patient-weighted denominator
    but kept in the trial-weighted denominator (logged behaviour per spec §1.6 #18).
"""
from __future__ import annotations
import numpy as np
import pandas as pd


class EmptyFunnelInput(ValueError):
    pass


def clustered_bootstrap_ci(
    df: pd.DataFrame, value_col: str, cluster_col: str, *,
    n_boot: int = 1000, seed: int = 20260507, alpha: float = 0.05,
) -> tuple[float | None, float | None]:
    """Cluster bootstrap CI on the mean of value_col, clustered by cluster_col.

    Returns (lo, hi) or (None, None) if k < 3 distinct clusters.
    """
    if df.empty:
        return None, None
    clusters = df[cluster_col].dropna().unique()
    if len(clusters) < 3:
        return None, None
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n_boot):
        picked = rng.choice(clusters, size=len(clusters), replace=True)
        sub = pd.concat([df[df[cluster_col] == c] for c in picked])
        if sub.empty:
            continue
        samples.append(sub[value_col].astype(float).mean())
    if not samples:
        return None, None
    arr = np.array(samples)
    lo = float(np.quantile(arr, alpha / 2))
    hi = float(np.quantile(arr, 1 - alpha / 2))
    return lo, hi


def compute_funnel(
    df: pd.DataFrame, *, stratify_by: str = "africa_recruiting",
    n_bootstrap: int = 1000,
) -> pd.DataFrame:
    """Compute per-stratum funnel from a per-trial DataFrame.

    Required input columns:
      - stratify_by (the stratification key)
      - lead_sponsor (cluster column)
      - enrollment (numeric, may be null)
      - has_results_posted, has_publication, in_cochrane (bool gate flags)

    Returns DataFrame with one row per stratum, columns:
      - <stratify_by>: stratum value
      - n_trials, n_results_posted, n_peer_published, n_in_cochrane
      - n_participants, n_participants_results_posted, n_participants_peer_published, n_participants_in_cochrane
      - pct_g0_to_g3 (trial-weighted), pct_g0_to_g3_pat (patient-weighted)
      - pct_g0_to_g3_ci_lo, pct_g0_to_g3_ci_hi (cluster bootstrap; None if k<3)
      - n_invisible: trials lacking BOTH NCT AND ISRCTN
    """
    if df.empty:
        raise EmptyFunnelInput("compute_funnel called on empty DataFrame")

    if stratify_by not in df.columns:
        raise KeyError(f"stratify_by column not in DataFrame: {stratify_by!r}")

    # Ensure required columns exist
    for col in ("lead_sponsor", "enrollment", "has_results_posted",
                "has_publication", "in_cochrane"):
        if col not in df.columns:
            raise KeyError(f"required column missing: {col!r}")

    # n_invisible: trials lacking BOTH NCT and ISRCTN. Defensive — these
    # columns may be absent (e.g., AACT-only data).
    nct_col = df.get("nct_id", pd.Series([""] * len(df), index=df.index))
    isrctn_col = df.get("isrctn_id", pd.Series([""] * len(df), index=df.index))
    df = df.copy()
    df["_invisible"] = (nct_col.fillna("") == "") & (isrctn_col.fillna("") == "")

    rows = []
    for stratum, sub in df.groupby(stratify_by, dropna=False):
        n_trials = len(sub)

        # Boolean gate counts
        n_g1 = int(sub["has_results_posted"].astype(bool).sum())
        n_g2 = int(sub["has_publication"].astype(bool).sum())
        n_g3 = int(sub["in_cochrane"].astype(bool).sum())
        n_inv = int(sub["_invisible"].astype(bool).sum())

        # Patient-weighted (drop null enrollment)
        sub_pat = sub[sub["enrollment"].notna()]
        n_part = int(sub_pat["enrollment"].sum()) if not sub_pat.empty else 0
        n_part_g1 = int(sub_pat[sub_pat["has_results_posted"].astype(bool)]["enrollment"].sum()) if not sub_pat.empty else 0
        n_part_g2 = int(sub_pat[sub_pat["has_publication"].astype(bool)]["enrollment"].sum()) if not sub_pat.empty else 0
        n_part_g3 = int(sub_pat[sub_pat["in_cochrane"].astype(bool)]["enrollment"].sum()) if not sub_pat.empty else 0

        pct = n_g3 / n_trials if n_trials else float("nan")
        pct_pat = n_part_g3 / n_part if n_part else float("nan")

        ci_lo, ci_hi = clustered_bootstrap_ci(
            sub.assign(_g3=sub["in_cochrane"].astype(int)),
            value_col="_g3",
            cluster_col="lead_sponsor",
            n_boot=n_bootstrap,
        )

        rows.append({
            stratify_by: stratum,
            "n_trials": n_trials,
            "n_results_posted": n_g1,
            "n_peer_published": n_g2,
            "n_in_cochrane": n_g3,
            "n_invisible": n_inv,
            "n_participants": n_part,
            "n_participants_results_posted": n_part_g1,
            "n_participants_peer_published": n_part_g2,
            "n_participants_in_cochrane": n_part_g3,
            "pct_g0_to_g3": pct,
            "pct_g0_to_g3_pat": pct_pat,
            "pct_g0_to_g3_ci_lo": ci_lo,
            "pct_g0_to_g3_ci_hi": ci_hi,
        })

    return pd.DataFrame(rows)
