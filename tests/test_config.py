import pytest
from pathlib import Path
from tb_atlas.config import load_paths, REQUIRED_KEYS, ConfigError, Paths


def _write_full_toml(tmp_path: Path) -> Path:
    """Write a paths.toml with all 5 required keys pointing at existing paths."""
    aact_dir = tmp_path / "aact"
    aact_dir.mkdir()
    ictrp_file = tmp_path / "ictrp.csv"
    ictrp_file.write_text("col1,col2\n1,2\n")
    p70 = tmp_path / "p70.parquet"
    p70.write_bytes(b"\x00\x01")  # placeholder; load_paths only checks existence
    cdsr = tmp_path / "cdsr.sqlite"
    cdsr.write_bytes(b"\x00\x01")
    cache_dir = tmp_path / "cache"  # may not exist; load_paths creates it
    cfg = tmp_path / "paths.toml"
    cfg.write_text(
        f'aact_snapshot_dir = "{aact_dir.as_posix()}"\n'
        f'ictrp_snapshot = "{ictrp_file.as_posix()}"\n'
        f'pairwise70_index = "{p70.as_posix()}"\n'
        f'cdsr_string_index = "{cdsr.as_posix()}"\n'
        f'europe_pmc_cache_dir = "{cache_dir.as_posix()}"\n'
    )
    return cfg


def test_load_paths_returns_paths_dataclass(tmp_path):
    cfg = _write_full_toml(tmp_path)
    paths = load_paths(cfg)
    assert isinstance(paths, Paths)
    for key in REQUIRED_KEYS:
        assert hasattr(paths, key), f"missing field: {key}"


def test_required_keys_includes_aact_and_ictrp(tmp_path):
    assert "aact_snapshot_dir" in REQUIRED_KEYS
    assert "ictrp_snapshot" in REQUIRED_KEYS
    assert "pairwise70_index" in REQUIRED_KEYS
    assert "cdsr_string_index" in REQUIRED_KEYS
    assert "europe_pmc_cache_dir" in REQUIRED_KEYS
    assert len(REQUIRED_KEYS) == 5


def test_load_paths_fails_closed_on_missing_key(tmp_path):
    cfg = tmp_path / "paths.toml"
    cfg.write_text('aact_snapshot_dir = "/x"\n')
    with pytest.raises(ConfigError) as exc:
        load_paths(cfg)
    assert "ictrp_snapshot" in str(exc.value).lower() or "missing" in str(exc.value).lower()


def test_load_paths_fails_on_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_paths(tmp_path / "does_not_exist.toml")


def test_load_paths_creates_cache_dir(tmp_path):
    cfg = _write_full_toml(tmp_path)
    cache_dir = tmp_path / "cache"
    assert not cache_dir.exists()
    paths = load_paths(cfg)
    assert cache_dir.exists()
    assert paths.europe_pmc_cache_dir == cache_dir


def test_load_paths_fails_when_aact_dir_missing(tmp_path):
    cfg = _write_full_toml(tmp_path)
    # Delete the aact dir AFTER writing the toml
    aact_dir = tmp_path / "aact"
    aact_dir.rmdir()
    with pytest.raises(ConfigError) as exc:
        load_paths(cfg)
    assert "aact" in str(exc.value).lower()
