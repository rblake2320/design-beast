# Media Evidence Intake Proof

## Result

The native Beast evidence layer admitted one exact retained tutorial video,
converted its Watch v3 timeline into 208 hash-bound visual events, linked nine
source-time frames to a procedure claim, freshly executed the documented
MetaBalls feedback repair in Inkscape, and derived `promotion_allowed: true`
from a successful hashed receipt.

This is a **reproduced repaired execution**, not an unbiased held-out pass and
not evidence of generalization. The original failed held-out result remains in
`bench/heldout-typed-compiler/RESULTS.md` and was not rewritten.

## Why this proves visual intake

- Source: `https://www.youtube.com/watch?v=cT41th-pIJc`
- Retained source SHA-256:
  `7385741a8bea4e02b97d3e5f68f743acf9e92ea1f2c7eed54c56b0c833549627`
- Watch schema: `beast.watch.timeline/v3`
- Timeline fingerprint:
  `c1e69c60cb87cff3b43c60d5deb517eddcdee70981630e71eab045737ceaaa88`
- Frames: 208
- Transcript method: `unavailable`
- Transcript segments: 0

The claim cites frames 0065, 0070, 0103, 0107, 0108, 0129, 0138, 0164,
and 0171. With no transcript, those facts necessarily came through retained
pixels and the typed visual repair record rather than narration.

The local raw video and extracted frame directory are retained outside Git to
avoid redistributing tutorial media. `source-manifest.json` and
`event-set.json` retain their exact hashes and source-time custody.

## Fresh execution

Environment:

- Python 3.12.10
- Inkscape 1.4.4 (`dcaf3e7`, 2026-05-05)
- Adapter SHA-256:
  `1f8cd5a3659a4c6b99a4a7fa73d9229023ecdd9d31b6fe1daeee5920ec979e0d`
- Typed-state compilation fingerprint:
  `6d7141bf526a137cc5382822c317502abc26c9f822499ab566cfa9cc0325636e`

The fresh adapter receipt measured:

- exact primitive order: Gaussian blur, color matrix, color matrix;
- blur standard deviation `34.79 34.79`;
- two identical 20-value matrices;
- two connected components in the unfiltered control;
- one connected component in the result;
- center alpha changed from 0 to 255; and
- exact render size 800 by 480.

All eight checks passed. The result PNG SHA-256 is
`3a4112e82833c4dc2b304559c1bce17898038e3e8ee867c227d7b71255f27608`.
The compiled procedure-bundle fingerprint is
`65352f4b20e834e68a00407fe2e8df85729861faca667741909c067b6640ca9f`.

## Rights gate

The source was admitted only as `fair_use_research` for evidence analysis and
procedure learning. That label is a workflow authorization boundary, not a
legal ruling. The attempted training export correctly failed with both:

- `fair_use_research source is not eligible for dataset training`; and
- `source lacks dataset_training authorization`.

## SafeSearch and Web Detection scope

The optional Google Cloud Vision adapter implements two separate features:

1. `SAFE_SEARCH_DETECTION` runs first and can block further processing for
   adult, violent, or racy results at the configured threshold.
2. `WEB_DETECTION` records web entities, matching pages/images, partial/full
   matches, visually similar images, and best-guess labels without fetching any
   returned URL.

Cloud use requires `cloud_analysis` authorization, an explicit per-call flag,
an explicit prior person-free screening confirmation, and a configured
credential. Web results remain hypothesis-only and cannot
alone verify identity, location, ownership, or wrongdoing.

The cloud adapter is proven here by adversarial tests with an injected
transport: authorization is required before network use, a blocked SafeSearch
result prevents Web Detection, a safe result permits it, returned URLs are not
fetched, unscreened/person-bearing images cannot enter Web Detection, and
web-only evidence cannot promote an identity claim. **No live
Google request was made**, so live service integration remains unproven.

After the R2 extractor package landed on main, this branch also wired its
canonical `SafeSearchExtractor` and `WebDetectionExtractor` stubs to the same
shared REST client. Injected-transport tests prove those actual extractor entry
points parse responses and fail closed without permission. The raw extractor
event schema remains canonical; this proof's stricter records are the separate
promotion-custody layer.

Official interfaces checked 2026-08-04:

- https://docs.cloud.google.com/vision/docs/detecting-safe-search
- https://docs.cloud.google.com/vision/docs/detecting-web
- https://docs.cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- https://docs.cloud.google.com/vision/docs/authentication

## Reproduction

Use `skills/media-evidence-intake/SKILL.md`. The generated evidence artifacts
in this directory are deterministic inputs/outputs except for timestamps. Run:

```powershell
python bench/heldout-typed-compiler/metaballs_adapter.py `
  bench/heldout-typed-compiler/typed-state-feedback-repair.json `
  proofs/media-evidence-intake/execution

python scripts/evidence_intake.py compile `
  proofs/media-evidence-intake/source-manifest.json `
  proofs/media-evidence-intake/event-set.json `
  proofs/media-evidence-intake/claim.json `
  proofs/media-evidence-intake/execution-receipt.json `
  proofs/media-evidence-intake/procedure-bundle.json `
  --artifact-root .
```

An independent reviewer must still verify the branch and receipts before merge.
