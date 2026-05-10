"""End-to-end orchestrator. Composes Phase A → B → C → D → E.

CLI:
  python -m pilots.run_all --paths-toml paths.toml --out-dir data/output/
  python -m pilots.run_all --paths-toml tests/fixtures/paths_micro.toml \
      --out-dir /tmp/out --micro --no-network

Outputs:
  <out_dir>/trials.parquet      — one row per trial after Phases A-D
  <out_dir>/atlas.csv            — aggregated by stratification (3× sensitivities)
  <out_dir>/denominator_audit.csv — Phase B drop reasons
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from tb_atlas.config import load_paths
from tb_atlas.aact_loader import load_aact
from tb_atlas.ictrp_loader import load_ictrp
from tb_atlas.population_pipeline import build_denominator
from tb_atlas.africa_classifier import classify_africa
from tb_atlas.drug_class_taxonomy import classify_regimen
from tb_atlas.results_posting import has_results_posted
from tb_atlas.publication_match import (
    lookup_publication, lookup_publication_by_isrctn,
)
from tb_atlas.cochrane_match import match_trial
from tb_atlas.funnel import compute_funnel


def _ensure_source_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure dedup-required ID columns exist (empty string when absent)."""
    df = df.copy()
    for col in ("nct_id", "isrctn_id", "euctr_id"):
        if col not in df.columns:
            df[col] = ""
    return df


def _load_cdsr_strings(cdsr_path: Path) -> dict:
    """Build {review_id: list[body_text]} from sqlite (table review_strings)."""
    out: dict[str, list[str]] = {}
    conn = sqlite3.connect(cdsr_path)
    try:
        for table in ("review_strings", "review_study_strings"):
            try:
                cur = conn.execute(f"SELECT review_id, body_text FROM {table}")
                break
            except sqlite3.OperationalError:
                continue
        else:
            raise RuntimeError(f"CDSR sqlite at {cdsr_path} has no expected table")
        for review_id, body_text in cur.fetchall():
            out.setdefault(review_id, []).append(body_text)
    finally:
        conn.close()
    return out


