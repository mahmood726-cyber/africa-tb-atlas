"""Filter trials to those whose interventions contain bedaquiline,
pretomanid, or linezolid (by generic name, brand name, or specific code names).

Positive list = match. Negative list = explicit non-match for confusable
code names.

CRITICAL: pretomanid is "PA-824" (Phase I/II code name). It is NOT
"TBA-354" — that is a different compound (a nitroimidazole investigated
separately and discontinued by TB Alliance). Misclassifying TBA-354 as
pretomanid would silently inflate the denominator and corrupt the atlas
headlines. The negative list exists to prevent this.
"""
from __future__ import annotations
import re
from typing import Optional


# Canonical drug -> list of accepted name patterns (case-insensitive).
# Each pattern uses \b for word boundaries to avoid sub-string matches.
POSITIVE_LIST = {
    "bedaquiline": [
        r"\bbedaquiline\b",
        r"\bsirturo\b",       # brand name (Janssen)
        r"\bbdq\b",           # common abbreviation
        r"\btmc[\s\-]?207\b", # original Tibotec code
    ],
    "pretomanid": [
        r"\bpretomanid\b",
        r"\bpa[\s\-]?824\b",  # Phase I/II code name (TB Alliance)
        r"\bdovprela\b",      # brand name (Mylan)
    ],
    "linezolid": [
        r"\blinezolid\b",
        r"\bzyvox\b",         # brand name (Pfizer)
        r"\blinox\b",         # generic brand
        r"\blinospan\b",      # generic brand (India)
        r"\bu[\s\-]?100766\b",# original Upjohn code
    ],
}

# Negative list: code names that look similar but are different compounds.
# These MUST NOT match. The atlas drops trials whose interventions match
# any negative-list pattern in 'strict' mode; in default mode, positive
# matches take precedence (see matches_target_drug logic).
NEGATIVE_LIST = [
    r"\btba[\s\-]?354\b",   # different nitroimidazole, discontinued -- NOT pretomanid
    r"\bpa[\s\-]?1314\b",   # unrelated PA-numbered compound
    r"\btba[\s\-]?7371\b",  # TB Alliance pipeline; not a target drug
]


class AmbiguousInterventionError(Exception):
    """Raised when an intervention string matches both positive and negative lists in strict mode."""


def matches_target_drug(name: str, strict: bool = False) -> Optional[str]:
    """Return canonical drug name (lowercase) if `name` matches one of the
    target drugs, else None.

    If `strict=True`, raise AmbiguousInterventionError on positive+negative
    co-match. Default (strict=False) returns the positive match (logged at
    orchestrator level via intervention_audit.csv).
    """
    if not name:
        return None
    text = name.lower()
    pos_match = None
    for canonical, patterns in POSITIVE_LIST.items():
        for pat in patterns:
            if re.search(pat, text):
                pos_match = canonical
                break
        if pos_match:
            break
    neg_match = any(re.search(pat, text) for pat in NEGATIVE_LIST)
    if pos_match and neg_match:
        if strict:
            raise AmbiguousInterventionError(
                f"intervention {name!r} matches both positive ({pos_match}) "
                f"and negative list (strict mode)"
            )
        # Default mode: positive wins, but the caller can still detect
        # ambiguity by checking matches_negative_list() separately.
    return pos_match


def matches_negative_list(name: str) -> bool:
    """Return True if `name` matches any negative-list pattern.

    Used by the orchestrator to log ambiguous strings to intervention_audit.csv
    without raising.
    """
    if not name:
        return False
    text = name.lower()
    return any(re.search(pat, text) for pat in NEGATIVE_LIST)


def contains_target_drug(interventions) -> bool:
    """Return True if ANY intervention in the list matches a target drug.

    `interventions` may be a list[str] or None (treated as empty).
    """
    if not interventions:
        return False
    return any(matches_target_drug(i) is not None for i in interventions)
