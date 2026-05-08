# africa-tb-atlas — Protocol

**Pre-registered via:** signed GitHub tag `prereg-v0.0.1` + Internet Archive Wayback snapshot
**GitHub repo:** `github.com/mahmood726-cyber/africa-tb-atlas`
**Spec sha256:** [recorded in `data/snapshots/prereg_manifest.json`; verified by `scripts/verify_prereg.py`]
**IA snapshot URLs:** [recorded in `data/snapshots/internet_archive_prereg.json`]

## Pre-extraction protocol

1. spec.md and protocol.md committed + GitHub repo created (public).
2. Tag `prereg-v0.0.1` created at the commit that holds the locked spec; tag pushed to GitHub.
3. Internet Archive snapshot of raw spec.md and protocol.md GitHub blob URLs requested via `web.archive.org/save/<URL>`; resulting Wayback URLs recorded in `data/snapshots/internet_archive_prereg.json`.
4. Snapshots sha256-pinned in `data/snapshots/*_metadata.json` (this happens at Task 6, after prereg, since snapshot integrity is about the input data not the protocol).
5. `pilots/preflight.py` runs first, fails closed on missing prerequisites.
6. Full pipeline runs end-to-end via `pilots/run_all.py`.

## Pre-ship validation gates (fail-closed)

1. Snapshot sha256 match against `*_metadata.json`.
2. TrialScout sanity: G0→G2 ≥53.6% (one-sided; high values OK).
3. 30-trial blinded G3 spot-check: ≥27/30 verdict-level agreement (else re-frame as methodology-calibration paper, PACTR-Hiddenness Amendment 2 precedent).
4. Sentinel pre-push BLOCK=0.
5. atlas.csv tagged at `v0.1.0` (immutable in git history) and IA-snapshotted; sha256 recorded in `data/snapshots/output_baselines.json`.

## Spot-check sampling

- seed = 20260507
- stratified: 10 africa_recruiting=True / 20 africa_recruiting=False
- blinded auditor sees: trial_id, NCT, ISRCTN, title, lead_sponsor, africa_recruiting
- auditor does NOT see: G1/G2/G3 algorithm verdicts
- merge happens via `scripts/merge_spotcheck.py`

## Amendments

Any change to the 19 locked-at-spec decisions in spec.md §1.6 requires:
1. New commit (the prior tag remains immutable in git history)
2. Entry in AMENDMENTS.md with date, decision-id, change, justification
3. Optional new tag (e.g. `prereg-v0.1.0-amend-1`) + IA snapshot of the amended spec
4. Re-run of any affected validation gate
