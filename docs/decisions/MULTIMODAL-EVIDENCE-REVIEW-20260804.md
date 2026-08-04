# Multimodal-evidence expansion — council review captured 2026-08-04

Source: user-run multi-model review (Grok 4.5 Medium + GPT-5.6 Sol Thinking;
Gemini returned nothing) of three DRAFT skills from another thread (multimodal
evidence ingestion, force-vision, visual-clue/OSINT). Honest headline preserved:
**those ZIPs were never committed anywhere** — they are drafts, not repo state.

## Repo-truth mapping (checked against main, 2026-08-04)

| Review item | Actual state here |
|---|---|
| "Fix the bundle-dir/slug bug first" | ALREADY FIXED — slug handling landed via PR (agent/fix-youtube-bundle-slugs) with regression test |
| "Canonical shared evidence schema missing" | PARTIAL — `beast.watch.timeline/v3` + `watch/typed_evidence.py` exist; elevating a shared `beast/evidence` package above all consumers is the real open proposal |
| "Five evidence states (Observed/Inferred/Uncertain/Verified-by-execution/Rejected)" | PARTIAL — ledger language (observed/reproduced/measured/verified/generalized) + reflection schema (observed/inferred/needs-verification) already enforce most of this; reconciling into ONE state vocabulary is worth doing, mechanically |
| "Skills must plug into Watch, not bypass it" | MATCHES existing doctrine (BEAST.md loop; watching gate) — adopt as binding for any multimodal add-on |
| OCR ≠ object/hand/reflection detector | Correct; adopt. Schema reuse yes, model reuse no |
| Force must emit uncertainty bounds + vector math (F_t = m·a_t, velocity as vector) | Adopt as precondition — force-vision stays OUT of the repo until it has an evaluation contract |
| Enhancement never presented as recovered fact | MATCHES claim discipline; C2PA-style transformation ledger proposed (see OPP-20260804-02) |
| OSINT/geolocation bounded + human-gated | MATCHES legal-floor culture; no autonomous person-identification, ever |
| DeepStream 9.1 MV3DT + AutoMagicCalib | NEW DOOR (see OPP-20260804-01) — single-model finding, verify before hardware time; SBSA container REQUIRED on DGX Spark (no bare-metal) |

## Adopted sequencing (edits to the council's order, given repo truth)

1. ~~bundle-dir fix~~ (done) → instead: land any real unpushed proof from the
   other thread through normal review
2. Shared evidence package (`beast/evidence`) unifying timeline/typed/receipt
   schemas + ONE evidence-state vocabulary reconciliation
3. NeMo Retriever OCR as a Watch EXTRACTOR (plug-in, not parallel pipeline),
   proven against a real screen-recording fixture
4. DeepStream 9.1 in the SBSA container on the Sparks as tracking substrate —
   AFTER verifying the single-model claims against NVIDIA docs; wrap its 10
   shipped agent skills, don't rebuild
5. Review gate with the reconciled evidence states
6. One compiled skill proven by replay through the new path

Force-vision and OSINT remain outside the repo (draft/experimental) until they
carry evaluation contracts and human-review policies. Nothing from the ZIPs
merges as-is.
