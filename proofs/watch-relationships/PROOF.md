# Relationship recovery: retained failure and known-case repairs

Stack: base PR42 / `codex/watch-positive-controls-20260919`, base head
`4a7207b8ef758d7a4f14e0339cfb09239ec05283`. Expected dependency order is
PR39 -> PR40 -> PR41 -> PR42 -> this draft, subject to human review/rebase.
No prior PR is modified or merged.

## Observed results

Ten actual25FPS Chrome recordings;11 independently labeled visible input events,
10result intervals and10 permitted order-compatible pairs. Two reviewers froze
native-frame labels before the first observer execution and without reading the
fixture, recorder or private telemetry. Their source hashes, boundary-frame
hashes and review methods are committed alongside the recordings.

| Execution | Baseline inputs /11 | Conditional inputs /11 | Correct control identity | Correct results /10 | Correct temporal pairs /10 | False temporal pairs |
|---|---:|---:|---|---|---|---|
| Initial frozen observer174a8ce |10|4|1 /0|0 /0|0 /0|0 /0|
| Border/pointer OCR repair0f11140 |10|6|10 /3|10 /10|9 /2|0 /4|
| Result-bracket repair0a335ea |10 retained|10|10 /6|10 /10|9 /5|0 /4|
| Unoccluded-context repair1248ec5 |10 retained|10|10 /10|10 /10|9 /9|0 /0|

Slash-separated paired values are baseline / conditional. Original score files
are retained, with stricter scorer rechecks separate. All final control boxes
pass the declared0.5IoU criterion. Final event false extras are0/0. Both arms
miss case08's single-native-frame press. Result-before-input produces no backward
candidate; input-absent footage produces no input. All10 causal abstentions are
correct against the unknown labels; causal acceptance is disabled in every run.

**Graduation FAIL:** conditional does not recover two events missed by baseline.
Final known-case recovery ties. These repairs are not fresh blind validation.

## What failed and was repaired

1. Pre-run independent review reproduced pixel routing accepting false frame
hash declarations. Replaced file reopening with the same snapshots checked for
OCR; shared source identity and dependency hashes were added before execution.
2. First actual run failed result recognition: PSM11 ignored bordered controls
and status. Source-derived, border-free crops and prior-frame control context
recovered these observations. Retained originals were not replaced.
3. Review caught result-label prefix mismatch, missing independent temporal-order
checks, and incomplete scorer custody. Scorer now validates reference bytes,
mode, prior-reference ordering, event spans, exact identities, box overlap,
resource finiteness, and single-use event/result matching. Regressions include
wrong controls, backward pairs, changed files and escaping paths.
4. Largest-pixel-change routing spent attention on page appearance. Result-bracket
inspection repaired event recall on the known cases. Incorrect cropped labels
under the pointer then prompted two budgeted earlier context frames.
5. Prior-control reuse now rejects future references; conflicting text on the
same held spatial event no longer creates an extra event.

Final repair measures160 requested frames per arm,160 baseline OCR calls and140
conditional calls. Baseline wall35.110s is retained from0f11140; final conditional
wall31.921s is from1248ec5. They are different execution stages, not a paired
speed comparison. GPU/model/paid-provider calls are zero. No narration ran.

## Proof boundary tested

Worked on the retained known cases: image-bound input/control/result observations,
temporal ordering, source references, and causal abstention. Failed: the frozen
superiority requirement and single-frame recovery. The corpus deliberately has
unknown causal sufficiency, so a score for successful causal recovery is not
reported as if it were measured.

Protocol: `bench/watch-relationships-v1.json`; reproduction and scope:
`docs/WATCH-RELATIONSHIPS.md`. Observe source videos in `capture/case-XX/source.webm`;
native labels and evidence are adjacent. No local drive path is required by a
GitHub reviewer. Initial and repaired executions are separate directories.
