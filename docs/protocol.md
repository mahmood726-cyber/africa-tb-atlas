# africa-tb-atlas — Protocol

**OTS-stamped:** [pending Task 6]
**Spec sha256:** [auto-filled by verify_prereg.py]

## Pre-extraction protocol

1. spec.md and protocol.md OTS-stamped on 3 calendars (a-pool, b-pool, finney/eternitywall) BEFORE any extraction.
2. Snapshots sha256-pinned in `data/snapshots/*_metadata.json`.
3. `pilots/preflight.py` runs first, fails closed on missing prerequisites.
4. Full pipeline runs end-to-end via `pilots/run_all.py`.

## Pre-ship validation gates (fail-closed)

1. Snapshot sha256 match against `*_metadata.json`.
2. TrialScout sanity: G0→G2 ≥53.6% (one-sided; high values OK).
3. 30-trial blinded G3 spot-check: ≥27/30 verdict-level agreement (else re-frame as methodology-calibration paper, PACTR-Hiddenness Amendment 2 precedent).
4. Sentinel pre-push BLOCK=0.
5. atlas.csv sha256 stamped on 3 OTS calendars.

## Spot-check sampling

- seed = 20260507
- stratified: 10 africa_recruiting=True / 20 africa_recruiting=False
- blinded auditor sees: trial_id, NCT, ISRCTN, title, lead_sponsor, africa_recruiting
- auditor does NOT see: G1/G2/G3 algorithm verdicts
- merge happens via `scripts/merge_spotcheck.py`

## Amendments

Any change to the 19 locked-at-spec decisions in spec.md §1.6 requires:
1. New OTS-stamped commit
2. Entry in AMENDMENTS.md with date, decision-id, change, justification
3. Re-run of any affected validation gate
