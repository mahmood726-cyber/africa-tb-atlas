"""Generate deterministic integration fixtures for the orchestrator.

Run: python scripts/build_fixtures.py [--out-dir tests/fixtures]

Produces:
  - tests/fixtures/aact_50trial/{studies,interventions,facilities,conditions,sponsors}.txt
  - tests/fixtures/ictrp_30trial.csv
  - tests/fixtures/pairwise70_micro.parquet
  - tests/fixtures/cdsr_string_micro.sqlite

Determinism contract: re-running this script must produce identical files.
The script uses no random seeding -- all data is explicit literals.
"""
from __future__ import annotations
import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# AACT 50-trial fixture
# ---------------------------------------------------------------------------
# Covers all 8 drug classes; mix of Africa-recruiting and not;
# 5 pre-2012 (date-excluded), 3 pediatric (population-excluded),
# 5 no-target-drug (intervention-excluded).
#
# Schema: (nct_id, brief_title, start_date, enrollment, overall_status, study_type)
# All NCTs are 8-digit per CT.gov format.
# ---------------------------------------------------------------------------

AACT_STUDIES = [
    # --- BPaL (5) ---
    ("NCT04340700", "BPaL Phase 3 ZeNix",                 "2017-01-01", 181,  "Completed",  "Interventional"),
    ("NCT02333799", "Nix-TB BPaL XDR",                    "2014-04-01", 109,  "Completed",  "Interventional"),
    ("NCT03086486", "TB-PRACTECAL BPaLM",                  "2017-01-16", 552,  "Completed",  "Interventional"),
    ("NCT04062201", "BPaL Operational",                    "2019-09-01", 800,  "Recruiting", "Interventional"),
    ("NCT05071716", "BPaL Implementation Study",           "2021-10-01", 220,  "Recruiting", "Interventional"),
    # --- Bdq+companion (8) ---
    ("NCT02573350", "STREAM Stage 2 Bdq Arm",              "2016-04-01", 588,  "Completed",  "Interventional"),
    ("NCT01918397", "Bdq plus Moxifloxacin MDR",           "2014-08-01", 240,  "Completed",  "Interventional"),
    ("NCT04094493", "Bdq plus Clofazimine MDR",            "2019-07-01", 130,  "Recruiting", "Interventional"),
    ("NCT03828201", "Bdq plus Levofloxacin Cohort",        "2018-12-01", 95,   "Completed",  "Interventional"),
    ("NCT02409290", "endTB Bdq plus Pa companion",         "2017-04-01", 750,  "Completed",  "Interventional"),
    ("NCT03237182", "Bdq Operational South Africa",        "2018-01-01", 320,  "Completed",  "Interventional"),
    ("NCT04734652", "Bdq plus Mfx Belarus Cohort",         "2020-05-01", 110,  "Completed",  "Interventional"),
    ("NCT04575467", "Bdq plus Cfz Companion Trial",        "2020-09-01", 85,   "Recruiting", "Interventional"),
    # --- Pa+Lzd no Bdq (5) ---
    ("NCT04114669", "Pa plus Lzd Phase 2 dose",            "2018-11-01", 75,   "Completed",  "Interventional"),
    ("NCT04256434", "Pa plus Lzd 1200mg arm",              "2019-04-01", 60,   "Completed",  "Interventional"),
    ("NCT05176262", "Pa plus Lzd Cohort South Africa",     "2021-12-01", 110,  "Recruiting", "Interventional"),
    ("NCT04568967", "Pa plus Lzd plus rifampin",           "2020-08-01", 80,   "Completed",  "Interventional"),
    ("NCT05214755", "Pa plus Lzd Multi-arm",               "2022-01-15", 140,  "Recruiting", "Interventional"),
    # --- Lzd dose-finding (5) ---
    ("NCT01691534", "Linezolid Dose Optimisation",         "2013-06-01", 90,   "Completed",  "Interventional"),
    ("NCT02573355", "Linezolid 600 vs 1200",               "2015-04-01", 175,  "Completed",  "Interventional"),
    ("NCT03237203", "Lzd Dose-Finding Cohort",             "2018-01-15", 200,  "Completed",  "Interventional"),
    ("NCT03828244", "Linezolid Pharmacokinetics",          "2019-02-01", 65,   "Completed",  "Interventional"),
    ("NCT04094521", "Lzd 300mg vs 600mg",                  "2019-08-01", 110,  "Recruiting", "Interventional"),
    # --- Bdq monotherapy/pair (4) ---
    ("NCT01215110", "Bdq alone Phase 1",                   "2013-02-01", 45,   "Completed",  "Interventional"),
    ("NCT02333805", "Bdq 200mg standalone",                "2015-08-15", 55,   "Completed",  "Interventional"),
    ("NCT04114670", "Bdq plus Placebo control",            "2019-03-01", 80,   "Completed",  "Interventional"),
    ("NCT05071732", "Bdq compassionate use",               "2021-11-01", 60,   "Completed",  "Interventional"),
    # --- Pa monotherapy/pair (4) ---
    ("NCT02333780", "Pretomanid alone Phase 1",            "2014-09-01", 30,   "Completed",  "Interventional"),
    ("NCT03237145", "Pretomanid 200mg",                    "2017-12-01", 40,   "Completed",  "Interventional"),
    ("NCT04256441", "Pretomanid plus Placebo",             "2019-10-01", 65,   "Recruiting", "Interventional"),
    ("NCT05214762", "Pretomanid PK Study",                 "2022-01-20", 50,   "Recruiting", "Interventional"),
    # --- BPaL Africa fixed-dose cohorts (4) ---
    ("NCT04734666", "BPaL Africa Cohort South Africa",     "2020-04-01", 220,  "Completed",  "Interventional"),
    ("NCT04875611", "BPaL Mozambique",                     "2021-03-01", 95,   "Completed",  "Interventional"),
    ("NCT05176290", "BPaL Kenya Operational",              "2021-08-01", 130,  "Recruiting", "Interventional"),
    ("NCT05425912", "BPaL Tanzania Phase 4",               "2022-09-15", 180,  "Recruiting", "Interventional"),
    # --- No target drug / OTHER -- should be dropped (5) ---
    ("NCT03085954", "Rifapentine 4-month DS-TB",           "2017-05-01", 2516, "Completed",  "Interventional"),
    ("NCT01691489", "BCG Vaccine Trial",                   "2013-04-01", 1200, "Completed",  "Interventional"),
    ("NCT02573344", "Isoniazid plus Rifampin Standard",    "2015-09-01", 350,  "Completed",  "Interventional"),
    ("NCT04062277", "Moxifloxacin alone DS-TB",            "2019-10-01", 800,  "Completed",  "Interventional"),
    ("NCT04875655", "Levofloxacin DS-TB",                  "2021-04-01", 600,  "Recruiting", "Interventional"),
    # --- Pre-2012 with Bdq/Lzd/Pa (drug+condition pass; date drops) (4) ---
    ("NCT00866554", "Bdq Pre-EUA Phase 2",                 "2009-05-01", 47,   "Completed",  "Interventional"),
    ("NCT01191515", "Linezolid 2010 trial",                "2010-08-01", 100,  "Completed",  "Interventional"),
    ("NCT01215127", "Pretomanid Pre-2012",                 "2010-12-01", 35,   "Completed",  "Interventional"),
    ("NCT00866570", "Bdq legacy phase 2",                  "2009-09-01", 30,   "Completed",  "Interventional"),
    # --- Pediatric (drug+date pass; population_filter drops) (3) ---
    ("NCT04340711", "Pediatric BPaL Africa",               "2018-06-01", 80,   "Recruiting", "Interventional"),
    ("NCT05425933", "Children with MDR-TB Bdq",            "2022-10-01", 60,   "Recruiting", "Interventional"),
    ("NCT04094534", "Infant Lzd PK study",                 "2019-09-01", 35,   "Completed",  "Interventional"),
    # --- BPaLM explicit (round out to 50) (3) ---
    ("NCT04568980", "BPaLM Extended Regimen",              "2020-07-01", 300,  "Recruiting", "Interventional"),
    ("NCT05000101", "BPaLM vs BPaL Comparison",            "2021-05-01", 400,  "Recruiting", "Interventional"),
    ("NCT05176300", "BPaLM Short-Course Africa",           "2021-11-01", 250,  "Recruiting", "Interventional"),
]

