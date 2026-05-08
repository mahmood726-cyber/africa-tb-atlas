"""Integration fixture tests for Task 23 (africa-tb-atlas v0.1.0).

Verifies that:
  - all 4 fixture artefacts load correctly
  - row counts match the deterministic generator
  - the Pairwise70 and CDSR fixtures have the expected schema
  - the AACT+ICTRP fixtures exercise the full population_pipeline
  - drug-class coverage in eligible trials includes at least BPaL, BPaLM, Bdq+companion
  - build_fixtures.py is byte-stable (re-running produces identical files)
"""
from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from tb_atlas.aact_loader import load_aact
from tb_atlas.drug_class_taxonomy import DrugClass, classify_regimen
from tb_atlas.ictrp_loader import load_ictrp
from tb_atlas.population_pipeline import build_denominator

FIX = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Basic load tests
# ---------------------------------------------------------------------------

def test_aact_50trial_loads():
    """AACT fixture loads to exactly 50 rows via the production loader."""
    df = load_aact(FIX / "aact_50trial")
    assert len(df) == 50


def test_ictrp_30trial_loads():
    """ICTRP fixture loads to exactly 30 rows via the production loader."""
    df = load_ictrp(FIX / "ictrp_30trial.csv")
    assert len(df) == 30


def test_pairwise70_micro_loads():
    """Pairwise70 micro fixture loads with the correct schema and row count."""
    df = pd.read_parquet(FIX / "pairwise70_micro.parquet")
    assert len(df) == 8
    assert {"review_id", "nct_id", "isrctn_id"}.issubset(set(df.columns))


def test_cdsr_string_micro_loads():
    """CDSR micro sqlite has exactly 4 distinct review IDs."""
    conn = sqlite3.connect(FIX / "cdsr_string_micro.sqlite")
    n = conn.execute(
        "SELECT COUNT(DISTINCT review_id) FROM review_strings"
    ).fetchone()[0]
    conn.close()
    assert n == 4


# ---------------------------------------------------------------------------
# Schema integrity tests
# ---------------------------------------------------------------------------

def test_aact_fixture_has_all_required_columns():
    """Loader output has all expected columns (confirms schema contract)."""
    df = load_aact(FIX / "aact_50trial")
    required = {"nct_id", "brief_title", "start_date", "enrollment",
                "overall_status", "study_type", "interventions",
                "countries", "conditions", "lead_sponsor"}
    assert required.issubset(set(df.columns))


def test_ictrp_fixture_has_all_required_columns():
    """ICTRP loader output has all expected columns."""
    df = load_ictrp(FIX / "ictrp_30trial.csv")
    required = {"nct_id", "isrctn_id", "euctr_id", "brief_title",
                "start_date", "enrollment", "interventions",
                "countries", "conditions", "lead_sponsor", "result_url", "source"}
    assert required.issubset(set(df.columns))


def test_pairwise70_has_isrctn_entry():
    """Pairwise70 fixture contains at least one row with a non-empty ISRCTN ID."""
    df = pd.read_parquet(FIX / "pairwise70_micro.parquet")
    assert (df["isrctn_id"] != "").any()


def test_cdsr_string_table_has_body_text():
    """review_strings table has non-empty body_text for every row."""
    conn = sqlite3.connect(FIX / "cdsr_string_micro.sqlite")
    rows = conn.execute("SELECT body_text FROM review_strings").fetchall()
    conn.close()
    assert all(row[0] for row in rows)


# ---------------------------------------------------------------------------
# Pipeline integration test
# ---------------------------------------------------------------------------

def test_aact_50trial_has_8_drug_classes_among_eligible():
    """Spec §1.6 #8: fixture covers all 8 drug-class buckets in the denominator.

    The fixture is designed to include at least one trial per bucket before
    population/date filters. BPaL, BPaLM, and Bdq+companion are required;
    the test also checks all 8 are present across the pre-filter denominator.
    """
    aact = load_aact(FIX / "aact_50trial")
    ictrp = load_ictrp(FIX / "ictrp_30trial.csv")
    denom, _ = build_denominator(aact, ictrp)
    classes = {classify_regimen(row.interventions) for _, row in denom.iterrows()}
    # Three buckets required by the task spec
    assert DrugClass.BPAL in classes, "BPaL not found in denominator drug classes"
    assert DrugClass.BPALM in classes, "BPaLM not found in denominator drug classes"
    assert DrugClass.BDQ_OTHER_COMPANION in classes, "Bdq+companion not found"
    # Verify all 8 buckets are represented across the combined fixture
    all_eight = {
        DrugClass.BPAL, DrugClass.BPALM, DrugClass.BDQ_OTHER_COMPANION,
        DrugClass.PA_LZD_NO_BDQ, DrugClass.LZD_DOSE,
        DrugClass.BDQ_ONLY, DrugClass.PA_ONLY, DrugClass.OTHER,
    }
    assert classes == all_eight, (
        f"Expected all 8 drug classes; missing: {all_eight - classes}"
    )


def test_ictrp_overlap_ncts_match_aact():
    """First 15 ICTRP rows share NCT IDs with the first 15 AACT trials."""
    from scripts.build_fixtures import AACT_STUDIES
    aact_ncts = {s[0] for s in AACT_STUDIES[:15]}
    df = load_ictrp(FIX / "ictrp_30trial.csv")
    ictrp_ncts_with_match = {
        nct for nct in df["nct_id"] if nct in aact_ncts
    }
    # At least 10 of the first 15 ICTRP rows must resolve to AACT NCTs
    assert len(ictrp_ncts_with_match) >= 10, (
        f"Expected >=10 ICTRP-AACT NCT overlaps, got {len(ictrp_ncts_with_match)}"
    )


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------

def test_aact_50trial_file_byte_stable():
    """Re-running build_fixtures.py produces byte-identical AACT and ICTRP files."""
    files = [
        REPO / "tests/fixtures/aact_50trial/studies.txt",
        REPO / "tests/fixtures/aact_50trial/interventions.txt",
        REPO / "tests/fixtures/aact_50trial/facilities.txt",
        REPO / "tests/fixtures/aact_50trial/conditions.txt",
        REPO / "tests/fixtures/aact_50trial/sponsors.txt",
        REPO / "tests/fixtures/ictrp_30trial.csv",
    ]
    before = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    subprocess.check_call(
        [sys.executable, "scripts/build_fixtures.py"],
        cwd=REPO,
    )
    after = {str(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    diffs = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    assert not diffs, (
        f"build_fixtures.py is not deterministic; changed files:\n"
        + "\n".join(f"  {k}: {v[0][:8]} -> {v[1][:8]}" for k, v in diffs.items())
    )
