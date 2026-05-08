"""Build sha256-pinned metadata for each off-repo snapshot.

Run: python scripts/build_snapshot_metadata.py [--paths-toml paths.toml]
Writes one *_metadata.json per source under data/snapshots/.

Idempotent: re-running produces byte-identical JSON for unchanged snapshots.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional dependency: tomllib (stdlib ≥3.11) or tomli (third-party fallback)
# ---------------------------------------------------------------------------
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        tomllib = None  # fallback: parse manually below

CHUNK = 1024 * 1024  # 1 MB streaming chunks for sha256


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    """Streaming sha256 of a single file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sha256_aact_dir(aact_dir: Path) -> str:
    """sha256 of the concatenation of the 5 required AACT tables in alphabetical order."""
    tables = sorted([
        "conditions.txt",
        "facilities.txt",
        "interventions.txt",
        "sponsors.txt",
        "studies.txt",
    ])
    h = hashlib.sha256()
    for name in tables:
        fp = aact_dir / name
        if not fp.exists():
            raise FileNotFoundError(f"Required AACT table missing: {fp}")
        with open(fp, "rb") as fh:
            while True:
                chunk = fh.read(CHUNK)
                if not chunk:
                    break
                h.update(chunk)
    return h.hexdigest()


def _line_count(path: Path) -> int:
    """Fast binary line count (counts newlines)."""
    count = 0
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK)
            if not chunk:
                break
            count += chunk.count(b"\n")
    return count


def _aact_n_rows(aact_dir: Path) -> int:
    """Sum of data rows (line count minus 1 header) across the 5 required tables.
    n_rows for the AACT directory = sum of (lines - 1) for each table,
    which equals total data rows across all 5 files.
    We also separately surface studies.txt rows as the primary trial count.
    """
    tables = [
        "conditions.txt",
        "facilities.txt",
        "interventions.txt",
        "sponsors.txt",
        "studies.txt",
    ]
    total = 0
    for name in tables:
        total += _line_count(aact_dir / name) - 1  # subtract header row
    return total


def _studies_n_rows(aact_dir: Path) -> int:
    """Row count for studies.txt only (primary NCT count)."""
    return _line_count(aact_dir / "studies.txt") - 1


def _csv_n_rows(path: Path) -> int:
    """Data rows in a CSV (line count minus 1 header)."""
    return _line_count(path) - 1


