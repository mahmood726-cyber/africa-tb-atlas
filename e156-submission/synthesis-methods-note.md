# africa-tb-atlas — Synthēsis Methods Note

**Title:** A four-gate audit of African representation in modern MDR/XDR-TB regimen trials' path to Cochrane synthesis

**Authors:** Mahmood Ahmad (corresponding); [middle authors TBD]

**Affiliations:** [TBD]

## Background

Trial-to-synthesis pipelines underrepresent African evidence (PACTR-Hiddenness Atlas, 2026). The TB Atlas extends that finding to disease-specific terrain: modern MDR/XDR-TB trials using bedaquiline, pretomanid, or linezolid since regulatory approval (2012-12-28 bedaquiline FDA-EUA).

## Methods

We constructed a global denominator of MDR/pre-XDR/XDR-TB trials starting on or after 2012-12-28 from AACT (CT.gov snapshot {{SNAPSHOT_DATE}}) union WHO ICTRP weekly export, deduplicated by NCT > ISRCTN > EUCTR ID priority. Pediatric trials and trials without bedaquiline/pretomanid/linezolid were excluded. Each trial passed a four-gate funnel: G0 registration, G1 results-posted (CT.gov date or ICTRP results URL), G2 peer-published (Europe PMC NCT-bridge or ISRCTN-bridge), G3 in-Cochrane (Pairwise70 NCT-bridge union ISRCTN-bridge union CDSR string-match). Trials were stratified by African site presence (binary ≥1 site; site-share ≥30% sensitivity; African-led/recruiting/non three-tier). Both trial-weighted and patient-weighted Cochrane inclusion rates were reported with cluster-bootstrap 95% CIs (cluster = lead sponsor; undefined when k<3). Pre-registered via signed GitHub tag prereg-v0.0.1 with sha256 manifest and Internet Archive snapshot before any data extraction.

## Headline finding (fixture-mode values — v0.1.0 release locks real values)

Of {{N_TRIALS}} modern MDR/XDR-TB trials registered globally since 2012-12-28, Cochrane inclusion was {{PCT_G3_AFRICA}}% for Africa-recruiting trials versus {{PCT_G3_NON_AFRICA}}% for non-Africa (trial-weighted); patient-weighted the gap was {{PCT_G3_PAT_AFRICA}}% versus {{PCT_G3_PAT_NON_AFRICA}}%, corresponding to {{N_PARTICIPANTS_AFRICA}} African-recruited patient-trial-arms outside any Cochrane review. Robust to site-share ≥30% sensitivity ({{SITE_SHARE_30PCT_AFRICA_PCT}}% vs {{SITE_SHARE_30PCT_NON_AFRICA_PCT}}%). Blinded G3 spot-check: {{SPOTCHECK_AGREE_N}}/{{SPOTCHECK_TOTAL}} verdict-level agreement.

## Limitations

NCT-bridge has known sensitivity gaps for non-CT.gov-registered trials (PACTR-Hiddenness lesson); modern MDR-TB trials are predominantly CT.gov-registered so this is fit-for-purpose, but ISRCTN-direct Europe PMC search is added as a sensitivity. Within-trial cohort dropout is deferred to v0.3.0. Pediatric MDR-TB trials are scoped to a future companion atlas.

## Ship gates

≥80 pytest tests passing; Sentinel BLOCK=0; ≥27/30 G3 spot-check agreement; atlas.csv tagged at v0.1.0; Internet Archive snapshot; prereg-v0.0.1 tag immutable in git history.
