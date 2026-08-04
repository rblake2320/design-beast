# Evidence contracts

## Contract layers

| Layer | Schema | Gate |
|---|---|---|
| Source | `beast.evidence.source-manifest/v1` | Exact SHA-256, approving principal, basis, and allowed uses |
| Event | `beast.evidence.event/v1` | Source/time/extractor/hash binding; uncertainty for derived measurements |
| Claim | `beast.evidence.procedure-claim/v1` | Every cited event resolves; hypothesis/generative evidence cannot masquerade as fact |
| Receipt | `beast.evidence.execution-receipt/v1` | Success equals all checks; artifacts and environment are hashed |
| Bundle | `beast.evidence.procedure-bundle/v1` | Promotion is derived, never authored |
| Dataset | `beast.evidence.dataset-rights/v1` | Explicit training rights for every admitted source |

JSON Schemas live in `watch/schemas/evidence-*-v1.schema.json`. Runtime checks
live in `watch/evidence/contracts.py`; runtime validation remains authoritative
because schema validation alone cannot re-hash files or resolve references.

`confidence` records the extractor's confidence in the emitted observation or
provider response. It is not a probability that the underlying real-world
claim is true. For example, a SafeSearch response can be captured exactly while
remaining a provider inference; its event therefore stays `inferred`.

## Receipt specification

Pass a JSON specification to `evidence_intake.py receipt`:

```json
{
  "receipt_id": "receipt-example",
  "claim_ids": ["claim-..."],
  "success": true,
  "environment_fingerprint": "64 lowercase hex characters",
  "executed_at": "2026-08-04T21:00:00Z",
  "artifact_base": "../..",
  "artifacts": [{"label": "result", "path": "proofs/example/result.png"}],
  "checks": [{"name": "pixel_gate", "passed": true, "evidence": "measured receipt path"}]
}
```

Artifact paths are resolved from the specification file. If `artifact_base` is
present, every artifact must remain below it and the receipt stores a relative
path.

## Dataset rights

`dataset-check` accepts one rights file and one or more `--manifest` arguments.
The rights file must enumerate exactly the manifest fingerprints being exported.
`fair_use_research`, `unverified`, or a missing `dataset_training` use fails.

## Google Cloud Vision boundary

The adapter implements two separate official Cloud Vision features using local
image bytes:

- SafeSearch: `SAFE_SEARCH_DETECTION`, categories adult/spoof/medical/violence/racy.
- Web Detection: `WEB_DETECTION`, web entities, matching pages, full/partial
  matches, visually similar images, and best-guess labels.

It calls `POST https://vision.googleapis.com/v1/images:annotate`, caps returned
rows, and never follows returned URLs. Authentication is optional at install
time and required only for a live cloud call.

Primary documentation (checked 2026-08-04):

- https://docs.cloud.google.com/vision/docs/detecting-safe-search
- https://docs.cloud.google.com/vision/docs/detecting-web
- https://docs.cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- https://docs.cloud.google.com/vision/docs/authentication
