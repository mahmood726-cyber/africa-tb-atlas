"""Load AACT pipe-delimited tables into a single per-trial DataFrame.

AACT (Aggregate Analysis of ClinicalTrials.gov) ships pipe-delimited TSVs
quarterly. Schema drifts between releases — fail closed on unrecognized
columns rather than silently skip (per Lessons file 'AACT pipe-delim is
fragile' note).

Schema validation and the one-to-many list collapse are delegated to the shared
``aact-kit`` package (``validate_columns`` / ``aggregate_lists`` /
``ensure_list_columns``); the AACT-specific read semantics (``dtype=str``,
``keep_default_na=False``) and the lead-sponsor selection stay here as domain
logic. Install: ``pip install aact-kit`` (or an editable local aact-kit checkout).
"""
from pathlib import Path
import pandas as pd

from aact_kit import (
    AACTSchemaError,  # re-exported: same class aact_kit.validate_columns raises
    aggregate_lists,
    ensure_list_columns,
    validate_columns,
)

REQUIRED_TABLES = ["studies", "interventions", "facilities", "conditions", "sponsors"]

REQUIRED_SCHEMAS = {
    "studies": {"nct_id", "brief_title", "start_date", "enrollment",
                "overall_status", "study_type"},
    "interventions": {"nct_id", "intervention_type", "name"},
    "facilities": {"nct_id", "country", "city"},
    "conditions": {"nct_id", "name"},
    "sponsors": {"nct_id", "lead_or_collaborator", "name"},
}

# Backward-compat alias (older code/tests may import EXPECTED_SCHEMAS).
EXPECTED_SCHEMAS = REQUIRED_SCHEMAS

# Optional columns we keep when present (real AACT carries many more cols
# than our fixture; we project to a stable subset). NEW cols added: any
# column appearing in REQUIRED_SCHEMAS[table] OR OPTIONAL_KEEP[table] is
# preserved through `_load_table`. Other AACT cols are silently dropped
# (subset semantics; real AACT has 60+ studies cols we don't use).
OPTIONAL_KEEP = {
    "studies": {"results_first_posted_date", "phase", "completion_date",
                "last_known_status", "official_title"},
    "interventions": set(),
    "facilities": set(),
    "conditions": set(),
    "sponsors": set(),
}


# AACTSchemaError is imported from aact_kit (see module header) and raised by
# aact_kit.validate_columns; re-exported here for backward-compatible imports.
__all__ = [
    "AACTSchemaError",
    "REQUIRED_TABLES",
    "REQUIRED_SCHEMAS",
    "EXPECTED_SCHEMAS",
    "OPTIONAL_KEEP",
    "load_aact",
]


def _load_table(snapshot_dir: Path, table: str) -> pd.DataFrame:
    path = snapshot_dir / f"{table}.txt"
    if not path.exists():
        raise FileNotFoundError(f"AACT table missing: {path}")
    # AACT-specific read: everything as strings, only "" is NA (so values like
    # "NA"/"null" survive as literal text). Type coercion happens in load_aact.
    df = pd.read_csv(path, sep="|", dtype=str, keep_default_na=False, na_values=[""])
    # Fail closed on missing required columns and project to required+optional
    # (sorted, byte-stable) via the shared validator.
    return validate_columns(
        df, f"{table}.txt", REQUIRED_SCHEMAS[table], OPTIONAL_KEEP.get(table, set())
    )


def load_aact(snapshot_dir) -> pd.DataFrame:
    """Load AACT snapshot and collapse to one row per NCT.

    Parameters
    ----------
    snapshot_dir : str or Path
        Directory containing pipe-delimited AACT .txt files:
        studies, interventions, facilities, conditions, sponsors.

    Returns
    -------
    pd.DataFrame
        One row per nct_id with columns:
        nct_id, brief_title, start_date (Timestamp), enrollment (numeric),
        overall_status, study_type, interventions (list[str]),
        countries (list[str]), conditions (list[str]), lead_sponsor (str).

    Raises
    ------
    FileNotFoundError
        If snapshot_dir does not exist or any required table file is missing.
    AACTSchemaError
        If any table has missing required columns or unexpected extra columns
        (indicating schema drift between AACT quarterly releases).
    """
    snapshot_dir = Path(snapshot_dir)
    if not snapshot_dir.exists():
        raise FileNotFoundError(f"AACT snapshot dir not found: {snapshot_dir}")

    studies = _load_table(snapshot_dir, "studies")
    interventions = _load_table(snapshot_dir, "interventions")
    facilities = _load_table(snapshot_dir, "facilities")
    conditions = _load_table(snapshot_dir, "conditions")
    sponsors = _load_table(snapshot_dir, "sponsors")

    # Collapse one-to-many joins to lists via the shared aggregator (sorts,
    # drops NaN, coerces to str for byte-stable output — spec §3.2). Note
    # interventions keep duplicates (dedup=False) to match prior behavior;
    # countries/conditions are deduped.
    interventions_grp = aggregate_lists(
        interventions, "name", dedup=False, name="interventions"
    )
    countries_grp = aggregate_lists(facilities, "country", name="countries")
    conditions_grp = aggregate_lists(conditions, "name", name="conditions")

    # Lead sponsor only (filter before join to avoid duplicating rows)
    lead = (
        sponsors[sponsors["lead_or_collaborator"] == "lead"][["nct_id", "name"]]
        .rename(columns={"name": "lead_sponsor"})
        .drop_duplicates(subset="nct_id")  # guard against >1 lead row per trial
    )

    # Type coercions on studies
    studies = studies.copy()
    studies["enrollment"] = pd.to_numeric(studies["enrollment"], errors="coerce")
    studies["start_date"] = pd.to_datetime(studies["start_date"], errors="coerce")

    # Merge everything
    out = (
        studies
        .merge(interventions_grp, on="nct_id", how="left")
        .merge(countries_grp, on="nct_id", how="left")
        .merge(conditions_grp, on="nct_id", how="left")
        .merge(lead, on="nct_id", how="left")
    )

    # Ensure list columns are never NaN (trials with no facilities/interventions
    # get empty list rather than float NaN)
    out = ensure_list_columns(out, ["interventions", "countries", "conditions"])

    return out
