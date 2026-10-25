# Watch frontier: bounded consequence-first reinspection

Separate experimental branch, stacked on the reviewed teachability dependency;
PR39 implementation and review are unchanged. No automatic narration or promotion.

```powershell
.\bin\beast.ps1 watch-rewind-eval --review watched\assembled-watch-03\review --units proofs\watch-teachability\result-unit.json --output watched\NEW-REWIND-RUN
```

This uses the existing Watch inspection executor, lock, write-ahead receipts,
source/frame hashes and retained timeline. CPU only, no API spend or GPU lease.
Inputs require one explicitly reviewed result-only unit. Its latest cited frame
is a declared result anchor, NOT an automatically located first-result frame.

Both arms receive the same source-linked search window, maximum16 charged frames
and60seconds. The deterministic Watch adapter's interval is intersected with the
same window and its sampling rate fitted to the frame cap. The rewind arm spends
five coarse requests, measures RGB mean absolute changes, then spends remaining
requests inside the largest-change adjacent interval. Highest change is not
semantic relevance. Repeated endpoints count against the budget; unique frames
are reported separately. Frame extraction is chronological within each request.
This is consequence-first interval selection, not backward video playback.

Both retain full-frame context at720px height. Control/action debt stays unresolved
and reproducibility untested. Confidence placeholders in the existing scheduling
contract are zero/uncalibrated; unknown evidence confidence remains null in debt.
No semantic detector or procedure verifier is installed by this change.

## Measurement boundary

Single known case; no blind corpus or learned policy. Reports include observed
elapsed inspection/measurement seconds, charged/unique frames and per-frame hashes.
Elapsed excludes initial source copying/setup. Source copies are hash-checked by
the executor. Execution order is fixed, so cache warming can bias timing; do not
infer a speed advantage. No model GPU work occurs; GPU-seconds and action accuracy
are not estimated. Semantic metrics remain null, not a fabricated zero-error rate.

Automatic resume is forbidden: choose a fresh output directory. Failed runs retain
failure/intent and cannot be scored as completed; interrupted executor locks are
preserved for explicit reconciliation. The interface is cooperative in-process,
not a sandbox against a malicious policy with arbitrary filesystem access.

## Next experiment gates

Freeze independently annotated recordings containing visible inputs, missing
inputs, brief menus, delayed results and competing preceding actions. Policies
must not receive annotations. Compare original Watch, bounded Watch and rewind
with identical budgets and counterbalanced order. Measure action evidence recall,
false causal claims and human review time independently. Only then add OCR/pointer
event association, cross-region graphs and learned inspection scheduling.

Prior art informing the experiment: Watch's own seek/escalation contracts;
[Google selective video inspection](https://ai.google.dev/gemini-api/docs/video-understanding)
and [NVIDIA regional inference](https://developer.nvidia.com/blog/applying-inference-over-specific-frame-regions-with-nvidia-deepstream/).
No novelty or imported speedup claim. This experiment tests scheduling mechanics
before connecting higher-cost semantic backends.
