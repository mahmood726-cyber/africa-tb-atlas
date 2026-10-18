# africa-tb-atlas

4-gate Cochrane-inclusion audit of modern MDR/XDR-TB regimen trials
(bedaquiline/pretomanid/linezolid post-2012-12-28).

Sister to [pactr-hiddenness-atlas](https://github.com/mahmood726-cyber/pactr-hiddenness-atlas).

**Status:** in development. v0.1.0 target Q3 2026.

## Spec

`docs/spec.md` (OTS-stamped before any extraction)

## Quick start

```bash
pip install -e .
cp paths.toml.example paths.toml  # then edit local paths
python -m pilots.preflight
python -m pilots.run_all --fixture-mode  # smoke test
```

## Data and release checks

Registry deduplication accepts filtered or repeated dataframe index labels and
does not match missing identifiers. Missing pandas values and null-text markers
do not count as posted results.

Run the release dry-run with `python scripts/release_v010.py` on Windows or
POSIX systems. Skipped research prerequisites still mean release is pending.
Attributes exceptions for `docs/AMENDMENTS.md`, `atlas.csv` and
`atlas_baseline.csv` preserve their original CRLF bytes and existing hashes;
registered content, data values and hash manifests have not changed.

## License

MIT — see LICENSE.
