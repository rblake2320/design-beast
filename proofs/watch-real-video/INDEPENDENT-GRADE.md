# Independent grade: real-video challenge 01

**Verdict: FAIL.** The frozen challenge did not recover the ten reference events. A schema-valid overview contained an incorrectly grounded visual transition; the detail response was repetitive, truncated, and correctly rejected. This result must not be presented as successful video watching or converted into a verified training procedure.

Reviewer: `/root/inspection_review`, 2026-09-18. No model reruns, prompt changes, or source-window substitutions were performed by this reviewer.

## Blindness and artifacts

The independent reference was written before answer inspection and committed as `596be81`. Its SHA256 remains `9b9643b7bfc39095b4784068e78698edb1709917424a745427b235abdc69a471`. It is an independent agent visual reference, not absolute human ground truth. Its 0.5-second sampling can miss intervening events.

Graded inputs under `watched/real-challenge-01/`:

The three answer/failure files below were also independently hash-checked in the durable export `proofs/watch-real-video/run-01/`; all match their graded originals. Use that exported directory for retained review.

- `overview-repair-answer.json`: SHA256 `b94c61aa05191d57af1160554836dc244f6af311ce8ae1cdd9a5d59512a011f3`.
- `detail-raw.json`: SHA256 `a801406fae7d6c33707bc80874828e2897676dbf9e3fae7968c5e3056742dffb`.
- `detail-failure.json`: SHA256 `bdba262ed5057e7c494975811b32c4ed8a3faa26f9eebbf68990be026477e7e2`.
- Supporting protocol, detail intent, two HTTP failure receipts, and denied resource-admission receipt.
- Directly re-viewed all four overview input JPEGs to check the emitted frame-index attribution.

## Event-level grade

Only complete validated outputs count toward recovery. No credit is awarded to fragments of the rejected detail response.

| Reference | Expected visual observation | Result |
|---|---|---|
| V1 | Side/front/oblique viewpoint changes | Missed in validated output. |
| V2 | Zoom-out and right-orthographic presentation | Missed in validated output. |
| V3 | Blue annotation drawn along body | Missed. |
| V4 | Additional view-scale reduction | Missed. |
| V5 | Annotation erased | Missed. |
| V6 | Return to front-ish perspective | Missed. |
| V7 | Arms reappear; visible unhide operator label | Missed. |
| V8 | Annotation cursor/tool changes to selection presentation | Missed. |
| V9 | Window switcher followed by slide | Coarse slide-change concept mentioned, but cited before/after pair is false; not a correctly grounded recovery. Window switcher missed. |
| V10 | Fifth slide point fades in | Missed. |

**Strict correctly grounded recovery: 0/10.** If ignoring timing and provenance, the output mentions the broad subject of one event, V9; that is **1/10 coarse mentions**, not successful recovery. These are reference-event counts for this clip, not generalized model recall estimates.

Sparse input is a material limitation: overview used clip seconds 0, 10, 20, 30; detail intent supplied only 2, 4, 6, 8. Several short events are absent from those model inputs, so those misses cannot all be attributed to perception. The complete system still fails the frozen all-major-changes criterion: it did not acquire and use adequate evidence to recover them.

## False claims and confidence

The overview emitted exactly one change record, citing indices **0 -> 1**. Index 1 is clip second 10/source second 1810 and visibly still shows Blender, in right orthographic view with an annotation. It is **not** the text slide. The slide is present at indices 2 and 3. Therefore:

- **False evidence-grounded change records: 1/1.** Counted once, not multiplied for repeated wording in the same record.
- Correctly grounded change records: 0/1.
- Perception and transition confidence were both **1.0 despite this false attribution**. Their values are not calibrated truth guarantees.
- The separate statement that the slide content is unrelated to the viewport is unsupported: both concern character blockout. This is an additional unsupported interpretation, not a second counted visual transition.
- No positive causal/procedure claim was emitted in the complete answer; procedure confidence was 0.0 and exact cause was left unresolved. This restraint is appropriate but does not repair the visual attribution error.

This is a false model observation, **not an observed false acceptance by Watch's evidence authority**. The retained result remains `unverified_visual_observations`; no verified procedure promotion was seen.

## Detail and transport failures

The detail model response ends with `done_reason=length`, `eval_count=1800`, an empty response field, and an incomplete JSON string in the thinking field. The validation receipt reports EOF inside a string. The raw output repeats body/head/feet descriptions until truncation; increasing the cap alone is not demonstrated to solve this degeneration. There is no accepted detail answer to grade as recovered evidence.

Diagnostic reading of the rejected fragment also shows errors: its claimed first pair 0 -> 1 corresponds to clip seconds 2 -> 4, but it calls the after view right orthographic when the reference at 4 seconds shows perspective. Its purported initial label `Umi/Anipage...` is not established by the reference. These fragment errors are not included in the 1/1 complete-record false-claim count.

Two schema-format requests failed with HTTP 400; the more detailed receipt identifies sampler grammar parsing failure. A separate diagnostic resource check denied admission. These retained failures are failures, not successful vision inspections. Parsing strict JSON already returned in the overview thinking field is a transport repair, not a new successful inference or evidence correction.

## What this run actually demonstrates

It demonstrates real local-model execution on retained tutorial pixels, a concrete image-to-index grounding failure, inadequate sampled-event coverage, a repetitive generation failure, and a rejection boundary that preserved the truncated result as failed. It does not demonstrate successful procedure extraction, reliable temporal understanding, efficient adaptive recovery, or Jev/SemIf capability.

For a future separately versioned experiment, strengthen frame-identity checks and inspection coverage, and prevent malformed/repetitive responses from entering evidence gates. Do not retune or cherry-pick this frozen challenge into a pass. Preserve this FAIL as the baseline.