def _parquet_info(path: Path):
    """Return (n_rows, n_unique_reviews) for the Pairwise70 parquet."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise ImportError("pyarrow is required for Pairwise70 metadata. pip install pyarrow")
    pf = pq.read_table(str(path))
    df = pf.to_pandas()
    n_rows = len(df)
    n_unique_reviews = int(df["review_id"].nunique()) if "review_id" in df.columns else None
    return n_rows, n_unique_reviews


def _cdsr_n_reviews(path: Path) -> int:
    """Count distinct review_id in the CDSR sqlite (table: review_strings)."""
    conn = sqlite3.connect(str(path))
    try:
        # Detect the table name defensively
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        # Prefer review_strings; fall back to review_study_strings
        candidates = [t for t in tables if "review" in t.lower()]
        if not candidates:
            raise ValueError(f"No review* table found in {path}. Tables: {tables}")
        table = candidates[0]
        # Determine the review_id column name
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        id_col = "review_id" if "review_id" in cols else cols[0]
        n = conn.execute(
            f"SELECT COUNT(DISTINCT {id_col}) FROM {table}"
        ).fetchone()[0]
        return int(n)
    finally:
        conn.close()


def _load_paths_toml(toml_path: Path) -> dict:
    """Load paths.toml. Uses tomllib/tomli if available, else minimal manual parse."""
    if not toml_path.exists():
        raise FileNotFoundError(
            f"paths.toml not found at {toml_path}. "
            "Copy paths.toml.example and fill in your local paths."
        )
    if tomllib is not None:
        with open(toml_path, "rb") as fh:
            return tomllib.load(fh)
    # Minimal fallback parser for simple key = "value" toml
    result = {}
    with open(toml_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                result[key] = val
    return result


def _write_json(path: Path, data: dict) -> None:
    """Write JSON with sorted keys and trailing newline (idempotent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ---------------------------------------------------------------------------
# Per-source builders
# ---------------------------------------------------------------------------

def build_aact(aact_dir: Path, out_dir: Path) -> dict:
    print("  Computing sha256 for AACT (streaming ~1.1 GB)...")
    sha = _sha256_aact_dir(aact_dir)
    # n_rows: sum of data rows across all 5 tables
    print("  Counting rows in AACT tables...")
    total_rows = _aact_n_rows(aact_dir)
    studies_rows = _studies_n_rows(aact_dir)
    meta = {
        "source": "aact",
        "snapshot_path": str(aact_dir),
        "sha256": sha,
        "fetched_at": "2026-05-08",
        "source_url": "https://aact.ctti-clinicaltrials.org/pipe_files",
        "snapshot_date": "2026-04-12",
        "n_rows": total_rows,
        "notes": (
            "AACT pipe-delimited dump 2026-04-12. "
            f"n_rows = sum of data rows across 5 tables (conditions, facilities, "
            f"interventions, sponsors, studies). "
            f"studies.txt alone: {studies_rows} rows (= NCT trial count). "
            "sha256 = hash of sequential concatenation of the 5 files in alphabetical order."
        ),
    }
    _write_json(out_dir / "aact_metadata.json", meta)
    print(f"  aact_metadata.json written. sha256={sha[:16]}... n_rows={total_rows}")
    return meta


def build_ictrp(ictrp_path: Path, out_dir: Path) -> dict:
    print("  Computing sha256 for ICTRP CSV...")
    sha = _sha256_file(ictrp_path)
    n_rows = _csv_n_rows(ictrp_path)
    meta = {
        "source": "ictrp",
        "snapshot_path": str(ictrp_path),
        "sha256": sha,
        "fetched_at": "2026-05-08",
        "source_url": "https://www.who.int/clinical-trials-registry-platform",
        "snapshot_date": "2026-05-04",
        "n_rows": n_rows,
        "notes": (
            "PACTR-scoped subset (~5,878 trials) in WHO ICTRP CSV schema. "
            "Not the full ICTRP weekly export (~700K trials). "
            "MUST be replaced with full ICTRP before Task 27 real run; "
            "v0.1.0 atlas headlines computed against this snapshot would "
            "systematically miss EUCTR/ISRCTN-only trials registered outside Africa."
        ),
    }
    _write_json(out_dir / "ictrp_metadata.json", meta)
    print(f"  ictrp_metadata.json written. sha256={sha[:16]}... n_rows={n_rows}")
    return meta


def build_pairwise70(parquet_path: Path, out_dir: Path) -> dict:
    print("  Computing sha256 for Pairwise70 parquet...")
    sha = _sha256_file(parquet_path)
    print("  Reading parquet for row/review counts...")
    n_rows, n_unique_reviews = _parquet_info(parquet_path)
    meta = {
        "source": "pairwise70",
        "snapshot_path": str(parquet_path),
        "sha256": sha,
        "fetched_at": "2026-05-08",
        "source_url": "https://github.com/mahmood726-cyber/repro-floor-atlas",
        "snapshot_date": "2026-04-12",
        "n_rows": n_rows,
        "n_unique_reviews": n_unique_reviews,
        "notes": (
            "Pairwise70 study_references index: NCT-to-review_id lookup for 374 "
            "Cochrane reviews. Used for cross-atlas linkage (TB trials -> Cochrane MA). "
            "n_unique_reviews = distinct review_id values in the parquet."
        ),
    }
    _write_json(out_dir / "pairwise70_metadata.json", meta)
    print(
        f"  pairwise70_metadata.json written. sha256={sha[:16]}... "
        f"n_rows={n_rows} n_unique_reviews={n_unique_reviews}"
    )
    return meta


def build_cdsr(cdsr_path: Path, out_dir: Path) -> dict:
    print("  Computing sha256 for CDSR sqlite...")
    sha = _sha256_file(cdsr_path)
    print("  Counting distinct reviews in CDSR...")
    n_reviews = _cdsr_n_reviews(cdsr_path)
    meta = {
        "source": "cdsr",
        "snapshot_path": str(cdsr_path),
        "sha256": sha,
        "fetched_at": "2026-05-08",
        "source_url": "https://www.cochranelibrary.com/cdsr/reviews",
        "snapshot_date": "2026-04-12",
        "n_rows": n_reviews,
        "n_reviews": n_reviews,
        "notes": (
            "CDSR string index (review_strings table) used for full-text TB-keyword "
            "screening of Cochrane reviews. n_rows = n_reviews = distinct review_id "
            "values in the review_strings table."
        ),
    }
    _write_json(out_dir / "cdsr_metadata.json", meta)
    print(f"  cdsr_metadata.json written. sha256={sha[:16]}... n_reviews={n_reviews}")
    return meta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths-toml",
        default="paths.toml",
        help="Path to paths.toml (default: paths.toml relative to cwd)",
    )
    args = parser.parse_args()

    # Resolve paths.toml relative to script's repo root (parent of scripts/)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    toml_path = Path(args.paths_toml)
    if not toml_path.is_absolute():
        toml_path = repo_root / toml_path

    print(f"Loading paths from: {toml_path}")
    cfg = _load_paths_toml(toml_path)

    out_dir = repo_root / "data" / "snapshots"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n[1/4] AACT")
    build_aact(Path(cfg["aact_snapshot_dir"]), out_dir)

    print("\n[2/4] ICTRP")
    build_ictrp(Path(cfg["ictrp_snapshot"]), out_dir)

    print("\n[3/4] Pairwise70")
    build_pairwise70(Path(cfg["pairwise70_index"]), out_dir)

    print("\n[4/4] CDSR")
    build_cdsr(Path(cfg["cdsr_string_index"]), out_dir)

    print("\nAll metadata JSONs written to", out_dir)


if __name__ == "__main__":
    main()
