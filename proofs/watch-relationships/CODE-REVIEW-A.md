# Independent code review A

Scope: watch/relationships.py, scripts/evaluate_watch_relationships.py, bench/watch-relationships-v1.json and directly imported custody/routing code. Frozen labels were not modified. Review concerns the pre-run implementation observed on 2026-09-19, before the builder's subsequent changes.

## Blocking custody defect

scripts/evaluate_watch_relationships.py:100 calls changes(output,frames). The imported scripts/evaluate_watch_rewind.py:20 implementation reopens image paths and never checks supplied SHA-256, path containment, or an immutable snapshot. OCR itself correctly hashes its byte snapshot and passes exactly those bytes to both Tesseract and PIL, but conditional routing can inspect different bytes from those whose identity appears in the OCR receipt. Fix the routing boundary by computing differences from verified byte snapshots; a hash followed by reopening is still vulnerable to replacement.

Read-only reproducer passed native f-0027.jpg and f-0028.jpg from case-01 with both declared hashes replaced in memory by 64 zeroes to changes(). It accepted the mismatching identities and returned start_ms=1040,end_ms=1080,mean_absolute_difference=2.012062355324074. No file was modified by the probe.

## Additional review findings

- Freeze provenance is incomplete: intent hashes only relationships.py and the evaluator. Actual perception and routing also depend on parse_overlay, changes, rewind, inspection, inspection_runtime, seek and core. Hash those dependencies before the observer run so a report is reproducible against its actual executed logic.
- Each arm independently establishes source_hash. A source replacement between arms can produce two individually successful arms on different clips. Establish the per-case identity once and require both arms match it; scoring must additionally match frozen visual-label source hashes. Source hashing before and after each individual arm is useful but does not enforce the pair's shared input.
- Result end_ms grows on repeated status observations, but result frame_refs retains only the first frame. Full report observations preserve the omitted supporting rows, so evidence is available indirectly. Append the relevant endpoint references or explicitly document that consumers must resolve duration evidence against observations.
- The arm timer starts after source digest/copy/timeline retention and elapsed is measured before final source digest/report retention. Therefore wall_seconds measures the inspection/OCR region, not total arm runtime. Either define that scope explicitly in the protocol or move the clock/cap boundary to include all arm work. This does not increase the declared 16 requested-frame or 16 OCR caps.
- run() truncates probed duration by 80 ms; protocol calls baseline uniform across retained source without stating that exclusion. Record the exact inspected interval and omitted tail. The two arms share the exclusion, but endpoint recall claims must respect it.
- Observations label requested extraction times, while ffmpeg seeks and returns a native presentation. They are not verified actual native frame PTS. Scoring against native visual-label intervals needs declared seek/frame tolerance; avoid an exact native timestamp claim from source_seconds alone.

## Reviewed behavior that is appropriately bounded

Event grouping only joins consecutive inspected DOWN rows with equal modality/key/control. An observed absent/UP row separates events; the unsampled continuity flag remains unknown. Unseen releases can still be missed, so a grouped event is an observation proposal, not proof of one physical press.

Temporal candidate construction excludes a result already present before a later input and requires a distinct earlier observed state. Control identity remains separately recorded from result identity. The stop condition is explicitly named temporal-candidate completeness; it is not causal or procedure sufficiency. Causal sufficiency is unconditionally unknown, accepted causal chains is empty, publication is false, and confidence is uncalibrated/null. This is an abstention policy, not learned causal discrimination or demonstrated causal recovery.

The experiment declares requested-frame rather than internal-codec-decode parity, and its zero GPU/model-token measurements match the CPU OCR path. Source and OCR snapshot hash checks fail closed inside the inspected paths. Labels are hashed without content parsing by the observer entry point.

## Validation

`python -m pytest tests/test_watch_relationships.py -q -p no:cacheprovider` with PYTHONDONTWRITEBYTECODE=1: 8 passed in 0.24 seconds. This verifies the existing unit scenarios; it does not cover the demonstrated routing custody gap, full observer run, scoring implementation, or native timing alignment. No observer evaluation was run by this reviewer.
