# Watch inspection policies v1

This is an extension beside `watch.seek`, not a perception engine. The policy
recommends epistemic work. Watch owns extraction, custody, gates and evidence classes.

`watch.inspection.InspectionPolicy` accepts a frozen `InspectionContext` and returns
a strict `InspectionDecision`. Unknown keys, invalid probabilities, reversed or
out-of-source intervals and invalid regions are rejected. Confidence dimensions
are independent: perception, transition, procedure. None grants acceptance authority.

The deterministic adapter calls existing `escalation_for` and `SEEK_LEVELS`.
`plan_seek` uses existing `seek_times`. The v1 adapter makes one bounded inspection;
it stops after that request, preserving uncertainty. This is not a learned
multi-step attention policy. Requests for OCR, tracking, region expansion or slow
review are representable but execution fails closed until an executor exists.

`execute_inspection` invokes real `watch.seek.reinspect`; it retains context,
decision, source/timeline hashes, exact sampling plan, frame hashes, cost and time.
An exclusive bundle lock prevents overlapping policy writers. A durable exclusive
intent prevents automatic replay. Failures retain a lock and failure receipt;
an operator must inspect/reconcile the bundle before releasing that lock. Legacy
direct calls to `reinspect` do not participate in this lock: do not mix concurrent
writers. This is a cooperative local boundary, not a hostile-process sandbox.

Frame admission happens before timestamp allocation. Extraction subprocesses share
a monotonic deadline. Provider/GPU calls do not occur. Passed Watch gate records
require evidence references. Gate references are supplied by trusted validators;
schema validity alone does not prove their truth. A transition gate alone yields
`evidence_supported_transition`. A procedure additionally requires independent
causal and reproducibility gates. Stopping never means accepting.

## Frozen control experiment

Run against the committed corpus; do not regenerate it for comparisons:

```powershell
python scripts/evaluate_watch_inspection.py evaluate `
  --corpus proofs/watch-inspection/corpus `
  --manifest-sha256 15323c1157d4898a68ee52b8cbe5a6d20e63d4402c2826905a084c140dfd4a07 `
  --ffmpeg <absolute-path-to-ffmpeg> --output <new-output-directory>
```

The four retained synthetic videos are simple luminance changes/absence controls,
not screen recordings of user actions. Every backend has the same 25-frame,
one-inspection, 60-second cap. Fixed sampling uses 1 fps; the existing deterministic
Watch schedule uses 4 fps for the same initial uncertainty. Gate: absolute mean
luminance change above 20 between requested frames. This tests real extraction and
control plumbing, not semantic perception. Case-level pixel-change recall is not
event-level or procedure accuracy. Stratum names indicate intended controls, not
validation of real silent actions, causes or occlusions.

Policy input excludes source paths, strata, hidden ground truth and prior sampling
decisions. Only explicit inspection requests expose frames. Ground truth is read by
the evaluator. This in-process split is not secure against malicious backend code;
isolation is required before adding untrusted model workers. The manifest and
video hashes are frozen and checked before evaluation writes. Empty/unsafe corpora
are rejected. Outputs are exclusive; failures are not overwritten by later runs.

The report records per-case latency, frames, provider cost, safety failures and
three Brier components. Constants in this control are not calibrated predictions.
Misleading narration, version drift, live capture and real tutorial test sets remain
explicitly absent. Jev, slow VLM and trained local policy are marked not run.
No efficiency or generalized understanding claim follows from passing controls.

## SemIf inspiration, not a dependency

Inspected upstream commit `b9cb32537e78be65f19abfcb1de8fc504b627d84`:

- https://github.com/TheoLeeCJ/SemIf/blob/b9cb32537e78be65f19abfcb1de8fc504b627d84/src/semif_phase1/direct.py
- https://github.com/TheoLeeCJ/SemIf/blob/b9cb32537e78be65f19abfcb1de8fc504b627d84/src/semif_phase1/core.py

Useful concepts: declared option logits, exact single-token boundary checks,
refusing prompt truncation, pinned model revisions, prompt hashes, and explicit
uncalibrated conditional-score labeling. `OptionReadout` adopts the audit pattern
as an original optional contract, separate from confidence and evidence gates.
No upstream code is vendored, no model downloaded, and no SemIf/Jev runtime result
is claimed. Prefix reuse must later be compared with fresh scoring for decision
drift, not assumed equivalent. Source README reports drift in its own experiment.
