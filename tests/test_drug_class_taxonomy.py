import pytest
from tb_atlas.drug_class_taxonomy import classify_regimen, DrugClass


@pytest.mark.parametrize("interventions,expected", [
    # BPaL: exactly Bdq + Pa + Lzd
    (["Bedaquiline", "Pretomanid", "Linezolid"], DrugClass.BPAL),
    # BPaLM: BPaL + Mfx
    (["Bedaquiline", "Pretomanid", "Linezolid", "Moxifloxacin"], DrugClass.BPALM),
    # Bdq + non-target companion (clofazimine)
    (["Bedaquiline", "Clofazimine"], DrugClass.BDQ_OTHER_COMPANION),
    # Bdq + Lzd (no Pa) — has both target drugs but not all three
    (["Bedaquiline", "Linezolid"], DrugClass.BDQ_OTHER_COMPANION),
    # Pa + Lzd (no Bdq) — distinct bucket
    (["Pretomanid", "Linezolid"], DrugClass.PA_LZD_NO_BDQ),
    # Lzd dose-finding (multiple Lzd arms)
    (["Linezolid 1200mg", "Linezolid 600mg"], DrugClass.LZD_DOSE),
    # Bdq monotherapy
    (["Bedaquiline 400mg"], DrugClass.BDQ_ONLY),
    # Pa monotherapy
    (["Pretomanid 200mg"], DrugClass.PA_ONLY),
    # Mixed with non-canonical companion (rifapentine)
    (["Rifapentine", "Bedaquiline"], DrugClass.BDQ_OTHER_COMPANION),
    # Empty
    ([], DrugClass.OTHER),
    # All non-target
    (["Rifampicin", "Isoniazid", "Pyrazinamide"], DrugClass.OTHER),
    # Single Lzd arm with no other target (falls to OTHER, not LZD_DOSE)
    (["Linezolid"], DrugClass.OTHER),
])
def test_classify_regimen(interventions, expected):
    assert classify_regimen(interventions) == expected


def test_drug_class_enum_has_8_values():
    """Spec §1.6 #8: exactly 8 drug-class buckets."""
    assert len(list(DrugClass)) == 8


def test_bpal_excludes_when_extra_companion_present():
    """BPaL = exactly Bdq + Pa + Lzd. Adding a non-mfx companion -> not BPaL."""
    assert classify_regimen(["Bedaquiline", "Pretomanid", "Linezolid", "Clofazimine"]) == DrugClass.BDQ_OTHER_COMPANION


def test_brand_names_recognised():
    """Sirturo = bedaquiline; Dovprela = pretomanid; Zyvox = linezolid."""
    assert classify_regimen(["Sirturo", "Dovprela", "Zyvox"]) == DrugClass.BPAL


def test_pa_lzd_without_bdq():
    """Pa + Lzd combo without Bdq -> distinct bucket."""
    assert classify_regimen(["Pretomanid", "Linezolid"]) == DrugClass.PA_LZD_NO_BDQ


def test_lzd_dose_finding_with_brand_variants():
    """Multiple Lzd arms with different doses (could be Zyvox + Linezolid)."""
    assert classify_regimen(["Zyvox 600mg", "Linezolid 1200mg"]) == DrugClass.LZD_DOSE


def test_none_input_returns_other():
    assert classify_regimen(None) == DrugClass.OTHER
