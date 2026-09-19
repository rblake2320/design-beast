# Evidence-guided instructional units

`watch-instruction-gate --review DIR --plan JSON --output NEW_DIR` turns an
existing draft into pending, ambiguous units. `--units JSON` validates a reviewed
unit file against the exact source, review manifest, and retained frame bytes.
Use `watch-training render` on the emitted `training-draft.json`, then
`watch-narrate` if speech is wanted. The automatic path stops before narration.

The four classes are observable action, observable result, ambiguous transition,
and scene change. Pending/ambiguous proposals require review. Scene changes are
omitted. Rejected proposals request annotation. Accepted action proposals missing
control, activation or result evidence request recapture. Result-only descriptions
must not imply a cause. All exports remain private uncertain drafts, never
verified procedures or publication authority. Confidence fields remain separate;
probability cannot promote evidence. A named reviewer is a declaration, not
authenticated identity. Nonblank evidence descriptions cannot prove truth;
semantic review and the separate procedure gate remain necessary.

Direct editorial render/narrate commands still accept private draft plans;
teachability is enforced for the automatic workflow, not an authorization boundary
for every manually authored draft. Pacing limits apply to all narration paths:
maximum 2 seconds added hold and minimum 75% unextended source per segment.
These are configurable-in-code editorial defaults, not scientifically calibrated
learning thresholds. No silent speech truncation, acceleration or invented footage.

## Evaluation contract

Freeze source hashes and independently annotated important actions before comparing
manual-only, assisted and automated workflows. Preserve original failures. Report
per source minute: recovered/missed actions, false narration claims, corrections,
active reviewer minutes, wall-clock latency, measured motion fraction, output/source
length, reproducibility by a first-time viewer, and evidence coverage of claims.
Do not substitute source duration for motion or a known-case repair for a blind test.

Report active human savings separately from sequential wall-clock savings:
manual active minutes minus assisted active minutes; and manual elapsed minus
(machine elapsed + review/correction elapsed) only when stages are sequential.
Record actual overlap for concurrent work. Separate API charges/credits, local
compute, infrastructure amortization and human labor. Unknown costs stay unknown.
No economic benefit is established without observed manual and assisted trials.

## Scope

This change contains narration inflation and unreviewed automatic narration.
It does not solve general visual comprehension, automatically authenticate causal
actions, establish 70–80% pixel motion, or prove reviewer time savings.