def _g2_publication(row, cache_dir: Path, no_network: bool) -> bool:
    """Phase D gate 2: publication via Europe PMC NCT-bridge OR ISRCTN-direct."""
    if no_network:
        return False  # mock for fixture-mode tests
    nct = row.get("nct_id", "") or ""
    isrctn = row.get("isrctn_id", "") or ""
    if nct:
        v = lookup_publication(nct, cache_dir)
        if v.published:
            return True
    if isrctn:
        v = lookup_publication_by_isrctn(isrctn, cache_dir)
        if v.published:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths-toml", default="paths.toml", type=Path)
    ap.add_argument("--out-dir", default="data/output", type=Path)
    ap.add_argument("--micro", action="store_true")
    ap.add_argument("--no-network", action="store_true",
                    help="Skip Europe PMC HTTP calls (tests).")
    ap.add_argument("--n-bootstrap", type=int, default=1000)
    ap.add_argument("--skip-ictrp", action="store_true",
                    help="Skip ICTRP load entirely (AACT-only). Use when the "
                         "ICTRP snapshot lacks required columns (e.g., the "
                         "PACTR-scoped subset which omits Public title, "
                         "Intervention, Target_size).")
    args = ap.parse_args()

    if not args.paths_toml.exists():
        print(f"FAIL: paths.toml not found: {args.paths_toml}", file=sys.stderr)
        return 1

    paths = load_paths(args.paths_toml)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Phase A: ingest
    print("[A] loading AACT…", flush=True)
    aact = load_aact(paths.aact_snapshot_dir)
    print(f"[A] AACT loaded: {len(aact)} trials")

    if args.skip_ictrp:
        print("[A] ICTRP load: SKIPPED (--skip-ictrp); AACT-only pipeline.", flush=True)
        ictrp = pd.DataFrame(columns=aact.columns)
    else:
        print("[A] loading ICTRP…", flush=True)
        try:
            ictrp = load_ictrp(paths.ictrp_snapshot)
            print(f"[A] ICTRP loaded: {len(ictrp)} trials")
        except Exception as e:
            print(f"[A] ICTRP load FAILED: {e}", file=sys.stderr)
            print(f"[A] ICTRP load: degraded to AACT-only mode.", file=sys.stderr)
            ictrp = pd.DataFrame(columns=aact.columns)

    # ---- Phase B: filter + dedup
    print("[B] building denominator…", flush=True)
    aact = _ensure_source_columns(aact)
    ictrp = _ensure_source_columns(ictrp)
    denom, audit = build_denominator(aact, ictrp)
    print(f"[B] denominator: {len(denom)} trials")
    audit.to_csv(args.out_dir / "denominator_audit.csv", index=False)

    if denom.empty:
        print("WARN: empty denominator; writing empty atlas.csv and exiting")
        pd.DataFrame().to_csv(args.out_dir / "atlas.csv", index=False)
        return 0

    # ---- Phase C: classify
    print("[C] classifying Africa + drug-class…", flush=True)
    afri_df = denom["countries"].apply(classify_africa).apply(pd.Series)
    denom = pd.concat([denom.reset_index(drop=True), afri_df.reset_index(drop=True)], axis=1)
    denom["drug_class"] = denom["interventions"].apply(lambda x: classify_regimen(x).value)

    # ---- Phase D gates
    print("[D] G1: results posting…", flush=True)
    denom["has_results_posted"] = denom.apply(has_results_posted, axis=1)

    print("[D] G2: publication match…", flush=True)
    denom["has_publication"] = denom.apply(
        lambda r: _g2_publication(r, paths.europe_pmc_cache_dir, args.no_network),
        axis=1,
    )

    print("[D] G3: Cochrane match…", flush=True)
    pairwise70 = pd.read_parquet(paths.pairwise70_index)
    # v0.2 supplement: TB-specific Cochrane reference index built via Playwright
    # scrape of cochranelibrary.com. Merged with Pairwise70 at runtime so the
    # atlas can match modern MDR-TB trials against TB-relevant Cochrane reviews
    # that aren't in Pairwise70's curated 374-review subset.
    tb_refs_path = Path("data/cochrane_tb_refs.parquet")
    if tb_refs_path.exists():
        tb_refs = pd.read_parquet(tb_refs_path)
        n_before = len(pairwise70)
        pairwise70 = pd.concat([pairwise70, tb_refs], ignore_index=True)
        print(f"[D]   merged TB-Cochrane supplement: +{len(tb_refs)} rows "
              f"({pairwise70.review_id.nunique()} distinct reviews; "
              f"{n_before} -> {len(pairwise70)})")
    cdsr_strings = _load_cdsr_strings(paths.cdsr_string_index)

    g3_dicts = denom.apply(
        lambda r: match_trial(r, pairwise70, cdsr_strings), axis=1
    ).tolist()
    g3_df = pd.DataFrame(g3_dicts)
    # Coerce list-column review_ids to semicolon-joined string for stable CSV/parquet schema
    if "review_ids" in g3_df.columns:
        g3_df["review_ids"] = g3_df["review_ids"].apply(
            lambda x: ";".join(x) if isinstance(x, list) else ""
        )
    denom = pd.concat([denom.reset_index(drop=True), g3_df.reset_index(drop=True)], axis=1)

    # ---- Save trials.parquet (master per-trial output)
    trials_path = args.out_dir / "trials.parquet"
    # Coerce list-columns to strings before writing parquet so the schema is stable
    # and easy to diff across runs.
    df_for_parquet = denom.copy()
    for col in ("interventions", "countries", "conditions"):
        if col in df_for_parquet.columns:
            df_for_parquet[col] = df_for_parquet[col].apply(
                lambda x: ";".join(map(str, x)) if isinstance(x, list) else str(x)
            )
    df_for_parquet.to_parquet(trials_path, index=False)
    print(f"[E] wrote {trials_path}")

    # ---- Phase E: aggregate by 3 stratifications + drug-class
    print("[E] computing atlas…", flush=True)
    atlas_blocks = []
    for stratifier, label in [
        ("africa_recruiting", "binary_1site"),
        ("site_share_30pct", "site_share_30pct"),
        ("africa_tier", "three_tier"),
        ("drug_class", "drug_class"),
    ]:
        if stratifier not in denom.columns:
            continue
        rows = compute_funnel(
            denom, stratify_by=stratifier, n_bootstrap=args.n_bootstrap,
        )
        rows = rows.copy()
        rows["sensitivity"] = label
        # Normalise the stratum column name for consistency in atlas.csv
        rows = rows.rename(columns={stratifier: "stratum_value"})
        rows["stratum_key"] = stratifier
        atlas_blocks.append(rows)

    atlas = pd.concat(atlas_blocks, ignore_index=True)
    # Reorder columns: stratum first, sensitivity second, then the metric block
    front_cols = ["sensitivity", "stratum_key", "stratum_value"]
    other_cols = [c for c in atlas.columns if c not in front_cols]
    atlas = atlas[front_cols + other_cols]

    atlas_path = args.out_dir / "atlas.csv"
    atlas.to_csv(atlas_path, index=False)
    print(f"[E] wrote {atlas_path}: {len(atlas)} rows")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
