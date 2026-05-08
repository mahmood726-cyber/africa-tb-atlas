from pathlib import Path
import pandas as pd
from tb_atlas.aact_loader import load_aact
from tb_atlas.ictrp_loader import load_ictrp
from tb_atlas.population_pipeline import build_denominator

FIX = Path(__file__).parent / "fixtures"


def test_phase_b_pipeline_yields_only_eligible_trials():
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    denom, audit = build_denominator(aact, ictrp)
    # Inspect what should be eligible:
    # AACT 5 trials (NCT01001-01005):
    #   NCT01001 Bdq+Lzd MDR-TB 2014 → eligible
    #   NCT01002 Pretomanid+PA-824 XDR 2017 → eligible
    #   NCT01003 Linezolid MDR-TB 2019 → eligible
    #   NCT01004 vaccine M72 → no target drug → drop
    #   NCT01005 Bdq MDR-TB 2010 → pre-2012 → drop
    # ICTRP 8 trials:
    #   NCT02000001 BPaL XDR 2018 → eligible
    #   ISRCTN26973455+NCT04207112 TB-PRACTECAL 2017 → eligible
    #   EUCTR2018-001234-56 Bdq+Mfx MDR 2018 → eligible
    #   NCT02000002 Linezolid MDR 2019 → eligible
    #   ICTRP-CN-001 Linezolid MDR 2020 → eligible
    #   NCT02000003 Pediatric BPaL 2021 → pediatric → drop
    #   NCT02000004 Linezolid MDR 2010 → pre-2012 → drop
    #   NCT02000005 Rifapentine+Mfx DS-TB → no target drug → drop
    # Total eligible: 3 (AACT) + 5 (ICTRP) = 8
    assert len(denom) == 8


def test_phase_b_audit_has_drop_reasons():
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    denom, audit = build_denominator(aact, ictrp)
    drop_reasons = set(audit[audit.included == False]["reason"])
    assert "no_target_drug" in drop_reasons
    assert "pre_2012" in drop_reasons
    assert "pediatric" in drop_reasons


def test_phase_b_audit_records_every_input_trial():
    """Every input trial should produce at least one audit row (included or
    not). Plus dedup rows for ICTRP trials that match an AACT trial."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    denom, audit = build_denominator(aact, ictrp)
    # 5 AACT + 8 ICTRP = 13 input trials. Each gets one filter-audit row.
    # Dedup may add more rows for ICTRP trials kept after filtering.
    filter_audit = audit[audit.source.isin(["aact", "ictrp"])]
    assert len(filter_audit) == 13


def test_phase_b_dedup_log_present_in_audit():
    """The audit should include rows from trial_dedup with source='dedup'."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    denom, audit = build_denominator(aact, ictrp)
    dedup_rows = audit[audit.source == "dedup"]
    # Filtered AACT (3 kept) + Filtered ICTRP (5 kept) — dedup decisions only
    # for the 5 ICTRP rows that survived filtering. Their NCTs are different
    # from the 3 AACT NCTs (NCT0200000* vs NCT0100*), so all 5 should be
    # 'kept_ictrp_only' (no merges).
    assert len(dedup_rows) == 5
    assert (dedup_rows["trial_id"] != "").all()


def test_phase_b_no_target_drug_drops_vaccine():
    """NCT01004 (M72 vaccine) has no Bdq/Pa/Lzd → no_target_drug."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    _, audit = build_denominator(aact, ictrp)
    nct04 = audit[(audit.trial_id == "NCT01004") & (audit.source == "aact")]
    assert len(nct04) == 1
    assert nct04.iloc[0]["reason"] == "no_target_drug"
    assert nct04.iloc[0]["included"] == False


def test_phase_b_pre_2012_drops_old_trials():
    """NCT01005 (start 2010-05-01) → pre_2012 (it has Bdq so passes intervention
    filter; start_date filter drops it)."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    _, audit = build_denominator(aact, ictrp)
    nct05 = audit[(audit.trial_id == "NCT01005") & (audit.source == "aact")]
    assert len(nct05) == 1
    assert nct05.iloc[0]["reason"] == "pre_2012"


def test_phase_b_pediatric_filter_drops_peds_trial():
    """NCT02000003 'Pediatric BPaL' → pediatric (passes drug + condition + date,
    fails population)."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    _, audit = build_denominator(aact, ictrp)
    peds = audit[(audit.trial_id == "NCT02000003") & (audit.source == "ictrp")]
    assert len(peds) == 1
    assert peds.iloc[0]["reason"] == "pediatric"


def test_phase_b_audit_columns():
    """Audit DataFrame must have exactly the 4 expected columns."""
    aact = load_aact(FIX / "aact_micro")
    ictrp = load_ictrp(FIX / "ictrp_micro.csv")
    _, audit = build_denominator(aact, ictrp)
    assert set(audit.columns) == {"source", "trial_id", "included", "reason"}
