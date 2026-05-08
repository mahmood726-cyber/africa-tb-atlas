# africa-tb-atlas — Design Spec

**Date:** 2026-05-07
**Status:** Brainstorming complete; awaiting user approval before transition to writing-plans skill.
**Source idea:** `C:/ProjectIndex/long-term-plan/ideas.yaml::africa-tb-atlas` (rank #2; objective `q3-2026-canon-3-atlases`).
**Sister projects** (template / reuse source): pactr-hiddenness-atlas (97 tests, v0.1.0 shipped 2026-05-05), trial-truthfulness-atlas, repro-floor-atlas, malaria-ct-recon, ARAC.

---

## 0. Summary (one paragraph)

The African TB Trial Atlas audits the Cochrane-inclusion pipeline for **modern MDR/XDR-TB regimen trials** — defined as trials of any regimen containing **bedaquiline, pretomanid, or linezolid** with start_date ≥ **2012-12-28** (bedaquiline FDA-EUA). The atlas builds a global denominator of ~150–300 such trials from AACT (CT.gov) ∪ ICTRP (WHO weekly export, deduped on NCT/ISRCTN/EUCTR), classifies each trial by African-site presence (binary headline + site-share + three-tier sensitivity), runs each trial through a 4-gate funnel (registered → results-posted → peer-published → in-Cochrane), and reports both **trial-weighted** and **patient-weighted** Cochrane-inclusion rates stratified by Africa-recruiting vs not. The atlas is pre-registered via a signed GitHub tag (`prereg-v0.0.1`) plus Internet Archive snapshot of the spec and protocol, and validated via a 30-trial blinded spot-check on the headline G3 gate. Target deliverable: Synthēsis E156 micro-paper + Methods Note at v0.1.0, on or before the Q3-2026 OKR deadline.

---

## 1. Scope and analytical contract

### 1.1 Project name and location

- **Project name:** `africa-tb-atlas`
- **Local path:** `C:\Projects\africa-tb-atlas\`
- **GitHub:** `github.com/mahmood726-cyber/africa-tb-atlas` (public)
- **Pages:** `mahmood726-cyber.github.io/africa-tb-atlas/`

### 1.2 Headline question

> *Of the modern MDR/XDR-TB regimen trials run since bedaquiline approval, what fraction reach a Cochrane synthesis — and how does that fraction differ between trials with African sites and trials run entirely outside Africa?*

### 1.3 4-gate funnel (per-trial)

| Gate | Question | Source |
|---|---|---|
| **G0** Registered | Trial is in AACT or ICTRP, started ≥ 2012-12-28, intervention contains ≥1 of {bedaquiline, pretomanid, linezolid}, condition is MDR/pre-XDR/XDR/RR-TB, adult/adolescent | AACT + ICTRP weekly export |
| **G1** Results-posted | CT.gov `results_first_posted_date` non-null OR ICTRP `result_url` resolves to a results page | AACT + ICTRP |
| **G2** Peer-published | Europe PMC search returns ≥1 publication tied to the NCT/ISRCTN ID using `EXT_ID:NCT* AND (SRC:MED OR SRC:PMC)` (Bug-6-fixed query from PACTR-Hiddenness) | Europe PMC API |
| **G3** In Cochrane | NCT/ISRCTN appears in Pairwise70 `study_references` parquet OR matches via CDSR string-index | Pairwise70 + CDSR |

### 1.4 Stratification

Every trial gets one of `{africa_recruiting=True, africa_recruiting=False}` from AACT `facilities.country` (with ICTRP `countries` fallback). No fuzzy country matching — ISO-3166 alpha-2 only. 54 African codes hardcoded (`iso3166` package + curated list).

### 1.5 Headline metrics (atlas.csv minimum spec)

For each of the 2 strata, report:
- `n_trials`, `n_results_posted`, `n_peer_published`, `n_in_cochrane`
- `n_invisible` = trials in the denominator lacking BOTH NCT AND ISRCTN (registered only in EUCTR or other secondary registries; functionally invisible to most synthesis pipelines because Cochrane CDSR predominantly references NCT/ISRCTN)
- `n_participants` summed across each gate (patient-weighted twin)
- `pct_g0_to_g3` (trial-weighted) and `pct_g0_to_g3_pat` (patient-weighted)
- 95% CI on G0→G3 rate via cluster bootstrap (cluster = lead sponsor); undefined if k<3

### 1.6 Locked-at-spec decisions (HARK protection)

These freeze on the git-tagged spec (tag `prereg-v0.0.1` pushed to GitHub + IA-snapshot before any extraction) and DO NOT change after data extraction. Any change requires a new commit + AMENDMENTS.md entry; the prior tag remains in the repo as immutable history and the prior IA snapshot remains accessible at the recorded Wayback URL.

1. Intervention list: bedaquiline, pretomanid, linezolid (positive list); plus brand names (Sirturo, Dovprela, Zyvox, Linox, Linospan, etc); plus pretomanid code names (PA-824 only — TBA-354 is a separate confusable, on negative list)
2. Time window: trial `start_date ≥ 2012-12-28` (bedaquiline FDA-EUA)
3. Drug-resistance scope: MDR + pre-XDR + XDR + RR-TB. DS-TB only if regimen contains ≥1 of the 3 drugs (rare; documented in extraction_audit.md)
4. Population scope: adult + adolescent (≥12y or per-trial-defined). Pure pediatric trials (IMPAACT, SHINE, TB-CHAMP) excluded
5. Africa-recruiting headline: binary, ≥1 African site
6. Africa-recruiting sensitivity (pre-registered): site-share ≥30% threshold
7. Africa-recruiting Section-3 sub-analysis: three-tier {African-led ≥50% sites OR PI-affiliation, African-recruiting ≥1 site & <50%, non-Africa}
8. Drug-class taxonomy (8 levels): {BPaL, BPaLM, Bdq+other-companion, Pa+Lzd (no Bdq), Lzd dose-finding, Bdq monotherapy/pair, Pa monotherapy/pair, other}
9. Cochrane-match (G3): union of {NCT-bridge in Pairwise70, ISRCTN-bridge in Pairwise70, CDSR string-index title-match}. The trial is in_cochrane=True if ANY of the three matches. Per-component flags tracked separately in trials.parquet for audit; ensemble-disagreement reported in extraction_audit.md (ship gate <5%)
10. Headline metric: `pct_g0_to_g3` (trial-weighted) AND `pct_g0_to_g3_pat` (patient-weighted)
11. Cluster bootstrap: cluster = lead sponsor; undefined when k<3
12. TrialScout sanity check: G0→G2 should sit near 63.6% baseline. **One-sided** — only flag if much LOWER. High publication rates are expected (TB Alliance/USAID/EDCTP funding) and not a failure
13. Pre-ship validation: 30-trial blinded spot-check on G3 only, ≥27/30 verdict-level agreement (PACTR-Hiddenness lesson: G1/G2 over-broadness is acceptable; G3 is the headline)
14. Country classification: ISO-3166 alpha-2 only. No fuzzy match. Unknown country → fail closed (logged)
15. Snapshot reproducibility: every external snapshot sha256-pinned in `data/snapshots/*_metadata.json`
16. Spot-check sampling: stratified, seed=20260507. 10 africa_recruiting=True / 20 africa_recruiting=False (rare class oversampled)
17. atlas.csv structure: ≤12 rows = 2 strata × 3 sensitivity defs (binary, site-share-30, three-tier-headline) + drug-class breakdown
18. Patient-weighted denominator: `enrollment` null on a trial → drop from patient-weighted denominator, keep in trial-weighted (logged)
19. Ensemble disagreement: pre-ship gate at <5% (NCT-bridge vs CDSR string disagreement)

### 1.7 Non-goals (NOT in v0.1.0 scope)

- No effect-size pooling. The atlas does not compute a TB MA — it audits which trials reach existing Cochrane MAs.
- No within-trial cohort dropout extraction. (This is theme B from the original idea entry; deferred to v0.3.0.)
- No PACTR registry scrape (covered by PACTR-Hiddenness Atlas).
- No pediatric MDR-TB trials.
- No risk-of-bias coding.
- No publication-bias adjustment (Egger / PET-PEESE) — deferred to v0.3.0.

---

## 2. Architecture

### 2.1 Top-level layout

```
africa-tb-atlas/
├── README.md, LICENSE (MIT), pyproject.toml
├── paths.toml.example          (committed)
├── paths.toml                  (gitignored)
├── index.html                  (Pages root, redirects to dashboard/)
├── atlas.csv                   (committed at v0.1.0, sha256-pinned)
├── atlas_baseline.csv          (committed)
├── docs/
│   ├── spec.md                 (git-tag prereg-v0.0.1 + IA snapshot BEFORE extraction)
│   ├── protocol.md             (git-tag prereg-v0.0.1 + IA snapshot sister doc)
│   ├── extraction_audit.md     (methodological caveats)
│   └── AMENDMENTS.md
├── data/
│   ├── snapshots/              (committed: *_metadata.json with sha256 of off-repo snapshots)
│   ├── processed/              (gitignored: spotcheck_*.csv, intervention_audit.csv, dedup_log.csv)
│   └── output/                 (gitignored intermediate parquets)
├── src/tb_atlas/               (15 modules; see 2.2)
├── pilots/
│   ├── preflight.py            (fail-closed prereq gate)
│   └── run_all.py              (end-to-end orchestrator)
├── scripts/                    (build_data_assets, stamp_file, release_v010, fill_paper_placeholders, merge_spotcheck, verify_prereg, aact_extract, ictrp_extract)
├── tests/                      (unit + integration; fixtures/ subdir)
├── dashboard/index.html        (inline-SVG, no external deps)
└── e156-submission/
    ├── body.md                 (156w validator-PASS)
    └── synthesis-methods-note.md  (≤400w)
```

### 2.2 `src/tb_atlas/` modules

R = Reused-from-PACTR-Hiddenness (light edit). N = New. A = Adapted.

| Module | Purpose | R/N/A |
|---|---|---|
| `config.py` | `paths.toml` loader | R |
| `aact_loader.py` | AACT pipe-delim → DataFrame for `studies / interventions / facilities / conditions / sponsors`. `information_schema` validation; fail closed on schema drift. | **N** |
| `ictrp_loader.py` | ICTRP weekly CSV → unified DataFrame | A |
| `trial_dedup.py` | Dedup AACT∪ICTRP by `{NCT, ISRCTN, EUCTR}` priority | **N** |
| `intervention_filter.py` | ≥1 of {Bdq/Pa/Lzd} in interventions; positive-list (drug + brands + code names) AND negative-list (TBA-354 etc); ≥40 fixture tests | **N** |
| `condition_filter.py` | MDR / pre-XDR / XDR / RR-TB matching (free-text + MeSH codes) | **N** |
| `population_filter.py` | Exclude pure pediatric (<12y) trials | **N** |
| `date_filter.py` | `start_date ≥ 2012-12-28` | **N** (trivial) |
| `africa_classifier.py` | Site list → `{africa_recruiting: bool, africa_site_share: float, africa_tier: enum}` via ISO-3166 lookup (54 African codes hardcoded) | **N** |
| `drug_class_taxonomy.py` | Regimen → enum (8 levels) | **N** |
| `nct_bridge.py` | Extract NCT/ISRCTN/EUCTR IDs | R |
| `results_posting.py` | Gate 1 (CT.gov + ICTRP results URL) | A |
| `publication_match.py` | Gate 2: Europe PMC `EXT_ID:NCT* AND (SRC:MED OR SRC:PMC)` (Bug-6-fixed) + per-NCT JSON cache | R |
| `cochrane_match.py` | Gate 3: NCT-bridge ∪ ISRCTN-bridge ∪ CDSR string-index | A |
| `funnel.py` | compute_funnel; cluster bootstrap CI; cluster = lead sponsor | A |

**Module count:** 15. Avg ~150 lines, cap target ~250. Every module has 3–8 unit tests. Net new code estimate: ~1500 LOC.

### 2.3 External dependencies (Python)

- Python 3.13
- `pandas` 2.x, `pyarrow` (parquet), `requests` (Europe PMC), `pytest`, `tomli` (paths.toml), `iso3166` (country codes)
- No DB engine — sqlite via stdlib only
- No web framework — dashboard is single-file inline-SVG HTML

### 2.4 Data assets (off-repo, in `paths.toml`)

- `aact_snapshot_dir` — pipe-delimited AACT dump (manual quarterly download from `aact.ctti-clinicaltrials.org`)
- `ictrp_snapshot` — WHO ICTRP weekly CSV (`C:/Users/user/data/ictrp/ictrp_<date>.csv`)
- `pairwise70_index` — `study_references.parquet` (built from CDE via `scripts/build_data_assets.py`, ported from PACTR-Hiddenness)
- `cdsr_string_index` — `cdsr_string_index.sqlite`
- `europe_pmc_cache_dir` — per-NCT JSON cache

### 2.5 Known risks at the architecture layer

1. **AACT pipe-delim schema drift** — column names change between AACT releases. `aact_loader.py` uses `information_schema.columns` for self-discovery and fails closed on unrecognized schema (per Lessons file `negated-counts silent corruption` pattern).
2. **Drug name regex over-match** — pretomanid PA-824 ≠ TBA-354 (different compounds, similar code names). `intervention_filter.py` has both positive and negative lists, ≥40 fixture tests covering ≥20 known-correct + ≥20 known-incorrect strings.
3. **ICTRP NCT-cross-reference gaps** — TB-PRACTECAL is ISRCTN26973455 first, NCT04207112 secondary. `trial_dedup.py` uses 3-key priority (NCT > ISRCTN > EUCTR) and logs every dedup decision to `dedup_log.csv`.
4. **Africa classifier needs comprehensive country table** — South Sudan, Eswatini, Côte d'Ivoire (encoding!), DRC vs Republic of Congo. ISO-3166 + curated list; tested with edge cases.

---

## 3. Data flow

End-to-end pipeline (vertical = time order; arrows = file/parquet boundaries):

```
   ┌───── EXTERNAL (paths.toml; NOT in repo) ─────┐
   │ AACT dump   ICTRP weekly  CDE      Pairwise70 │
   └───┬───────────┬───────────┬─────────┬────────┘
       ▼           ▼           ▼         ▼
   aact_loader  ictrp_loader  build_data_assets
       │           │           │
       ▼           ▼           ▼
  aact_trials  ictrp_trials  cdsr_string_index.sqlite
   .parquet    .parquet     study_references.parquet
       └─────┬─────┘
             ▼
   ┌── PHASE B: population filter (this order) ──┐
   │ intervention_filter (≥1 of Bdq/Pa/Lzd)      │
   │ condition_filter    (MDR/pre-XDR/XDR/RR)    │
   │ date_filter         (start_date ≥ 2012-12-28)│
   │ population_filter   (exclude peds)          │
   │ trial_dedup         (NCT > ISRCTN > EUCTR)  │
   └─────────────────────┬───────────────────────┘
                         ▼
              filtered_trials.parquet (~150–300 rows; the denominator)
                         │
   ┌── PHASE C: classification (adds columns) ──┐
   │ africa_classifier   → africa_recruiting,    │
   │                       africa_site_share,    │
   │                       africa_tier           │
   │ drug_class_taxonomy → drug_class            │
   └─────────────────────┬──────────────────────┘
                         ▼
   ┌── PHASE D: gates (per-trial bool columns) ──┐
   │ G1 results_posting                          │
   │ G2 publication_match (Europe PMC, cached)   │
   │ G3 cochrane_match    (NCT∪ISRCTN∪CDSR)      │
   └─────────────────────┬──────────────────────┘
                         ▼
                trials.parquet  (master output, one row per trial)
                         │
   ┌── PHASE E: aggregation + outputs ──────────┐
   │ funnel.compute_funnel → atlas.csv          │
   │ dashboard/index.html  ← trials + atlas     │
   │ fill_paper_placeholders.py → body.md +     │
   │                        methods-note.md     │
   └─────────────────────┬──────────────────────┘
                         ▼
            Pre-ship validation gates (fail-closed)
            1. Snapshot sha256 match
            2. TrialScout sanity (G2 ≥ 53.6%, one-sided)
            3. 30-trial blinded spot-check on G3 ≥ 27/30
            4. Sentinel pre-push: BLOCK=0
            5. Prereg verify (git tag prereg-v0.0.1 + IA snapshots on spec, protocol; atlas.csv tagged at v0.1.0)
                         │
                         ▼
                   v0.1.0 release
```

### 3.1 Fail-closed gates inside the pipeline

1. **`pilots/preflight.py`** — runs first, BEFORE extraction. Fails closed on:
   - any path in `paths.toml` not resolvable
   - AACT or ICTRP snapshot file sha256 mismatch with `data/snapshots/<source>_metadata.json`
   - Pairwise70 parquet < 1000 rows or CDSR sqlite < 100 reviews
   - missing critical columns in AACT (`information_schema` check)
2. **`aact_loader.py`** — asserts column schema before parsing. If unknown columns appear, raise.
3. **`intervention_filter.py`** — positive-list AND negative-list. Fails closed on ambiguous strings (logged to `intervention_audit.csv`).
4. **`trial_dedup.py`** — logs every dedup decision to `dedup_log.csv`. Fail-closed if same trial has NCT and ISRCTN pointing to different studies rows (manual reconciliation).
5. **`africa_classifier.py`** — `iso3166` package + curated 54-country table. Country in `facilities.country` not in lookup → raise.
6. **`publication_match.py`** — Bug-6-fixed Europe PMC query. Cache key includes query-version hash; old caches invalidated.
7. **`cochrane_match.py`** — ensemble logs disagreement when NCT-bridge says yes but CDSR string says no. Pre-ship gate: ensemble disagreement < 5%.

### 3.2 Snapshot reproducibility

- Every external snapshot sha256-pinned in `data/snapshots/*_metadata.json` (committed)
- Every output parquet/CSV sha256 captured in `data/snapshots/output_baselines.json` at v0.1.0 (committed)
- Re-running pipeline against same snapshots on different machine → byte-identical outputs (modulo Europe PMC ordering, which `publication_match.py` sorts before write)

### 3.3 Patient-weighted twin

Every gate carries `n_trials` and `n_participants` summed simultaneously. Headline pair `(pct_g0_to_g3, pct_g0_to_g3_pat)` computed once per stratum × sensitivity-def. Marginal cost: one `groupby().sum()` per gate.

---

## 4. Testing strategy and pre-registration discipline

### 4.1 Test pyramid (target ≥80 pytest tests at v0.1.0)

| Layer | Count | What |
|---|---|---|
| Unit (one module, mocked I/O) | ~50 | Each `src/tb_atlas/*.py` module: 3–8 tests covering normal, edge, adversarial |
| Integration (multi-module, fixture data) | ~10 | Phase B chain, Phase D chain, full orchestrator on 50-trial fixture |
| Fixture-baseline (regression) | ~5 | atlas.csv from 50-trial fixture must match committed baseline byte-for-byte |
| Validation-gate (subprocess) | ~5 | preflight, sentinel, ots-verify, fill-paper-placeholders, release dry-run |
| Property/adversarial | ~10 | Drug-name confusables, country-string edge cases, date-parse boundaries, enrollment=0/null |

### 4.2 Critical fixtures (4, all committed)

- `tests/fixtures/aact_50trial_subset/` — synthetic AACT pipe-delimited dump: 50 trials covering all 8 drug-classes, mix of African/non/dual sites, 5 NCT-only / 5 ISRCTN-only / 5 dual-registered (dedup test)
- `tests/fixtures/ictrp_30trial.csv` — synthetic ICTRP CSV; 15 overlap with AACT + 15 ICTRP-only
- `tests/fixtures/pairwise70_micro.parquet` — 5 NCTs, 3 ISRCTNs, 4 fake review IDs
- `tests/fixtures/cdsr_string_micro.sqlite` — 3 reviews with study-list strings

### 4.3 Pre-registration / HARK protection (GitHub tag + Internet Archive)

The spec doc (`docs/spec.md`) and protocol doc (`docs/protocol.md`) are pre-registered via two independent timestamping mechanisms **before any data extraction runs**:

1. **Signed GitHub tag** `prereg-v0.0.1` pushed to `github.com/mahmood726-cyber/africa-tb-atlas` — anyone can clone the repo and verify the commit SHA + tag-creation timestamp recorded by GitHub.
2. **Internet Archive (Wayback) snapshot** of the raw spec.md and protocol.md GitHub URLs — independent of GitHub; provides a second-witness timestamp at `web.archive.org/web/<timestamp>/...`.

Bitcoin OpenTimestamps was the original plan; switched to GitHub+IA on 2026-05-08 (recorded in AMENDMENTS.md). The combination provides defense-in-depth: even if GitHub is compromised, IA carries an independent record; even if IA disappears, the GitHub tag remains.

After prereg:
1. The 19 locked-at-spec decisions cannot change without a public AMENDMENT.
2. Every amendment is committed + logged in `AMENDMENTS.md`; the prior tag remains immutable in git history.
3. `verify_prereg.py` is a CI/preflight script that fails closed if local spec sha256 has drifted from the value recorded in `data/snapshots/prereg_manifest.json`.
4. atlas.csv is git-tagged + IA-snapshotted at v0.1.0 release (NOT before).

### 4.4 30-trial blinded spot-check (G3-only)

The methodological centerpiece. Protocol:

1. After algorithm runs and produces `trials.parquet`, sample 30 trials via `seed=20260507`. Stratified: 10 africa_recruiting=True / 20 africa_recruiting=False.
2. Write `data/processed/spotcheck_v0.1.0_blinded.csv` with `trial_id, NCT, ISRCTN, title, lead_sponsor, africa_recruiting` — **no algorithm verdicts**.
3. Dispatch a subagent (or human auditor) to web-verify each trial's G3 status: search Cochrane Library + Pairwise70 + manual title-match in CDSR. Auditor produces `spotcheck_v0.1.0_auditor.csv` with verdict + evidence URL per trial.
4. `merge_spotcheck.py` joins blinded + auditor; `validation_gates.py` computes per-gate agreement.
5. Pre-ship gate: **G3 verdict-level agreement ≥27/30**. (G1/G2 over-broadness is acceptable; only G3 — the headline — must hit the bar.)
6. If <27/30, do NOT ship v0.1.0. Either fix the algorithm OR document the disagreement profile as the substantive finding (PACTR-Hiddenness Amendment 2 precedent).

### 4.5 Sentinel pre-push hook (mode=block at v0.1.0)

- Default rules (XSS, hardcoded paths, leaked secrets, .pyc commits, license-noncompliance)
- TB-Atlas-specific WARN rule: `intervention_audit.csv` must not contain unresolved ambiguous interventions
- Target at release: BLOCK=0

### 4.6 TrialScout sanity (TB-tuned)

- Run `validation_gates.py::check_trialscout_sanity` after pipeline
- Expected: G0→G2 ≈ 63.6% per TrialScout 2026 baseline
- TB rationale: high-funded TB Alliance/USAID/EDCTP trials → publication rate likely *higher* than baseline
- **One-sided check**: warn if ≪53.6%, never fail-close on high values

### 4.7 Math edge cases (locked behaviors)

| Case | Behavior |
|---|---|
| `k < 3` in cluster bootstrap | CI undefined; report point estimate only |
| `enrollment` null on a trial | Drop from patient-weighted denominator, keep in trial-weighted (logged) |
| Empty stratum | Headline reports `n=0, pct=undefined`; dashboard shows "—" |
| All trials in one stratum | Skip stratification CI, report single pooled headline |
| Ambiguous intervention regex match | Fail closed, log to `intervention_audit.csv`, exclude from atlas |

### 4.8 Atlas baseline / regression test

- `atlas_baseline.csv` = the v0.1.0 atlas, committed, byte-pinned
- After v0.1.0, pipeline change altering atlas.csv → regression test failure
- Updating baseline requires explicit `--update-baseline` flag + AMENDMENTS.md entry

### 4.9 Recovery / rollback contract

- atlas.csv committed alongside the snapshot it was built from (sha256-pinned)
- Bad release = `git revert` v0.1.0 tag + ship v0.1.1 with documented amendment
- No deletions of tagged artifacts; the prereg tag is immutable; only additions/amendments allowed

---

## 5. Deliverables and release contract

### 5.1 v0.1.0 deliverables

| Artifact | Path | Notes |
|---|---|---|
| Master per-trial output | `trials.parquet` | Off-repo if >2 MB after compression |
| Aggregated atlas | `atlas.csv` | Committed; sha256-pinned in `data/snapshots/output_baselines.json` |
| Regression baseline | `atlas_baseline.csv` | Identical to v0.1.0 atlas.csv at release |
| Pre-registered protocol | `docs/spec.md` + `docs/protocol.md` | git-tag `prereg-v0.0.1` + IA snapshot BEFORE extraction |
| Methodological caveats | `docs/extraction_audit.md` | Drug confusables, dedup decisions, country-code coverage |
| Spot-check artifacts | `data/processed/spotcheck_v0.1.0_{blinded,auditor,merged}.csv` | Pre-ship gate evidence |
| Snapshot integrity | `data/snapshots/{aact,ictrp,pairwise70,cdsr}_metadata.json` | sha256, fetched_at, source_url |
| Dashboard | `dashboard/index.html` (+ `index.html` redirect) | Inline-SVG: Sankey, per-stratum forest, drug-class bar, Africa-vs-rest map. No external CDN. |
| E156 micro-paper | `e156-submission/body.md` | 156w validator-PASS |
| Methods note | `e156-submission/synthesis-methods-note.md` | ≤400w |
| Release script | `scripts/release_v010.sh` | Dry-run by default; `--execute` runs full pipeline + spot-check + sign-off |
| Sentinel hook | `.git/hooks/pre-push` (installed) | mode=block at v0.1.0 |
| GitHub Pages | `mahmood726-cyber.github.io/africa-tb-atlas/` | HTTP 200 verified |
| Internet Archive | Wayback snapshots of root, spec, protocol, dashboard | All HTTP 200 |
| Release stamps | spec.md, protocol.md (prereg-v0.0.1 tag); atlas.csv (v0.1.0 tag) | All IA-snapshotted; recorded in `data/snapshots/` JSON manifests |

### 5.2 Test target

≥80 pytest tests passing, 0 BLOCK from Sentinel, spot-check ≥27/30 G3 agreement.

### 5.3 Headline finding (locked-format; values filled at release)

> *"Of the N modern MDR/XDR-TB regimen trials registered globally since 2012-12-28, X% reach a Cochrane MA pool. African-recruiting trials reach Cochrane at A%; non-Africa-recruiting trials at B%. Patient-weighted, the gap is C% vs D% — corresponding to E,000 African-recruited patient-trial-arms outside any Cochrane synthesis. Sub-analysis: BPaL/BPaLM family trials reach Cochrane at F%; Bdq+companion trials at G%. The gap is robust to site-share≥30% sensitivity (H% vs I%)."*

### 5.4 Target publication venues

- **Primary:** Synthēsis E156 micro-paper (middle-author-only per E156 authorship rule; MA left Synthēsis editorial board so disclosure scope retired 2026-04-20)
- **Companion:** Synthēsis Methods Note (≤400w)
- **Stretch (NOT a v0.1.0 gate):** PLOS Global Public Health full paper, Q4 2026
- **Conference:** Union TB Conference 2026, abstract submission ~July 2026

### 5.5 Q3-2026 OKR alignment

This atlas is one of the 3 disease-specific Africa atlases under `q3-2026-canon-3-atlases` (with `africa-snakebite-atlas` and `africa-hiv-prep-atlas`). v0.1.0 release ≤ 2026-09-30 = on-time.

### 5.6 Effort estimate (calendar)

| Phase | Sessions | Hours |
|---|---|---|
| Spec + prereg + plan | 1 | 8 |
| Phase A+B (denominator) | 2 | 16 |
| Phase C+D (classify + gates) | 1 | 8 |
| Phase E+F (atlas/dashboard/paper, validation) | 2 | 16 |
| Spot-check + release | 1 | 8 |
| Buffer (bugs) | 2 | 16 |
| **Total** | **~9 sessions** | **~72 h** |

### 5.7 Version bumps post-v0.1.0

- **v0.1.1** — Fresh AACT/ICTRP snapshots (quarterly cadence)
- **v0.2.0** — ISRCTN-direct + EUCTR-direct Europe PMC search; per-site enrollment extraction; patient-weighted Africa-share as third headline
- **v0.3.0** — Cohort dropout (theme B from original idea); TB-specific publication-bias analysis (Egger / PET-PEESE)

### 5.8 Success criteria (v0.1.0 done)

1. ≥80 tests passing
2. Sentinel BLOCK=0
3. Spot-check ≥27/30 on G3 (or documented disagreement profile per Amendment, PACTR-Hiddenness precedent)
4. atlas.csv sha256 matches `atlas_baseline.csv` (regression test green)
5. dashboard live on Pages (HTTP 200)
6. spec.md + protocol.md tagged `prereg-v0.0.1`; atlas.csv tagged `v0.1.0`; all IA-snapshotted with URLs recorded in `data/snapshots/`
7. body.md passes 156w validator + DOI-resolved references
8. Workbook entry appended to `C:\E156\rewrite-workbook.txt`
9. tag `v0.1.0` annotated and pushed
10. Internet Archive snapshot of root + dashboard + spec + protocol all HTTP 200

### 5.9 Failure / revert contract

- If 1–10 fail at release: `git reset --soft` to before tag, fix, retag.
- Critical bug post-release: `git revert` + ship v0.1.1 with `AMENDMENTS.md` entry. Never delete or force-push over tagged artifacts (the `prereg-v0.0.1` and `v0.1.0` tags are immutable).
- Spot-check <25/30: ship as methodology-calibration paper (PACTR-Hiddenness Amendment 2 precedent) — disagreement profile becomes the substantive finding.

---

## 6. Decisions log

### 6.1 Locked at spec time (HARK protection — see §1.6 for the 19 items)

### 6.2 Auto-locked at spec time (canonical from sister atlases; not user-decided)

- Pre-registration via signed GitHub tag (`prereg-v0.0.1`) + Internet Archive snapshot (changed from Bitcoin OTS on 2026-05-08; see AMENDMENTS.md)
- Spot-check via blinded subagent (no algorithm verdicts)
- Sentinel pre-push hook with mode=block at release
- `paths.toml` for external snapshots; no hardcoded `C:\` in src/tests
- Repo at `C:\Projects\africa-tb-atlas\` + GitHub `mahmood726-cyber/africa-tb-atlas`
- E156 + Methods Note as primary deliverable

### 6.3 Deferred to v0.2.0+

- ISRCTN-direct / EUCTR-direct Europe PMC search
- Per-site enrollment extraction (patient-weighted Africa-share)
- Cohort dropout (theme B)
- Publication-bias analysis (Egger / PET-PEESE)
- Pediatric MDR-TB trials (separate atlas)

---

## 7. Open questions (none currently — all clarified during brainstorming)

- ~~Primary atlas axis (Cochrane-inclusion vs cohort dropout)~~ → **Cochrane-inclusion** (Q1)
- ~~Trial population scope~~ → **bedaquiline / pretomanid / linezolid containing MDR/XDR regimens** (Q2)
- ~~Africa framing (filtered vs stratified vs patient-weighted)~~ → **global stratified by African-site presence** (Q3)
- ~~Trial denominator data source~~ → **AACT + ICTRP merged** (Q4)
- ~~Headline metric structure~~ → **trial- AND patient-weighted dual headline** + drug-class Section 3 (Q5)
- ~~African-site definition~~ → **binary ≥1-site headline + site-share ≥30% sensitivity + three-tier Section 3** (Q6)

---

## 8. References to other portfolio assets

- `C:/Users/user/.claude/projects/C--Users-user/memory/pactr-hiddenness-atlas.md` — sister atlas; ~70% plumbing reuse
- `C:/Projects/pactr-hiddenness-atlas/` — codebase to clone modules from
- `C:/ProjectIndex/long-term-plan/ideas.yaml::africa-tb-atlas` — source idea
- `C:/E156/rewrite-workbook.txt` — submission ledger
- `C:/Sentinel/` — pre-push hook engine
- `C:/MetaAudit/data/pairwise70/` — Pairwise70 source assets

---

**End of design spec. Awaiting user approval before transition to writing-plans.**
