import pytest
from tb_atlas.population_filter import is_adult_or_adolescent


@pytest.mark.parametrize("title,expected", [
    ("BPaL Phase 3 in Adults", True),
    ("Pediatric BPaL", False),
    ("Children with MDR-TB", False),
    ("Adolescent and Adult Bdq trial", True),
    ("Infants and Children", False),
    ("MDR-TB in Adults Aged ≥18", True),
    ("Paediatric MDR-TB Trial", False),
    ("Adult Pretomanid Study", True),
    ("MDR-TB Treatment Trial", True),  # no peds keywords; default include
    ("", True),  # empty title; default include
])
def test_is_adult_or_adolescent(title, expected):
    assert is_adult_or_adolescent(title) is expected
