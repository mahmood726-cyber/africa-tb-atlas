from pathlib import Path
import pytest
from tb_atlas.ictrp_loader import load_ictrp, ICTRPSchemaError

FIXTURE = Path(__file__).parent / "fixtures" / "ictrp_micro.csv"


def test_load_ictrp_returns_normalised_columns():
    df = load_ictrp(FIXTURE)
    for col in ["nct_id", "isrctn_id", "euctr_id", "brief_title",
                "start_date", "enrollment", "interventions",
                "countries", "conditions", "lead_sponsor",
                "result_url", "source"]:
        assert col in df.columns, f"missing column: {col}"
    assert len(df) == 8


def test_load_ictrp_extracts_dual_registration():
    df = load_ictrp(FIXTURE)
    dual = df[df.brief_title == "Dual-registered Trial"].iloc[0]
    assert dual.nct_id == "NCT02000002"
    assert dual.isrctn_id == "ISRCTN12345678"


def test_load_ictrp_extracts_isrctn_with_nct_secondary():
    df = load_ictrp(FIXTURE)
    pract = df[df.brief_title == "TB-PRACTECAL"].iloc[0]
    assert pract.isrctn_id == "ISRCTN26973455"
    assert pract.nct_id == "NCT04207112"


def test_load_ictrp_handles_ictrp_only_no_secondary():
    df = load_ictrp(FIXTURE)
    cn = df[df.brief_title == "Chinese MDR-TB linezolid trial"].iloc[0]
    assert cn.nct_id == ""
    assert cn.isrctn_id == ""
    assert cn.euctr_id == ""


def test_load_ictrp_country_list_split_correctly():
    df = load_ictrp(FIXTURE)
    pract = df[df.brief_title == "TB-PRACTECAL"].iloc[0]
    assert set(pract.countries) == {"South Africa", "Belarus", "Uzbekistan"}


def test_load_ictrp_intervention_list_split_correctly():
    df = load_ictrp(FIXTURE)
    bpal = df[df.brief_title == "BPaL Phase 3"].iloc[0]
    assert "Bedaquiline" in bpal.interventions
    assert "Pretomanid" in bpal.interventions
    assert "Linezolid" in bpal.interventions


def test_load_ictrp_extracts_euctr_id():
    df = load_ictrp(FIXTURE)
    eu = df[df.brief_title == "European Bdq+Mfx"].iloc[0]
    assert eu.euctr_id == "EUCTR2018-001234-56"
    assert eu.nct_id == ""


def test_load_ictrp_fails_closed_on_missing_column(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("TrialID,SomethingElse\nNCT001,x\n", encoding="utf-8")
    with pytest.raises(ICTRPSchemaError):
        load_ictrp(bad)


def test_load_ictrp_fails_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_ictrp(tmp_path / "does_not_exist.csv")


def test_load_ictrp_lists_are_sorted_for_byte_stability():
    """Spec §3.2: list-valued columns must be sorted."""
    df = load_ictrp(FIXTURE)
    for _, row in df.iterrows():
        assert row.interventions == sorted(row.interventions), f"{row.brief_title}: interventions not sorted"
        assert row.countries == sorted(row.countries), f"{row.brief_title}: countries not sorted"
        assert row.conditions == sorted(row.conditions), f"{row.brief_title}: conditions not sorted"


def test_load_ictrp_source_column_marked():
    df = load_ictrp(FIXTURE)
    assert (df["source"] == "ictrp").all()


def test_load_ictrp_excludes_no_source_filter():
    """Different from PACTR loader: TB Atlas keeps ALL trials, not just one register."""
    df = load_ictrp(FIXTURE)
    # 8 trials in fixture, all should be present
    assert len(df) == 8
