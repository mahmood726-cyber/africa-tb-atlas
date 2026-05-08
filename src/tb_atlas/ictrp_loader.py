"""ICTRP weekly export loader for africa-tb-atlas.

Loads the WHO ICTRP weekly CSV export and normalizes to match aact_loader.py
output schema: nct_id, isrctn_id, euctr_id, brief_title, start_date, enrollment,
interventions (list[str]), countries (list[str]), conditions (list[str]),
lead_sponsor (str), result_url (str).

Different from PACTR-Hiddenness's loader: NO source-register filter (we want
ALL ICTRP trials, then dedup against AACT in trial_dedup.py). Extracts NCT,
ISRCTN, and EUCTR IDs from TrialID + Secondary_IDs columns.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd


REQUIRED_COLUMNS = (
    "TrialID", "Public_title", "Date_registration", "Target_size",
    "Countries", "Intervention", "Conditions", "Primary_sponsor",
    "Recruitment_Status", "Results_URL", "Secondary_IDs", "Source_Register",
)


class ICTRPSchemaError(ValueError):
    """Raised when an ICTRP CSV has unexpected/missing columns."""


# Regex patterns for ID extraction
_NCT_RE = re.compile(r"\b(NCT\d{8})\b")
_ISRCTN_RE = re.compile(r"\b(ISRCTN\d{8})\b")
_EUCTR_RE = re.compile(r"\b(EUCTR\d{4}-\d{6}-\d{2})\b")


def _extract_nct(*texts) -> str:
    for t in texts:
        if t:
            m = _NCT_RE.search(str(t))
            if m:
                return m.group(1)
    return ""


def _extract_isrctn(*texts) -> str:
    for t in texts:
        if t:
            m = _ISRCTN_RE.search(str(t))
            if m:
                return m.group(1)
    return ""


def _extract_euctr(*texts) -> str:
    for t in texts:
        if t:
            m = _EUCTR_RE.search(str(t))
            if m:
                return m.group(1)
    return ""


def _split_list(value: str, sep: str = ";") -> list[str]:
    """Split a delimited string into trimmed non-empty parts.
    Sorted for byte-stability per spec §3.2.
    """
    if not value or not isinstance(value, str):
        return []
    parts = [p.strip() for p in value.split(sep) if p.strip()]
    return sorted(set(parts))


def load_ictrp(path) -> pd.DataFrame:
    """Load WHO ICTRP weekly CSV -> normalized DataFrame.

    Returns DataFrame with columns:
      nct_id, isrctn_id, euctr_id, brief_title, start_date, enrollment,
      interventions, countries, conditions, lead_sponsor, result_url, source.

    Schema-drift fail-closed: missing required columns raise ICTRPSchemaError.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ICTRP snapshot missing: {path}")

    raw = pd.read_csv(
        path, dtype=str, low_memory=False,
        keep_default_na=False, na_values=[""],
    )

    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ICTRPSchemaError(
            f"ICTRP snapshot at {path} missing required columns: {missing}"
        )

    out = pd.DataFrame()
    out["nct_id"] = raw.apply(
        lambda r: _extract_nct(r["TrialID"], r.get("Secondary_IDs", "")), axis=1
    )
    out["isrctn_id"] = raw.apply(
        lambda r: _extract_isrctn(r["TrialID"], r.get("Secondary_IDs", "")), axis=1
    )
    out["euctr_id"] = raw.apply(
        lambda r: _extract_euctr(r["TrialID"], r.get("Secondary_IDs", "")), axis=1
    )
    out["brief_title"] = raw["Public_title"].fillna("").astype(str)
    out["start_date"] = pd.to_datetime(raw["Date_registration"], errors="coerce")
    out["enrollment"] = pd.to_numeric(raw["Target_size"], errors="coerce")
    out["countries"] = raw["Countries"].fillna("").apply(lambda s: _split_list(s, sep=";"))
    out["interventions"] = raw["Intervention"].fillna("").apply(lambda s: _split_list(s, sep=";"))
    out["conditions"] = raw["Conditions"].fillna("").apply(lambda s: _split_list(s, sep=";"))
    out["lead_sponsor"] = raw["Primary_sponsor"].fillna("").astype(str)
    out["result_url"] = raw["Results_URL"].fillna("").astype(str)
    out["source"] = "ictrp"
    return out
