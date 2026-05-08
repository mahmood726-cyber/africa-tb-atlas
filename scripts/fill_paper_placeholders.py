# sentinel:skip-file — this file defines {{...}} patterns as dict-key string
# literals that will later fill templates; they are intentional data, not
# unfilled template tokens (P1-unpopulated-placeholder false-positive).
"""Fill {{PLACEHOLDERS}} in a Markdown template using atlas.csv values.

Usage:
    python scripts/fill_paper_placeholders.py \\
        --template e156-submission/body.template.md \\
        --atlas tests/fixtures/atlas_baseline_micro.csv \\
        --out e156-submission/body.md

    python scripts/fill_paper_placeholders.py \\
        --template e156-submission/synthesis-methods-note.md \\
        --atlas data/processed/atlas.csv \\
        --snapshot-meta data/snapshots/aact_metadata.json \\
        --spotcheck data/processed/spotcheck_v0.1.0.csv \\
        --out e156-submission/synthesis-methods-note.filled.md
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd


def _row(atlas: pd.DataFrame, sensitivity: str, stratum_value) -> dict:
    sub = atlas[
        (atlas["sensitivity"] == sensitivity)
        & (atlas["stratum_value"].astype(str).str.lower()
           == str(stratum_value).lower())
    ]
    if sub.empty:
        return {}
    return sub.iloc[0].to_dict()


def _format_pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    return f"{x * 100:.1f}"


def _format_int(x) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "—"
    try:
        return f"{int(x):,}"
    except (TypeError, ValueError):
        return "—"


def _build_placeholders(
    atlas: pd.DataFrame,
    snapshot_meta: dict | None = None,
    spotcheck: dict | None = None,
) -> dict[str, str]:
    binary = atlas[atlas["sensitivity"] == "binary_1site"]
    africa = _row(atlas, "binary_1site", "True")
    non_africa = _row(atlas, "binary_1site", "False")
    site30_a = _row(atlas, "site_share_30pct", "True")
    site30_na = _row(atlas, "site_share_30pct", "False")

    drug = atlas[atlas["sensitivity"] == "drug_class"]
    bpal_drug = drug[drug["stratum_value"].isin(["BPaL", "BPaLM"])]
    n_bpal_bpalm = int(bpal_drug["n_trials"].sum()) if not bpal_drug.empty else 0

    # Weighted average of pct_g0_to_g3 for BPaL + BPaLM (weight = n_trials)
    if not bpal_drug.empty and bpal_drug["n_trials"].sum() > 0:
        pct_bpal_bpalm: float | None = (
            (bpal_drug["pct_g0_to_g3"] * bpal_drug["n_trials"]).sum()
            / bpal_drug["n_trials"].sum()
        )
    else:
        pct_bpal_bpalm = None

    p: dict[str, str] = {
        "{{N_TRIALS}}": _format_int(binary["n_trials"].sum()) if not binary.empty else "—",
        "{{N_AFRICA_RECRUITING}}": _format_int(africa.get("n_trials")),
        "{{N_NON_AFRICA}}": _format_int(non_africa.get("n_trials")),
        "{{PCT_G3_AFRICA}}": _format_pct(africa.get("pct_g0_to_g3")),
        "{{PCT_G3_NON_AFRICA}}": _format_pct(non_africa.get("pct_g0_to_g3")),
        "{{PCT_G3_PAT_AFRICA}}": _format_pct(africa.get("pct_g0_to_g3_pat")),
        "{{PCT_G3_PAT_NON_AFRICA}}": _format_pct(non_africa.get("pct_g0_to_g3_pat")),
        "{{N_PARTICIPANTS_AFRICA}}": _format_int(africa.get("n_participants")),
        "{{N_BPAL_BPALM}}": _format_int(n_bpal_bpalm),
        "{{PCT_G3_BPAL_BPALM}}": _format_pct(pct_bpal_bpalm),
        "{{SITE_SHARE_30PCT_AFRICA_PCT}}": _format_pct(site30_a.get("pct_g0_to_g3")),
        "{{SITE_SHARE_30PCT_NON_AFRICA_PCT}}": _format_pct(site30_na.get("pct_g0_to_g3")),
        "{{SNAPSHOT_DATE}}": (snapshot_meta or {}).get("snapshot_date", "{{SNAPSHOT_DATE}}"),
        "{{SPOTCHECK_AGREE_N}}": str((spotcheck or {}).get("agree_n", "{{SPOTCHECK_AGREE_N}}")),
        "{{SPOTCHECK_TOTAL}}": str((spotcheck or {}).get("total", "{{SPOTCHECK_TOTAL}}")),
    }
    return p


def fill_template(
    template_path: Path,
    atlas_csv: Path,
    snapshot_meta_path: Path | None = None,
    spotcheck_path: Path | None = None,
) -> str:
    atlas = pd.read_csv(atlas_csv)
    snapshot_meta = (
        json.loads(snapshot_meta_path.read_text(encoding="utf-8"))
        if snapshot_meta_path and snapshot_meta_path.exists()
        else None
    )
    spotcheck = (
        json.loads(spotcheck_path.read_text(encoding="utf-8"))
        if spotcheck_path and spotcheck_path.exists()
        else None
    )
    placeholders = _build_placeholders(atlas, snapshot_meta, spotcheck)
    text = template_path.read_text(encoding="utf-8")
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--atlas", type=Path, required=True)
    ap.add_argument("--snapshot-meta", type=Path, default=None)
    ap.add_argument("--spotcheck", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if not args.template.exists():
        print(f"FAIL: template not found: {args.template}", file=sys.stderr)
        return 1
    if not args.atlas.exists():
        print(f"FAIL: atlas not found: {args.atlas}", file=sys.stderr)
        return 1

    text = fill_template(
        args.template, args.atlas, args.snapshot_meta, args.spotcheck
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")

    # Report any unresolved placeholders
    unresolved = re.findall(r"\{\{[A-Z0-9_]+\}\}", text)
    if unresolved:
        print(
            f"WARN: unresolved placeholders: {sorted(set(unresolved))}",
            file=sys.stderr,
        )
        return 0
    print(f"OK: filled {args.template} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
