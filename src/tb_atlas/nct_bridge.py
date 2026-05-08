"""Extract NCT/ISRCTN/EUCTR cross-references from free-text fields.

Strict regex match. Trials whose IDs are absent from a text field
yield None — handled at orchestrator level.
"""
from __future__ import annotations
import re
from typing import Optional

NCT_RE = re.compile(r"\bNCT(\d{8})\b")
ISRCTN_RE = re.compile(r"\b(ISRCTN\d{8})\b")
EUCTR_RE = re.compile(r"\b(EUCTR\d{4}-\d{6}-\d{2})\b")


def extract_nct(text: Optional[str]) -> Optional[str]:
    """Extract NCT ID from text.

    Args:
        text: Text to search for NCT ID.

    Returns:
        NCT ID string (e.g. 'NCT04207112') or None if not found.
    """
    if not text:
        return None
    m = NCT_RE.search(text)
    return f"NCT{m.group(1)}" if m else None


def extract_isrctn(text: Optional[str]) -> Optional[str]:
    """Extract ISRCTN ID from text.

    Args:
        text: Text to search for ISRCTN ID.

    Returns:
        ISRCTN ID string (e.g. 'ISRCTN26973455') or None if not found.
    """
    if not text:
        return None
    m = ISRCTN_RE.search(text)
    return m.group(1) if m else None


def extract_euctr(text: Optional[str]) -> Optional[str]:
    """Extract EUCTR ID from text.

    Args:
        text: Text to search for EUCTR ID.

    Returns:
        EUCTR ID string (e.g. 'EUCTR2018-001234-56') or None if not found.
    """
    if not text:
        return None
    m = EUCTR_RE.search(text)
    return m.group(1) if m else None


def is_tier0_invisible(nct: Optional[str]) -> bool:
    """Check if trial is tier0 (invisible to synthesis pipelines).

    Trials with no NCT cross-reference are tier0 — an equity finding per spec.

    Args:
        nct: NCT ID string or None.

    Returns:
        True if trial is tier0 (no NCT), False otherwise.
    """
    return not nct
