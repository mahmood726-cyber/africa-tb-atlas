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

---

## 2026-05-08 (later) — Sentinel skip-file marker on docs/spec.md (post-prereg amendment)

**Decision affected:** None of the 19 locked-at-spec analytical decisions in §1.6. This amendment is purely tooling metadata — it does NOT alter the analytical contract.

**Change:** Added a `<!-- sentinel:skip-file -->` HTML comment at the top of `docs/spec.md` so Sentinel's `P0-hardcoded-local-path` rule does not flag the spec document. Rationale embedded in the comment: the spec contains absolute local paths as descriptive content (data locations at §2.4, project layout at §1.1, sister-project references at §8) — not application configuration. Same legitimate-paths-as-data pattern as `C:\E156\rewrite-workbook.txt`.

**Justification:** Before this marker, Sentinel reported BLOCK=5 on `docs/spec.md` lines 21, 153, 424, 450, 451. Three resolution paths were considered:
1. Add `sentinel:skip-file` marker with documented rationale (chosen)
2. Refactor spec to use placeholder paths (would degrade the spec's usefulness as a session-resumption document)
3. Tune Sentinel's rule to globally exclude `docs/` (changes Sentinel project-wide; over-broad)

Option 1 is the narrowest fix. The marker explicitly documents the rationale so future readers understand why the file is exempt. After this amendment, Sentinel reports BLOCK=0 — clearing the path for the Task 34 mode-switch from warn → block at v0.1.0.

**Side-effect on prereg integrity:** The marker is plain HTML comment bytes prepended to spec.md; no analytical content changed. However, `sha256(docs/spec.md)` changed from `23a5c9b1b5799238...` to `b14056a02700784e...`. `data/snapshots/prereg_manifest.json` updated in this commit to reflect the new sha256. The original `prereg-v0.0.1` tag remains immutable in git history at commit `a9b6485`, anchoring the original spec content for any future audit.

**Affected files in this amendment commit:**
- `docs/spec.md` — `<!-- sentinel:skip-file -->` HTML comment prepended
- `docs/AMENDMENTS.md` — this entry
- `data/snapshots/prereg_manifest.json` — updated sha256 for docs/spec.md and docs/AMENDMENTS.md

**Validation gates re-run:** Sentinel scan (BLOCK=0 confirmed). verify_prereg.py (passes against updated manifest). All 246 pytest tests still pass.