assert len(AACT_STUDIES) == 50, f"AACT_STUDIES must be exactly 50, got {len(AACT_STUDIES)}"

# Interventions per NCT: (intervention_type, name) pairs
AACT_INTERVENTIONS: dict[str, list[tuple[str, str]]] = {
    # BPaL block
    "NCT04340700": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT02333799": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT03086486": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid"), ("Drug", "Moxifloxacin")],
    "NCT04062201": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT05071716": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    # Bdq+companion
    "NCT02573350": [("Drug", "Bedaquiline"), ("Drug", "Clofazimine"), ("Drug", "Moxifloxacin")],
    "NCT01918397": [("Drug", "Bedaquiline"), ("Drug", "Moxifloxacin")],
    "NCT04094493": [("Drug", "Bedaquiline"), ("Drug", "Clofazimine")],
    "NCT03828201": [("Drug", "Bedaquiline"), ("Drug", "Levofloxacin")],
    "NCT02409290": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Clofazimine")],
    "NCT03237182": [("Drug", "Bedaquiline"), ("Drug", "Clofazimine")],
    "NCT04734652": [("Drug", "Bedaquiline"), ("Drug", "Moxifloxacin")],
    "NCT04575467": [("Drug", "Bedaquiline"), ("Drug", "Clofazimine")],
    # Pa+Lzd no Bdq
    "NCT04114669": [("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT04256434": [("Drug", "Pretomanid"), ("Drug", "Linezolid 1200mg")],
    "NCT05176262": [("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT04568967": [("Drug", "Pretomanid"), ("Drug", "Linezolid"), ("Drug", "Rifampin")],
    "NCT05214755": [("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    # Lzd dose-finding
    "NCT01691534": [("Drug", "Linezolid 1200mg"), ("Drug", "Linezolid 600mg")],
    "NCT02573355": [("Drug", "Linezolid 600mg"), ("Drug", "Linezolid 1200mg")],
    "NCT03237203": [("Drug", "Linezolid 600mg"), ("Drug", "Linezolid 300mg")],
    "NCT03828244": [("Drug", "Linezolid 600mg"), ("Drug", "Linezolid 1200mg")],
    "NCT04094521": [("Drug", "Linezolid 300mg"), ("Drug", "Linezolid 600mg")],
    # Bdq monotherapy/pair
    "NCT01215110": [("Drug", "Bedaquiline")],
    "NCT02333805": [("Drug", "Bedaquiline 200mg")],
    "NCT04114670": [("Drug", "Bedaquiline"), ("Other", "Placebo")],
    "NCT05071732": [("Drug", "Bedaquiline")],
    # Pa monotherapy/pair
    "NCT02333780": [("Drug", "Pretomanid")],
    "NCT03237145": [("Drug", "Pretomanid 200mg")],
    "NCT04256441": [("Drug", "Pretomanid"), ("Other", "Placebo")],
    "NCT05214762": [("Drug", "Pretomanid")],
    # BPaL Africa fixed-dose cohorts
    "NCT04734666": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT04875611": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT05176290": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT05425912": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    # No target drug -- should be dropped
    "NCT03085954": [("Drug", "Rifapentine"), ("Drug", "Moxifloxacin")],
    "NCT01691489": [("Biological", "BCG Vaccine")],
    "NCT02573344": [("Drug", "Isoniazid"), ("Drug", "Rifampin")],
    "NCT04062277": [("Drug", "Moxifloxacin")],
    "NCT04875655": [("Drug", "Levofloxacin")],
    # Pre-2012
    "NCT00866554": [("Drug", "Bedaquiline")],
    "NCT01191515": [("Drug", "Linezolid")],
    "NCT01215127": [("Drug", "Pretomanid")],
    "NCT00866570": [("Drug", "Bedaquiline")],
    # Pediatric
    "NCT04340711": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid")],
    "NCT05425933": [("Drug", "Bedaquiline"), ("Drug", "Clofazimine")],
    "NCT04094534": [("Drug", "Linezolid")],
    # BPaLM explicit round-out
    "NCT04568980": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid"), ("Drug", "Moxifloxacin")],
    "NCT05000101": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid"), ("Drug", "Moxifloxacin")],
    "NCT05176300": [("Drug", "Bedaquiline"), ("Drug", "Pretomanid"), ("Drug", "Linezolid"), ("Drug", "Moxifloxacin")],
}

# Facilities: first 25 trials have at least one African country, rest non-African.
# Deterministic: assigned by index position in AACT_STUDIES.
_AFRICAN = ["South Africa", "Kenya", "Tanzania", "Uganda", "Mozambique", "Zambia"]
_NON_AFRICAN = ["United States", "United Kingdom", "Belarus", "Russia", "Germany", "Brazil"]

AACT_FACILITIES: dict[str, list[tuple[str, str]]] = {}
for _i, (_nct, *_rest) in enumerate(AACT_STUDIES):
    _countries: list[str]
    if _i < 25:
        _countries = [_AFRICAN[_i % len(_AFRICAN)]]
        if _i % 3 == 0:
            _countries.append("United Kingdom")
    else:
        _countries = [_NON_AFRICAN[(_i - 25) % len(_NON_AFRICAN)]]
        if _i % 4 == 0:
            _countries.append("South Africa")
    AACT_FACILITIES[_nct] = [("US", c) for c in _countries]

# Conditions per NCT
AACT_CONDITIONS: dict[str, list[tuple[str]]] = {}
for _i, (_nct, _title, *_rest) in enumerate(AACT_STUDIES):
    if "Vaccine" in _title or "BCG" in _title:
        AACT_CONDITIONS[_nct] = [("Tuberculosis, Pulmonary",)]
    elif "DS-TB" in _title or "Standard" in _title or "Rifapentine 4-month" in _title:
        AACT_CONDITIONS[_nct] = [("Drug-Sensitive Tuberculosis",)]
    elif any(w in _title for w in ("Pediatric", "Children", "Infant")):
        AACT_CONDITIONS[_nct] = [("Multidrug-Resistant Tuberculosis",)]
    elif _i % 2 == 0:
        AACT_CONDITIONS[_nct] = [("Multidrug-Resistant Tuberculosis",)]
    else:
        AACT_CONDITIONS[_nct] = [("MDR-TB",)]

# Sponsors per NCT
_SPONSORS = ["TB Alliance", "MSF", "USAID", "NIH", "EDCTP", "WHO", "Janssen", "GSK"]
AACT_SPONSORS: dict[str, list[tuple[str, str]]] = {
    _nct: [("lead", _SPONSORS[_i % len(_SPONSORS)])]
    for _i, (_nct, *_rest) in enumerate(AACT_STUDIES)
}


def _write_aact(out_dir: Path) -> None:
    """Write 5 pipe-delimited files for the AACT 50-trial fixture."""
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "studies.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("nct_id|brief_title|start_date|enrollment|overall_status|study_type\n")
        for nct, title, dt, enr, status, stype in AACT_STUDIES:
            fh.write(f"{nct}|{title}|{dt}|{enr}|{status}|{stype}\n")

    with (out_dir / "interventions.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("nct_id|intervention_type|name\n")
        for nct, *_ in AACT_STUDIES:
            for itype, name in AACT_INTERVENTIONS.get(nct, []):
                fh.write(f"{nct}|{itype}|{name}\n")

    with (out_dir / "facilities.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("nct_id|country|city\n")
        for nct, *_ in AACT_STUDIES:
            for _, country in AACT_FACILITIES.get(nct, []):
                fh.write(f"{nct}|{country}|\n")

    with (out_dir / "conditions.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("nct_id|name\n")
        for nct, *_ in AACT_STUDIES:
            for cond_tuple in AACT_CONDITIONS.get(nct, []):
                fh.write(f"{nct}|{cond_tuple[0]}\n")

    with (out_dir / "sponsors.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("nct_id|lead_or_collaborator|name\n")
        for nct, *_ in AACT_STUDIES:
            for role, name in AACT_SPONSORS.get(nct, []):
                fh.write(f"{nct}|{role}|{name}\n")


# ---------------------------------------------------------------------------
# ICTRP 30-trial fixture
# ---------------------------------------------------------------------------
# 15 overlap with AACT (same NCT IDs), 15 ICTRP-only (various registries).
# ---------------------------------------------------------------------------

def _build_ictrp_rows() -> list[dict]:
    # First 15: overlap with AACT (first 15 NCTs from AACT_STUDIES)
    overlap_rows: list[dict] = []
    for idx, (nct, title, start_dt, enrollment, status, _) in enumerate(AACT_STUDIES[:15]):
        ivs = "; ".join(name for _, name in AACT_INTERVENTIONS.get(nct, []))
        overlap_rows.append({
            "TrialID": nct,
            "Source_Register": "ClinicalTrials.gov",
            "Conditions": "MDR-TB",
            "Secondary_IDs": "",
            "Results_URL": f"https://example.org/results/{nct}" if idx % 2 == 0 else "",
            "Date_registration": start_dt,
            "Countries": "South Africa" if idx % 2 == 0 else "United States",
            "Intervention": ivs,
            "Primary_sponsor": "TB Alliance",
            "Recruitment_Status": status,
            "Public_title": title,
            "Target_size": str(enrollment),
        })

    # Next 15: ICTRP-only trials (various registries, some with exclusion flags)
    ictrp_only: list[dict] = [
        # ISRCTN-registered (overlap secondary NCT with different primary source)
        {"TrialID": "ISRCTN26973455", "Source_Register": "ISRCTN",
         "Conditions": "MDR-TB", "Secondary_IDs": "NCT04207112",
         "Results_URL": "https://www.isrctn.com/ISRCTN26973455",
         "Date_registration": "2017-01-16", "Countries": "South Africa;Belarus;Uzbekistan",
         "Intervention": "Bedaquiline; Pretomanid; Linezolid; Moxifloxacin",
         "Primary_sponsor": "Medecins Sans Frontieres", "Recruitment_Status": "Completed",
         "Public_title": "TB-PRACTECAL ISRCTN-version", "Target_size": "552"},
        # EUCTR-only
        {"TrialID": "EUCTR2018-001234-56", "Source_Register": "EUCTR",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2018-08-12",
         "Countries": "Germany;France", "Intervention": "Bedaquiline; Moxifloxacin",
         "Primary_sponsor": "Charite Berlin", "Recruitment_Status": "Completed",
         "Public_title": "European Bdq plus Mfx Trial", "Target_size": "40"},
        # ChiCTR-only
        {"TrialID": "ChiCTR2000035001", "Source_Register": "ChiCTR",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2020-03-15",
         "Countries": "China", "Intervention": "Linezolid",
         "Primary_sponsor": "Beijing Chest Hospital", "Recruitment_Status": "Completed",
         "Public_title": "Chinese MDR-TB linezolid trial", "Target_size": "100"},
        # CTRI-only
        {"TrialID": "CTRI/2019/04/018700", "Source_Register": "CTRI",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2019-04-01",
         "Countries": "India", "Intervention": "Bedaquiline; Linezolid; Clofazimine",
         "Primary_sponsor": "AIIMS Delhi", "Recruitment_Status": "Completed",
         "Public_title": "Indian MDR-TB Cohort", "Target_size": "200"},
        # NCT-only not in AACT -- South Africa BPaL
        {"TrialID": "NCT03255954", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2017-08-15",
         "Countries": "South Africa", "Intervention": "Bedaquiline; Pretomanid; Linezolid",
         "Primary_sponsor": "TB Alliance", "Recruitment_Status": "Completed",
         "Public_title": "ICTRP-only BPaL South Africa", "Target_size": "85"},
        # NCT-only not in AACT -- Pre-XDR
        {"TrialID": "NCT04199253", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "Pre-XDR Tuberculosis", "Secondary_IDs": "",
         "Results_URL": "https://example.org/results/icaa",
         "Date_registration": "2019-12-15", "Countries": "Russia;Belarus",
         "Intervention": "Bedaquiline; Linezolid; Clofazimine",
         "Primary_sponsor": "USAID", "Recruitment_Status": "Completed",
         "Public_title": "Pre-XDR ICTRP Bdq Trial", "Target_size": "150"},
        # NCT-only not in AACT -- West Africa BPaL
        {"TrialID": "NCT05425971", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2022-09-20",
         "Countries": "Nigeria;Ghana",
         "Intervention": "Bedaquiline; Pretomanid; Linezolid",
         "Primary_sponsor": "EDCTP", "Recruitment_Status": "Recruiting",
         "Public_title": "West Africa BPaL Cohort", "Target_size": "250"},
        # East Africa Lzd dose-finding
        {"TrialID": "NCT04568974", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2020-08-15",
         "Countries": "Ethiopia;Kenya",
         "Intervention": "Linezolid 1200mg; Linezolid 600mg",
         "Primary_sponsor": "AHRI", "Recruitment_Status": "Completed",
         "Public_title": "East Africa Lzd dose-finding", "Target_size": "120"},
        # Pa+Lzd RR-TB cohort
        {"TrialID": "NCT04875620", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "RR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2021-03-15",
         "Countries": "South Africa",
         "Intervention": "Pretomanid; Linezolid",
         "Primary_sponsor": "Stellenbosch University", "Recruitment_Status": "Recruiting",
         "Public_title": "Pa plus Lzd RR-TB Cohort", "Target_size": "90"},
        # Pediatric (should be excluded)
        {"TrialID": "NCT05176295", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2021-12-10",
         "Countries": "South Africa",
         "Intervention": "Bedaquiline; Pretomanid; Linezolid",
         "Primary_sponsor": "IMPAACT", "Recruitment_Status": "Recruiting",
         "Public_title": "Pediatric BPaL Africa (excluded)", "Target_size": "60"},
        # Pre-2012 (should be excluded)
        {"TrialID": "NCT01215159", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2010-12-15",
         "Countries": "South Africa", "Intervention": "Linezolid",
         "Primary_sponsor": "Stellenbosch University", "Recruitment_Status": "Completed",
         "Public_title": "Pre-2012 trial (excluded)", "Target_size": "50"},
        # DS-TB no target drug (should be excluded)
        {"TrialID": "NCT04062345", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "Drug-Sensitive Tuberculosis", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2019-09-15",
         "Countries": "Brazil;South Africa",
         "Intervention": "Rifapentine; Moxifloxacin",
         "Primary_sponsor": "CDC", "Recruitment_Status": "Completed",
         "Public_title": "DS-TB rifapentine (excluded no Bdq Pa Lzd)", "Target_size": "2500"},
        # Uganda-Tanzania cohort
        {"TrialID": "NCT04999001", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2021-06-01",
         "Countries": "Uganda;Tanzania",
         "Intervention": "Bedaquiline; Linezolid",
         "Primary_sponsor": "Makerere University", "Recruitment_Status": "Recruiting",
         "Public_title": "Uganda-Tanzania Bdq plus Lzd Cohort", "Target_size": "75"},
        # Nigeria RR-TB BPaL
        {"TrialID": "NCT05000888", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "Rifampicin-Resistant Tuberculosis", "Secondary_IDs": "",
         "Results_URL": "https://example.org/results/rr-tb",
         "Date_registration": "2021-08-20", "Countries": "Nigeria",
         "Intervention": "Bedaquiline; Pretomanid; Linezolid",
         "Primary_sponsor": "EDCTP", "Recruitment_Status": "Completed",
         "Public_title": "Nigeria RR-TB Cohort BPaL", "Target_size": "110"},
        # India Pa+Lzd cohort
        {"TrialID": "NCT05100200", "Source_Register": "ClinicalTrials.gov",
         "Conditions": "MDR-TB", "Secondary_IDs": "",
         "Results_URL": "", "Date_registration": "2021-09-01",
         "Countries": "India",
         "Intervention": "Pretomanid; Linezolid",
         "Primary_sponsor": "ICMR", "Recruitment_Status": "Recruiting",
         "Public_title": "India Pa plus Lzd Cohort", "Target_size": "95"},
    ]

    all_rows = overlap_rows + ictrp_only
    assert len(all_rows) == 30, f"ICTRP rows must be exactly 30, got {len(all_rows)}"
    return all_rows


def _write_ictrp(out_path: Path) -> None:
    rows = _build_ictrp_rows()
    df = pd.DataFrame(rows, columns=[
        "TrialID", "Source_Register", "Conditions", "Secondary_IDs",
        "Results_URL", "Date_registration", "Countries", "Intervention",
        "Primary_sponsor", "Recruitment_Status", "Public_title", "Target_size",
    ])
    df.to_csv(out_path, index=False, lineterminator="\n")


# ---------------------------------------------------------------------------
# Pairwise70 micro parquet
# ---------------------------------------------------------------------------

def _write_pairwise70(out_path: Path) -> None:
    """8 rows linking fixture NCTs/ISRCTNs to fake Cochrane review IDs."""
    df = pd.DataFrame([
        {"review_id": "CD001234", "nct_id": "NCT04340700", "isrctn_id": ""},
        {"review_id": "CD001234", "nct_id": "NCT02333799", "isrctn_id": ""},
        {"review_id": "CD001235", "nct_id": "NCT03086486", "isrctn_id": "ISRCTN26973455"},
        {"review_id": "CD001235", "nct_id": "NCT04207112", "isrctn_id": "ISRCTN26973455"},
        {"review_id": "CD001236", "nct_id": "NCT02573350", "isrctn_id": ""},
        {"review_id": "CD001237", "nct_id": "NCT04114669", "isrctn_id": ""},
        {"review_id": "CD001238", "nct_id": "NCT01691534", "isrctn_id": ""},
        {"review_id": "CD001238", "nct_id": "NCT03237203", "isrctn_id": ""},
    ], columns=["review_id", "nct_id", "isrctn_id"])
    df.to_parquet(out_path, index=False)


# ---------------------------------------------------------------------------
# CDSR string micro sqlite
# ---------------------------------------------------------------------------

def _write_cdsr_sqlite(out_path: Path) -> None:
    """4-review CDSR string index for cochrane_match smoke-testing."""
    if out_path.exists():
        out_path.unlink()
    conn = sqlite3.connect(out_path)
    conn.executescript("""
        CREATE TABLE review_strings (review_id TEXT, body_text TEXT);
        INSERT INTO review_strings VALUES
            ('CD001239', 'Smith 2019; BPaL Phase 3 ZeNix in MDR-TB'),
            ('CD001240', 'TB-PRACTECAL bedaquiline pretomanid linezolid moxifloxacin trial'),
            ('CD001241', 'BPaL Implementation Study evidence summary'),
            ('CD001242', 'Linezolid Dose Optimisation arm review');
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate deterministic integration fixtures for africa-tb-atlas."
    )
    ap.add_argument("--out-dir", default="tests/fixtures", type=Path,
                    help="Root directory to write fixtures into (default: tests/fixtures)")
    args = ap.parse_args(argv)
    out = args.out_dir.resolve()
    print(f"Writing fixtures to {out}")

    _write_aact(out / "aact_50trial")
    print("  aact_50trial/: 5 pipe-delimited files, 50 studies")

    _write_ictrp(out / "ictrp_30trial.csv")
    print("  ictrp_30trial.csv: 30 trials")

    _write_pairwise70(out / "pairwise70_micro.parquet")
    print("  pairwise70_micro.parquet: 8 references")

    _write_cdsr_sqlite(out / "cdsr_string_micro.sqlite")
    print("  cdsr_string_micro.sqlite: 4 reviews")

    return 0


if __name__ == "__main__":
    sys.exit(main())
