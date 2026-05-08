# Extraction audit

## 1. Drug-name confusables resolved

The intervention filter (`src/tb_atlas/intervention_filter.py`) uses a
positive list (drug + brand + code names) AND a negative list (confusables
that look similar but are different compounds).

### Positive list (each pattern case-insensitive, word-bounded)

| Canonical | Patterns matched |
|---|---|
| bedaquiline | bedaquiline, sirturo, bdq, tmc-207 |
| pretomanid  | pretomanid, pa-824 (and PA 824, PA824), dovprela |
| linezolid   | linezolid, zyvox, linox, linospan, u-100766 |

### Negative list (must NOT match — silent corruption hazard)

| Pattern | What it really is |
|---|---|
| tba-354 | A different nitroimidazole; investigated separately by TB Alliance and discontinued. **Not pretomanid (PA-824).** |
| pa-1314 | Unrelated PA-numbered compound. |
| tba-7371 | TB Alliance pipeline; not a target drug. |

### Strict-mode behavior

`matches_target_drug(name, strict=True)` raises `AmbiguousInterventionError`
when a free-text intervention contains BOTH a positive and a negative-list
match (e.g., "PA-824 / TBA-354 combination"). Default mode (strict=False)
returns the positive match without raising; the orchestrator logs ambiguous
strings to `data/processed/intervention_audit.csv` for spot-check review
without blocking the pipeline.

## 2. Dedup decisions

Trial dedup (`src/tb_atlas/trial_dedup.py`) merges AACT∪ICTRP via
NCT > ISRCTN > EUCTR ID priority. AACT row metadata is kept on overlap
(more comprehensive). Every dedup decision is logged to
`data/processed/dedup_log.csv` with columns `{trial_id, decision, via}`,
where `decision` ∈ {merged_nct, merged_isrctn, merged_euctr, kept_ictrp_only}.

### Conflict semantics (DedupConflictError)

If AACT and ICTRP both have a row with the same NCT but DIFFERENT
ISRCTN/EUCTR (or vice versa), `dedup_trials` raises `DedupConflictError`.
This is a data-integrity error, not a normal case — the cross-registration
either has a typo or one registry has stale information. Manual
reconciliation required before re-running.

In v0.1.0 fixture-mode runs across the 50-trial AACT × 30-trial ICTRP
fixture, no DedupConflictError fires. Real-data runs (Task 27) will
re-audit.

## 3. Country-code coverage

`africa_classifier._to_alpha2` resolves country names to ISO-3166 alpha-2
codes via:

1. A curated `ALIAS` map (case-insensitive, ≥80 entries; covers all 54
   African countries + frequent non-African collaborators)
2. Unicode normalization for accented characters (Côte d'Ivoire → CI;
   São Tomé and Príncipe → ST)
3. `iso3166` package as fallback for unrecognized strings
4. Fail-closed `UnknownCountryError` if both the ALIAS map AND iso3166
   miss

### African set (54 codes)

The hardcoded `AFRICAN_ALPHA2` is exactly 54 ISO-3166 alpha-2 codes,
matching UN-recognized sovereign African states. Western Sahara (EH)
is in the ALIAS map (resolves to "EH") but NOT in `AFRICAN_ALPHA2` —
intentional per the UN definition (the AU recognizes WS as a 55th member,
but the UN does not). For v0.1.0, trials with sites in Western Sahara
will be classified as non-Africa. Document any real-data trials that hit
this case.

### Three-tier thresholds

- **African-led:** ≥50% of sites in African countries (or PI affiliation
  in Africa, where extractable from registry data)
- **African-recruiting:** ≥1 African site, but <50% of total sites
- **Non-Africa:** 0 African sites

### 30% sensitivity threshold

Pre-registered binary sensitivity at site-share ≥30% (boundary-inclusive).

## 4. Methodological caveats (v0.1.0)

### 4.1 Gate 1 over-broadness

`results_first_posted_date` non-null OR `result_url` non-empty does not
guarantee that meaningful results are actually present. CT.gov requires
posting under FDAAA; ICTRP `Results URL` is populated for nearly all
PACTR trials regardless of actual content. The TrialScout-sanity check
on Gate 2 (G0→G2 ≥53.6%, one-sided) compensates: low G2 rates suggest
the population deviates from baseline; high rates are EXPECTED for
TB-Alliance/USAID/EDCTP-funded modern MDR-TB trials and do not fail-close.

### 4.2 NCT-bridge fitness for modern TB trials

