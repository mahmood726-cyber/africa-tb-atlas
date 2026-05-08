"""Path configuration loader. Single source of truth for external paths.

TOML format is flat (no sections):

    aact_snapshot_dir    = "/path/to/aact/dir/"
    ictrp_snapshot       = "/path/to/ictrp.csv"
    pairwise70_index     = "/path/to/study_references.parquet"
    cdsr_string_index    = "/path/to/cdsr_string_index.sqlite"
    europe_pmc_cache_dir = "/path/to/cache/"   # created on demand

All paths must already exist on disk except europe_pmc_cache_dir, which is
created if absent.  aact_snapshot_dir must be a directory; ictrp_snapshot,
pairwise70_index, and cdsr_string_index must be files.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when paths.toml is missing, malformed, or references absent paths."""


@dataclass(frozen=True)
class Paths:
    aact_snapshot_dir: Path
    ictrp_snapshot: Path
    pairwise70_index: Path
    cdsr_string_index: Path
    europe_pmc_cache_dir: Path


# Public: downstream tests/scripts can introspect which keys are required.
REQUIRED_KEYS: tuple[str, ...] = (
    "aact_snapshot_dir",
    "ictrp_snapshot",
    "pairwise70_index",
    "cdsr_string_index",
    "europe_pmc_cache_dir",
)

# Per-key existence semantics:
#   "dir"         — must already exist and be a directory
#   "file"        — must already exist and be a file
#   "cache_dir"   — created on demand (mkdir parents=True)
_KEY_KIND: dict[str, str] = {
    "aact_snapshot_dir": "dir",
    "ictrp_snapshot": "file",
    "pairwise70_index": "file",
    "cdsr_string_index": "file",
    "europe_pmc_cache_dir": "cache_dir",
}


def load_paths(toml_path: Path) -> Paths:
    """Load and validate a flat paths.toml, returning a frozen Paths dataclass.

    Raises ConfigError on any of:
    - toml_path does not exist
    - a required key is absent from the TOML
    - a referenced path does not exist (except europe_pmc_cache_dir)
    - aact_snapshot_dir exists but is not a directory
    - ictrp_snapshot / pairwise70_index / cdsr_string_index exist but are not files
    """
    if not toml_path.exists():
        raise ConfigError(f"paths.toml not found at {toml_path}")

    with toml_path.open("rb") as fh:
        raw = tomllib.load(fh)

    # Pass 1: check all required keys are present before validating paths.
    # This ensures a "missing key" error names the absent key, not a
    # path-existence error for an unrelated key that happened to be listed first.
    for key in REQUIRED_KEYS:
        if key not in raw:
            raise ConfigError(
                f"missing required key '{key}' in {toml_path}"
            )

    # Pass 2: validate and resolve paths.
    fields: dict[str, Path] = {}

    for key in REQUIRED_KEYS:
        p = Path(raw[key]).expanduser()
        kind = _KEY_KIND[key]

        if kind == "cache_dir":
            p.mkdir(parents=True, exist_ok=True)
        elif kind == "dir":
            if not p.exists():
                raise ConfigError(
                    f"aact_snapshot_dir does not exist: {p}"
                )
            if not p.is_dir():
                raise ConfigError(
                    f"aact_snapshot_dir is not a directory: {p}"
                )
        else:  # "file"
            if not p.exists():
                raise ConfigError(
                    f"referenced path missing for '{key}': {p}"
                )
            if not p.is_file():
                raise ConfigError(
                    f"referenced path for '{key}' is not a file: {p}"
                )

        fields[key] = p

    return Paths(**fields)
