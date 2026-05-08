import json
from pathlib import Path
from unittest.mock import patch
import pytest

from tb_atlas.publication_match import (
    lookup_publication, lookup_publication_by_isrctn,
    Gate2Verdict, LookupFailed,
    _query_url,
)


def _epmc_response(pmids: list[str]) -> dict:
    """Build a fake Europe PMC search response."""
    return {
        "resultList": {
            "result": [{"id": f"PMID:{p}", "pmid": p, "source": "MED"} for p in pmids]
        }
    }


def test_query_url_uses_correct_src_filter():
    """Bug-6 sanity: query MUST include SRC:MED or SRC:PMC, NOT SRC:CLINICALTRIALS."""
    url = _query_url("NCT04207112")
    assert "SRC:MED" in url or "SRC%3AMED" in url
    assert "SRC:CLINICALTRIALS" not in url
    assert "SRC%3ACLINICALTRIALS" not in url


@patch("tb_atlas.publication_match._http_get")
def test_lookup_publication_returns_pmid_when_found(mock_get, tmp_path):
    mock_get.return_value = _epmc_response(["12345"])
    verdict = lookup_publication("NCT04207112", tmp_path)
    assert verdict.published is True
    assert verdict.pmid == "12345"
    assert verdict.ambiguous is False
    assert verdict.lookup_failed is False


@patch("tb_atlas.publication_match._http_get")
def test_lookup_publication_returns_unpublished_when_empty(mock_get, tmp_path):
    mock_get.return_value = _epmc_response([])
    verdict = lookup_publication("NCT00000000", tmp_path)
    assert verdict.published is False
    assert verdict.pmid is None


@patch("tb_atlas.publication_match._http_get")
def test_lookup_publication_marks_ambiguous_on_multiple_pmids(mock_get, tmp_path):
    """Multiple PMIDs → ambiguous=True; primary verdict picks lowest PMID."""
    mock_get.return_value = _epmc_response(["54321", "12345", "98765"])
    verdict = lookup_publication("NCT04207112", tmp_path)
    assert verdict.published is True
    assert verdict.pmid == "12345"  # lowest
    assert verdict.ambiguous is True


@patch("tb_atlas.publication_match._http_get")
def test_lookup_publication_uses_cache(mock_get, tmp_path):
    """Second call reads cache, doesn't hit HTTP."""
    mock_get.return_value = _epmc_response(["12345"])
    v1 = lookup_publication("NCT04207112", tmp_path)
    v2 = lookup_publication("NCT04207112", tmp_path)
    assert v1.pmid == v2.pmid == "12345"
    assert mock_get.call_count == 1  # only first call hits HTTP


@patch("tb_atlas.publication_match._http_get")
def test_lookup_publication_lookup_failed_sets_flag(mock_get, tmp_path):
    """HTTP failure after retries → lookup_failed=True, published=False."""
    mock_get.side_effect = LookupFailed("network error")
    verdict = lookup_publication("NCT04207112", tmp_path)
    assert verdict.published is False
    assert verdict.lookup_failed is True


@patch("tb_atlas.publication_match._http_get")
def test_lookup_by_isrctn_returns_pmid_when_found(mock_get, tmp_path):
    """ISRCTN-direct lookup uses same query template, returns pmid."""
    mock_get.return_value = _epmc_response(["67890"])
    verdict = lookup_publication_by_isrctn("ISRCTN26973455", tmp_path)
    assert verdict.published is True
    assert verdict.pmid == "67890"


@patch("tb_atlas.publication_match._http_get")
def test_lookup_by_isrctn_caches_under_isrctn_key(mock_get, tmp_path):
    """Cache file should be ISRCTN26973455.json (not NCT*)."""
    mock_get.return_value = _epmc_response(["67890"])
    lookup_publication_by_isrctn("ISRCTN26973455", tmp_path)
    cache_file = tmp_path / "ISRCTN26973455.json"
    assert cache_file.exists()
    assert json.loads(cache_file.read_text())["resultList"]["result"][0]["pmid"] == "67890"


@patch("tb_atlas.publication_match._http_get")
def test_isrctn_and_nct_caches_independent(mock_get, tmp_path):
    """ISRCTN cache != NCT cache (different filenames)."""
    mock_get.return_value = _epmc_response(["12345"])
    lookup_publication("NCT04207112", tmp_path)
    mock_get.return_value = _epmc_response(["67890"])
    lookup_publication_by_isrctn("ISRCTN26973455", tmp_path)
    assert (tmp_path / "NCT04207112.json").exists()
    assert (tmp_path / "ISRCTN26973455.json").exists()
    assert mock_get.call_count == 2


def test_gate2_verdict_dataclass_frozen():
    """Verdict should be hashable/immutable."""
    v = Gate2Verdict(published=True, pmid="12345")
    assert v.published is True
    assert v.pmid == "12345"
    # Try to mutate — should raise
    with pytest.raises((AttributeError, Exception)):
        v.published = False
