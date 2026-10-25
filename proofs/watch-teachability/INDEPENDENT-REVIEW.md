# Independent teachability and pacing review

Reviewer: `/root/training_review`, 2026-09-19. Implementation reviewed:
`64895768f23344ba335f5b776f1d403c4153a892` (draft PR #39).

**Disposition: accepted for the bounded containment claim and draft review.**
This is not merge approval, proof of automatic teaching quality, or a verified
causal procedure. I authored only `result-review.json` and this independent
report; no implementation or earlier review reports were changed.

## Checks personally performed

- Read the new instruction contract/gate, automatic orchestration changes,
  pacing implementation, tests and claim boundaries under the repository's
  independent-review rules and engineering constitution.
- Ran `python -m pytest tests/test_watch_teachability.py tests/test_watch_narration.py tests/test_watch_training.py -q`
  against the committed implementation: **46 passed**. This includes six
  filesystem/contract attack cases and a mocked orchestration test that fails
  if automatic proposals reach rendering or narration. These are not 46 real
  instructional-video evaluations.
- Inspected the real old-draft gate receipt: all three proposals are pending,
  zero eligible units, `review_required_no_narration`. Confirmed code exports no
  training plan when none qualify, and `auto` stops at the gate.
- Inspected the actual pacing refusal: two seconds of source plus 12.608 seconds
  of generated speech would need 10.866667 seconds of hold. Retained directory
  contains WAV, intent, classified review request and failure, **no final MP4**.
  Reviewer did not rerun the already completed TTS refusal experiment.
- Freshly viewed and hash-checked source frames at 1000ms and 2000ms. The former
  shows User Perspective (Local); the latter Front Orthographic (Local). I
  accepted only **“Front orthographic view appears.”** in the 500..2500ms interval,
  as detailed in `result-review.json`. Exact user action, transition instant,
  causality, continuous coverage and reproducibility were not accepted.
- Checked that `result-unit.json` faithfully uses that result-only review and
  does not expand it into an action claim. Output still requires human review,
  remains uncertain, and cannot publish or certify a procedure.
- Independently hashed and decoded the final short MP4:
  `watched/teachability-result-voice-01/narrated-training.mp4`, SHA256
  `29470e6e87170eda5b584ba0455ac6bc6397c2de1ab5f1516109b5aab8c26c7d`.
  Source-picture RGB mean absolute error at 0.5s versus the input segment was
  **0.0254879196**. The short hold at 2.1s versus the actual final source frame
  had error **0.0946932870**. Comparison of held source regions at 2.1s and 2.2s
  yielded **0.0009512442**, consistent with lossy encoding of the held picture.
  This independently covers the short hold omitted by the verifier's >0.5s rule.
- OCR on decoded lower-band pixels confirms the synthetic-narration label at
  1s and the added held-source label at 2.1s. These labels do not cover the
  original application controls.
- Inspected the builder-executed ASR receipt: the decoded four-word sentence
  matches expected normalized words (similarity 1.0), audio RMS 0.0728972554,
  and matching final video hash. I independently verified media/pixels but did
  not repeat Whisper inference or conduct a separate human listening test.

## Review findings and repair

1. The first gate version trusted frame references in the manifest without
   checking current image bytes. Final implementation checks frame containment
   and SHA256 before export; hostile changed-frame/escape cases pass as denials.
2. Initial parse-then-rehash reads could bind intent receipts to different bytes
   than were evaluated. Final manifest/unit parsing and SHA256 share one retained
   byte snapshot. Source media and frames are separately checked before export.
3. Automatic model output now remains pending/ambiguous instead of proceeding
   directly to speech. All three confidence fields can be 1.0 without promotion.
4. Pacing rejects excessive extension rather than silently truncating speech,
   speeding it up, or fabricating scenes. Limits are maximum two seconds of added
   hold and at least 75% unextended source **on the planned segment timeline**.
   The short proof has two seconds source, 1.962667 seconds speech, 2.233333 seconds
   planned timeline and 0.233333 seconds hold (89.552% source). Container duration
   is 2.276 seconds; encoding overhead is explicitly separate.

## Residual boundaries

- The gate validates declared review/evidence links, not reviewer authentication
  or semantic truth. Nonempty action/control/result strings do not prove a causal
  chain. An accepted result is not automatically an accepted action.
- Direct manual editorial render/narrate paths remain allowed for private drafts;
  teachability is not a cryptographic authorization boundary over every command.
- Pacing limits do not establish pixel-motion percentage, learning effectiveness,
  useful instructional coverage or lower reviewer labor. Measured motion remains
  null; no 70–80% motion claim follows from source-duration percentage.
- Source hashes/frames do not establish rights clearance or publication approval.
  A four-word correct result sentence is not a reproducible lesson.
- The builder reports full-suite 381 passes, one Windows symlink skip and seven
  live-GPU deselections. Reviewer personally ran the focused 46-test suite above,
  not that full suite. Blind action-recovery, manual/assisted economic comparison,
  clean-install proof and production-scale operation remain outside this review.
- Earlier narration and semantic failures remain valid failed evidence; this
  containment does not retroactively make those drafts instructional successes.

## Exact reviewed Git bytes

All six files below were independently confirmed byte-identical between the
working tree and Git blobs at the reviewed commit. Later implementation changes
need affected-scope re-review; a report-only commit does not expand this verdict.

| File | SHA256 |
|---|---|
| watch/teachability.py | 0915693b588c4f9c0bcf6f1a2ef135e6f37ad120234014bc03cc326e4fea69e1 |
| scripts/gate_watch_instruction.py | 2107e62d4e5c31f0a1848a2c2418c697aa19fc8100d0bbbb56e2bc8035c64b6c |
| scripts/narrate_watch_training.py | a6a33f0f1eb5f868fe6c5a869c8588fe8accd84904cb92220881adb163003b3b |
| scripts/watch_training.py | 77d59ec4dbe03d02c901a173edd17a5e0592a73be8507261283c192e57fc45a2 |
| tests/test_watch_teachability.py | 4a80d82ae751e1f1895c1a616ccaa2af37d93c27053e16ea351ae34cab6eb993 |
| tests/test_watch_narration.py | 304f7b9348c48504c86d4f18fcf31a4049c007c7e9c2a86411abe3cea6c1981c |
