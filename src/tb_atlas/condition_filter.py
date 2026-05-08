"""Match conditions field to MDR / pre-XDR / XDR / RR-TB (drug-resistant TB).

The atlas is restricted to drug-resistant TB. Drug-sensitive TB trials are
included only if their intervention contains a target drug (handled upstream
in intervention_filter); their condition does NOT trigger inclusion here.
"""
from __future__ import annotations
import re

DR_TB_PATTERNS = [
    r"\bmdr[\s\-]?tb\b",
    r"\bmultidrug[\s\-]?resistant\s+tuberculos",
    r"\bxdr[\s\-]?tb\b",
    r"\bextensively[\s\-]?drug[\s\-]?resistant\s+tuberculos",
    r"\bpre[\s\-]?xdr",
    r"\brifampi(?:cin|n)[\s\-]resistant[\s\-]tuberculos",
    r"\brr[\s\-]?tb\b",
    r"\bmdr\s+tuberculos",
]


def is_drug_resistant_tb(conditions) -> bool:
    """Return True if any item in `conditions` matches a DR-TB pattern."""
    if not conditions:
        return False
    text = " | ".join(str(c) for c in conditions).lower()
    return any(re.search(p, text) for p in DR_TB_PATTERNS)
