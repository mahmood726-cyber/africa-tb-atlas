"""Preflight: fail-closed gate that runs before any extraction.

Verifies:
- paths.toml resolves all required keys
- Each external snapshot exists
- AACT has the expected pipe-delim tables
- Pairwise70 parquet has >= 1 row (full snapshot has >= 1000)
- CDSR sqlite has >= 1 review (full snapshot has >= 100)

Use --micro for fixture-mode (skips production thresholds).
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from tb_atlas.config import load_paths
from tb_atlas.aact_loader import REQUIRED_TABLES


def _check_aact(aact_dir: Path) -> tuple[bool, str]:
    if not aact_dir.exists():
        return False, f"aact_snapshot_dir missing: {aact_dir}"
    for tbl in REQUIRED_TABLES:
        p = aact_dir / f"{tbl}.txt"
        if not p.exists():
            return False, f"AACT table missing: {p}"
    return True, ""


def _check_ictrp(ictrp_path: Path) -> tuple[bool, str]:
    if not ictrp_path.exists():
        return False, f"ictrp_snapshot missing: {ictrp_path}"
    return True, ""


def _check_pairwise70(p70_path: Path, threshold: int) -> tuple[bool, str]:
    if not p70_path.exists():
        return False, f"pairwise70_index missing: {p70_path}"
    df = pd.read_parquet(p70_path)
    if len(df) < threshold:
        return False, f"pairwise70 has {len(df)} rows; expected >={threshold}"
    return True, ""


def _check_cdsr(cdsr_path: Path, threshold: int) -> tuple[bool, str]:
    if not cdsr_path.exists():
        return False, f"cdsr_string_index missing: {cdsr_path}"
    conn = sqlite3.connect(cdsr_path)
    try:
        # Probe the schema for a review-id column. Try common table names.
        n = None
        for table_name in ("review_strings", "review_study_strings"):
            try:
                cur = conn.execute(
                    f"SELECT COUNT(DISTINCT review_id) FROM {table_name}"
                )
                n = cur.fetchone()[0]
                break
            except sqlite3.OperationalError:
                continue

        if n is None:
            return (
                False,
                f"cdsr sqlite at {cdsr_path} has no review_strings or "
                f"review_study_strings table",
            )
    finally:
        conn.close()

    if n < threshold:
        return False, f"cdsr has {n} reviews; expected >={threshold}"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fail-closed preflight gate for africa-tb-atlas extraction."
    )
    ap.add_argument("--paths-toml", default="paths.toml", type=Path)
    ap.add_argument(
        "--micro",
        action="store_true",
        help="Allow micro-fixture sizes (skip production thresholds)",
    )
    args = ap.parse_args()

    if not args.paths_toml.exists():
        print(f"FAIL: paths.toml not found: {args.paths_toml}", file=sys.stderr)
        return 1

    try:
        paths = load_paths(args.paths_toml)
    except Exception as e:
        print(f"FAIL: paths.toml load: {e}", file=sys.stderr)
        return 1

    p70_threshold = 1 if args.micro else 1000
    cdsr_threshold = 1 if args.micro else 100

    checks = [
        ("AACT", _check_aact(paths.aact_snapshot_dir)),
        ("ICTRP", _check_ictrp(paths.ictrp_snapshot)),
        ("Pairwise70", _check_pairwise70(paths.pairwise70_index, p70_threshold)),
        ("CDSR", _check_cdsr(paths.cdsr_string_index, cdsr_threshold)),
    ]

    failures = [(name, msg) for name, (ok, msg) in checks if not ok]
    if failures:
        for name, msg in failures:
            print(f"FAIL [{name}]: {msg}", file=sys.stderr)
        return 1

    # Cache dir is created on demand (not a fail condition).
    paths.europe_pmc_cache_dir.mkdir(parents=True, exist_ok=True)

    print("OK: preflight passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
