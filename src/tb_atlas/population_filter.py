"""Exclude pure pediatric trials (the spec scopes to adult/adolescent only).

Pure-pediatric markers are conservative — when in doubt, INCLUDE
(false positives are caught downstream by the spot-check audit;
false negatives are silent and unrecoverable).
"""
from __future__ import annotations
import re

PEDIATRIC_PATTERNS = [
    r"\bpediatric\b",
    r"\bpaediatric\b",
    r"\binfant",
    r"\bchildren\b",
    r"\bunder[\s\-]?(age[\s\-]?)?(5|10|12)\b",
]

# Adult-positive markers that override pediatric-keyword matches
ADULT_OVERRIDES = [
    r"\badult",
    r"\badolescent",
    r"\bage[ds]?[\s\-]?\>?[=]?[\s\-]?(12|18)\b",
]


def is_adult_or_adolescent(title: str) -> bool:
    if not title:
        return True  # default include — population filter is permissive
    text = title.lower()
    has_ped = any(re.search(p, text) for p in PEDIATRIC_PATTERNS)
    has_adult = any(re.search(p, text) for p in ADULT_OVERRIDES)
    if has_ped and not has_adult:
        return False
    return True
