from pathlib import Path
import pytest
from tb_atlas.aact_loader import load_aact, AACTSchemaError

FIXTURE = Path(__file__).parent / "fixtures" / "aact_micro"


def test_load_aact_returns_df_with_expected_columns():
    df = load_aact(FIXTURE)
    expected = {"nct_id", "brief_title", "start_date", "enrollment",
                "interventions", "countries", "conditions", "lead_sponsor"}
    assert expected.issubset(df.columns), f"missing columns: {expected - set(df.columns)}"
    assert len(df) == 5  # 5 trials in fixture


def test_load_aact_collapses_one_to_many_to_lists():
    df = load_aact(FIXTURE)
    nct1 = df[df.nct_id == "NCT01001"].iloc[0]
    assert "Bedaquiline" in nct1["interventions"]
    assert "Linezolid" in nct1["interventions"]
    assert "South Africa" in nct1["countries"]
    assert "United Kingdom" in nct1["countries"]


def test_load_aact_fails_closed_on_missing_table(tmp_path):
    # Empty dir — no studies.txt
    with pytest.raises(FileNotFoundError):
        load_aact(tmp_path)


def test_load_aact_fails_closed_on_schema_drift(tmp_path):
    # studies.txt with unexpected columns (missing expected, has unknown)
    (tmp_path / "studies.txt").write_text(
        "nct_id|UNKNOWN_NEW_COLUMN\nNCT001|x\n", encoding="utf-8"
    )
    for fname, header in [
        ("interventions.txt", "nct_id|intervention_type|name"),
        ("facilities.txt", "nct_id|country|city"),
        ("conditions.txt", "nct_id|name"),
        ("sponsors.txt", "nct_id|lead_or_collaborator|name"),
    ]:
        col_count = header.count('|')
        if col_count >= 2:
            (tmp_path / fname).write_text(f"{header}\nNCT001|x|y\n", encoding="utf-8")
        else:
            (tmp_path / fname).write_text(f"{header}\nNCT001|x\n", encoding="utf-8")
    with pytest.raises(AACTSchemaError):
        load_aact(tmp_path)


def test_load_aact_lead_sponsor_distinct_from_collaborator():
    df = load_aact(FIXTURE)
    nct4 = df[df.nct_id == "NCT01004"].iloc[0]
    assert nct4["lead_sponsor"] == "GSK"


def test_load_aact_enrollment_is_numeric():
    df = load_aact(FIXTURE)
    nct1 = df[df.nct_id == "NCT01001"].iloc[0]
    assert nct1["enrollment"] == 150  # not "150" string


def test_load_aact_start_date_is_datetime():
    import pandas as pd
    df = load_aact(FIXTURE)
    nct1 = df[df.nct_id == "NCT01001"].iloc[0]
    assert isinstance(nct1["start_date"], pd.Timestamp)
    assert nct1["start_date"].year == 2014