PACTR-Hiddenness Atlas reported NCT-bridge has 6.2% sensitivity for
PACTR-registered African publications, because most PACTR trials lack
NCT cross-references. The TB Atlas does not depend on PACTR — modern
MDR-TB trials are predominantly CT.gov-registered (TB Alliance, NIH,
USAID, EDCTP funding) or ISRCTN-first (MSF-led trials like TB-PRACTECAL).
NCT-bridge is fit-for-purpose. ISRCTN-direct Europe PMC search is added
as a sensitivity layer in `publication_match.lookup_publication_by_isrctn`.

### 4.3 Pediatric exclusion is title-keyword-based

`population_filter.is_adult_or_adolescent` checks for pediatric markers
in the trial title (`pediatric`, `paediatric`, `infant`, `children`,
`under <age>`). Adult-positive markers (`adult`, `adolescent`,
`age[ds]? >=12|18`) override. Some borderline trials (e.g., 16-65 age
range without explicit "adolescent" keyword) may slip through. The
30-trial blinded G3 spot-check (Task 32) audits this on the pre-ship
sample.

### 4.4 Patient-weighted denominator drops null enrollment

Trials with `enrollment` null (no target sample size posted) are dropped
from the patient-weighted denominator but kept in the trial-weighted
denominator. The orchestrator does not log a count of these in v0.1.0;
v0.1.1 will add a summary row.

### 4.5 ICTRP placeholder caveat (v0.1.0 known limitation)

The v0.1.0 atlas runs against `tests/fixtures/ictrp_30trial.csv` (and
production `paths.toml` points at a PACTR-scoped subset of ICTRP, NOT
the full WHO ICTRP weekly export). This systematically underrepresents
EUCTR-only and ISRCTN-only trials registered outside Africa. Documented
in `data/snapshots/ictrp_metadata.json::notes`. **Task 27 (deferred) must
replace the ICTRP snapshot with the full WHO weekly export before v0.1.0
release.**

### 4.6 Drug-class taxonomy edge cases

`drug_class_taxonomy.classify_regimen` is order-dependent in its if-chain:
BPaLM (Bdq+Pa+Lzd+Mfx) → BPaL (exactly Bdq+Pa+Lzd, no other) → Pa+Lzd
(no Bdq) → Lzd dose-finding (multi-arm Lzd-only) → Bdq+other-companion
→ Bdq monotherapy/pair → Pa monotherapy/pair → other.

Lzd dose-finding requires ≥2 distinct Lzd-matching intervention strings
(e.g., "Linezolid 1200mg" + "Linezolid 600mg"). A single-arm Lzd trial
falls to OTHER. Documented in `tests/test_drug_class_taxonomy.py`.

### 4.7 Ensemble disagreement <5% pre-ship gate

The G3 union is `{NCT-bridge, ISRCTN-bridge, CDSR string-match}`. When
two or more components return data but disagree, `match_trial` flags
`ensemble_disagree=True`. Pre-ship gate: aggregate disagreement <5%
across the denominator. If exceeded, the disagreement profile is
investigated before tagging v0.1.0.

### 4.8 Bootstrap CI undefined when k<3 lead-sponsor clusters

Cluster bootstrap (`funnel.clustered_bootstrap_ci`, cluster=`lead_sponsor`)
returns `(None, None)` if fewer than 3 distinct sponsors exist in a stratum.
The atlas reports point estimates only in those cases; CIs are surfaced
as "—" in the dashboard. Real-data runs typically clear this threshold
within Africa-recruiting strata; small drug-class buckets may not.

### 4.9 Pre-registration mechanism amendment (2026-05-08)

Per `AMENDMENTS.md` 2026-05-08 entry: pre-registration is via signed
GitHub tag `prereg-v0.0.1` + Internet Archive snapshot, NOT Bitcoin
OpenTimestamps. This was decided pre-data-extraction. Spec sha256s
recorded in `data/snapshots/prereg_manifest.json`; verifiable via
`scripts/verify_prereg.py`. IA Wayback URLs in
`data/snapshots/internet_archive_prereg.json`.

### 4.10 Sentinel skip-file marker on spec.md (Amendment 2, post-prereg)

Per `AMENDMENTS.md` 2026-05-08 (later) entry: `docs/spec.md` carries a
`<!-- sentinel:skip-file -->` HTML comment to exempt it from the
`P0-hardcoded-local-path` rule. The spec contains absolute paths as
descriptive content (not application configuration). This amendment
is purely tooling metadata; no analytical decision changed. spec.md
sha256 updated in prereg_manifest accordingly.
