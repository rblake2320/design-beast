# PR #42 requested-output-frame budget correction

Correction baseline: `4a7207b8ef758d7a4f14e0339cfb09239ec05283`.
This append-only note supersedes the decoder-budget interpretation, not the
retained measurements or scores. No media experiment is rerun for this correction.

## Preserved original overstatement

- `docs/WATCH-POSITIVE-CONTROLS.md` at the baseline said
  `16requests,16decodes,16OCRcalls`.
- `comparison/protocol.json` retains `"decode_cap_per_arm": 16`.
- `PROOF.md` retains `16requests/decodes/OCRcalls`.
- `INDEPENDENT-REVIEW.md` retains `16 requests, 16 decodes, 16 OCR calls`.
- The baseline comparison script emitted that misleading protocol field.

The historical proof files, labels, media, observer reports, scores, and original
review remain unchanged. Historical `decode_cap_per_arm` must be interpreted as
the declared requested-output-frame cap, not as measured internal decoder work.

## Correct resource interpretation

Each arm has a cap of 16 charged requested output-frame timestamps. Repeated
endpoints count against it; unique retained frames are reported separately.
The baseline arms supplied 16 unique frames to OCR, and rewind supplied 14;
both charged 16 sampling requests. Other declared caps remain 16 OCR calls,
zero model tokens, 60 seconds sampling and 60 seconds OCR per arm.

`watch.inspection_runtime.execute_inspection` charges planned output timestamps;
`watch.seek.reinspect` reuses existing timestamps where possible;
`watch.core.extract_frame` asks FFmpeg for one output using `-frames:v 1`.
None counts frames the codec processes internally while seeking or reconstructing
that output. The new protocol labels the cap `requested_output_frame_cap_per_arm`,
sets `internal_decoder_frames_measured` to false and
`internal_decoder_frame_cap` to null. It no longer emits `decode_cap_per_arm`.

Cause: output request count was mislabeled as decoder work. Existing scoring and
review checked recovered indicators and matched declared caps, not this unit
distinction. The scoped sweep found the script, active guide, historical protocol,
proof and review above; historical wording is corrected by this note, not erased.

## Verification scope

`tests/test_watch_positive_budget_wording.py` exercises the real protocol-writing
entry point, deliberately halting before media work. It checks the new resource
fields, rejects the old field, retains a failure rather than fabricating a
completed run, and checks the active guide's measurement disclosure. These are
report-contract tests, not decoder measurements. The observer, schedules and
scorer are unchanged; the retained 3/3 tie and comparative graduation failure
remain unchanged. Fresh independent review is required before updating PR #42.

Local correction checks: 11 passed (two report-contract tests and nine existing
input-overlay tests); retained JUnit receipt: `budget-correction-tests.xml`.
Focused Ruff E9/F63/F7/F82 and `git diff --check` passed. Core validation passed
with eight capabilities and one pack. Doctor reported missing FFmpeg/ffprobe on
this worktree's PATH and optional ComfyUI offline; no media/GPU work was needed
or attempted. The contract test stops at a stubbed media boundary; it is not
an additional real-OCR execution. Historical real-media receipts are unchanged.
