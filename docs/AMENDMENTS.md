# Amendments

## 2026-05-08 — Pre-registration mechanism: Bitcoin OTS → GitHub tag + IA snapshot

**Decision affected:** Original spec §4.3 + §6.2 specified pre-registration via Bitcoin OpenTimestamps (OTS) on 3 calendars (a-pool, b-pool, finney/eternitywall).

**Change:** Replaced with signed GitHub tag (`prereg-v0.0.1`) + Internet Archive Wayback snapshot.

**Justification:** For a single-author atlas at this scale, GitHub tag + IA provides sufficient timestamping rigor (two independent third-party witnesses to file content + creation time). Bitcoin OTS was the canonical sister-atlas (PACTR-Hiddenness) approach and provides stronger third-party-verifiable timestamps via the Bitcoin chain, but is overkill for the use case here (defending against post-hoc spec tweaking by the author against reviewer audit). The Bitcoin OTS path also has a known Windows + Python 3.13 setup tax (`ots` CLI fails to load libeay32 via python-bitcoinlib). GitHub + IA is two independent witnesses with near-zero infrastructure cost.

**Made before any data extraction.** This amendment is recorded BEFORE the `prereg-v0.0.1` tag is pushed, so it is part of the locked spec — not a post-hoc revision.

**Affected files in this amendment commit:**
- `docs/spec.md` — §0, §1.6, §2.1 layout, §3 data-flow gate 5, §4.3 (rewritten), §4.9, §5.1 deliverables, §5.6, §5.8 #6, §5.9, §6.2
- `docs/protocol.md` — full rewrite of header, §1, §5
- `docs/AMENDMENTS.md` — this entry

**Validation gates re-run:** none affected; the validation gates (snapshot sha256 match, TrialScout sanity, spot-check, Sentinel BLOCK=0, atlas.csv tagging) are mechanism-agnostic.
