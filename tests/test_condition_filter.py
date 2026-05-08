import pytest
from tb_atlas.condition_filter import is_drug_resistant_tb

@pytest.mark.parametrize("conditions,expected", [
    (["Multidrug-Resistant Tuberculosis"], True),
    (["MDR-TB"], True),
    (["MDR Tuberculosis"], True),
    (["MDR TB"], True),
    (["Extensively Drug-Resistant Tuberculosis"], True),
    (["XDR-TB"], True),
    (["XDR TB"], True),
    (["Pre-XDR Tuberculosis"], True),
    (["Pre-XDR-TB"], True),
    (["Rifampicin-Resistant Tuberculosis"], True),
    (["Rifampin-Resistant Tuberculosis"], True),
    (["RR-TB"], True),
    (["RR TB"], True),
    (["Tuberculosis, Pulmonary"], False),       # generic TB, not DR
    (["Drug-Sensitive Tuberculosis"], False),
    (["Latent TB Infection"], False),
    (["HIV-Tuberculosis Co-infection"], False),  # ambiguous; default False
    (["MDR-TB", "HIV"], True),                   # any DR-TB term wins
    ([], False),
    (None, False),
])
def test_is_drug_resistant_tb(conditions, expected):
    assert is_drug_resistant_tb(conditions) is expected
