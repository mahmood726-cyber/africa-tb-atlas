"""Load AACT pipe-delimited tables into a single per-trial DataFrame.

AACT (Aggregate Analysis of ClinicalTrials.gov) ships pipe-delimited TSVs
quarterly. Schema drifts between releases — fail closed on unrecognized
columns rather than silently skip (per Lessons file 'AACT pipe-delim is
fragile' note).
"""
from pathlib import Path
import pandas as pd

REQUIRED_TABLES = ["studies", "interventions", "facilities", "conditions", "sponsors"]

EXPECTED_SCHEMAS = {
    "studies": {"nct_id", "brief_title", "start_date", "enrollment",
                "overall_status", "study_type"},
    "interventions": {"nct_id", "intervention_type", "name"},
    "facilities": {"nct_id", "country", "city"},
    "conditions": {"nct_id", "name"},
    "sponsors": {"nct_id", "lead_or_collaborator", "name"},
}


class AACTSchemaError(Exception):
    """Raised when an AACT table has unexpected columns (schema drift)."""


def _load_table(snapshot_dir: Path, table: str) -> pd.DataFrame:
    path = snapshot_dir / f"{table}.txt"
    if not path.exists():
        raise FileNotFoundError(f"AACT table missing: {path}")
    df = pd.read_csv(path, sep="|", dtype=str, keep_default_na=False, na_values=[""])
    expected = EXPECTED_SCHEMAS[table]
    actual = set(df.columns)
    if not expected.issubset(actual):
        missing = expected - actual
        raise AACTSchemaError(f"{table}.txt missing columns: {missing}")
    extra = actual - expected
    if extra:
        raise AACTSchemaError(
            f"{table}.txt has unexpected columns: {extra}. "
            f"AACT schema may have drifted; update EXPECTED_SCHEMAS after audit."
        )
    return df


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

    # Collapse one-to-many joins to lists.
    # Sort all list-valued aggregations for byte-stable output (spec §3.2).
    # AACT row order can drift between releases; downstream filters are order-insensitive.
    interventions_grp = (
        interventions.groupby("nct_id")["name"]
        .apply(lambda s: sorted(s))
        .rename("interventions")
    )
    countries_grp = (
        facilities.groupby("nct_id")["country"]
        .apply(lambda s: sorted(set(s)))
        .rename("countries")
    )
    conditions_grp = (
        conditions.groupby("nct_id")["name"]
        .apply(lambda s: sorted(set(s)))
        .rename("conditions")
    )

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
    for col in ["interventions", "countries", "conditions"]:
        out[col] = out[col].apply(lambda x: x if isinstance(x, list) else [])

    return out
