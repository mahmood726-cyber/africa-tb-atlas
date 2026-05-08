"""Map intervention list to one of 8 drug-class buckets (spec §1.6 #8)."""
from __future__ import annotations
from enum import Enum
from .intervention_filter import matches_target_drug


class DrugClass(str, Enum):
    BPAL = "BPaL"
    BPALM = "BPaLM"
    BDQ_OTHER_COMPANION = "Bdq+other-companion"
    PA_LZD_NO_BDQ = "Pa+Lzd (no Bdq)"
    LZD_DOSE = "Lzd dose-finding"
    BDQ_ONLY = "Bdq monotherapy/pair"
    PA_ONLY = "Pa monotherapy/pair"
    OTHER = "other"


def _has_moxifloxacin(interventions) -> bool:
    if not interventions:
        return False
    txt = " | ".join(interventions).lower()
    return ("moxifloxacin" in txt) or ("mfx" in txt.split())


def _has_non_target_companion(interventions) -> bool:
    """Any intervention that is NOT a target drug AND NOT moxifloxacin
    (moxifloxacin is treated separately for BPaLM detection)."""
    if not interventions:
        return False
    for i in interventions:
        if matches_target_drug(i) is None:
            txt = i.lower()
            if "moxifloxacin" in txt or "mfx" in txt.split():
                continue
            # Anything else non-target counts as a companion
            # (clofazimine, ethambutol, levofloxacin, isoniazid, rifampin, etc)
            return True
    return False


def classify_regimen(interventions) -> DrugClass:
    """Classify a trial's intervention list into one of 8 drug classes.

    Uses target-drug membership (matches_target_drug) to determine which
    of {Bdq, Pa, Lzd} are present.

    Order of checks (caveat: order-dependent):
      1. BPaLM first (BPaL + Mfx)
      2. BPaL (exact: all three target drugs, no mfx, no other companion)
      3. Pa+Lzd (no Bdq)
      4. Lzd dose-finding (Lzd-only, multiple arms)
      5. Bdq + companion (mfx or other or lzd or pa, but not BPaL/BPaLM)
      6. Bdq monotherapy/pair
      7. Pa monotherapy/pair
      8. OTHER
    """
    if not interventions:
        return DrugClass.OTHER

    drugs = set()
    for i in interventions:
        m = matches_target_drug(i)
        if m:
            drugs.add(m)

    has_bdq = "bedaquiline" in drugs
    has_pa = "pretomanid" in drugs
    has_lzd = "linezolid" in drugs
    has_mfx = _has_moxifloxacin(interventions)
    has_other = _has_non_target_companion(interventions)

    # BPaLM: all three target drugs + moxifloxacin
    if has_bdq and has_pa and has_lzd and has_mfx:
        return DrugClass.BPALM

    # BPaL: all three target drugs, no other companions, no moxifloxacin
    if has_bdq and has_pa and has_lzd and not has_mfx and not has_other:
        return DrugClass.BPAL

    # Pa+Lzd (no Bdq)
    if has_pa and has_lzd and not has_bdq:
        return DrugClass.PA_LZD_NO_BDQ

    # Lzd dose-finding: Lzd-only with multiple linezolid arms (heuristic:
    # multiple intervention strings that match linezolid)
    if has_lzd and not has_bdq and not has_pa:
        lzd_arms = [i for i in interventions if matches_target_drug(i) == "linezolid"]
        if len(lzd_arms) > 1:
            return DrugClass.LZD_DOSE
        # Otherwise fall through to OTHER (single Lzd arm with non-target
        # companions doesn't fit any specific bucket)

    # Bdq + companion (mfx OR other), but NOT BPaL/BPaLM
    if has_bdq and (has_mfx or has_other or has_lzd or has_pa):
        # Already excluded BPaL/BPaLM above
        return DrugClass.BDQ_OTHER_COMPANION

    # Bdq monotherapy/pair (no Pa, no Lzd, no other companion)
    if has_bdq and not (has_pa or has_lzd):
        return DrugClass.BDQ_ONLY

    # Pa monotherapy/pair (no Bdq, no Lzd, no other companion)
    if has_pa and not (has_bdq or has_lzd):
        return DrugClass.PA_ONLY

    return DrugClass.OTHER
