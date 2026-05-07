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

## License

MIT — see LICENSE.
