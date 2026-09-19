# Teachability and pacing containment — 2026-09-19

Failure: a 6-second selection became a 35.309-second narrated draft, dominated
by 29.267 seconds of added holds. Render/audio correctness tests did not assess
instructional value or pacing. The mechanism was unrestricted extension to fit
model-written prose, plus automatic narration of unreviewed observations.

Controls: automatic proposals stop at pending teachability review; separate
confidence values cannot approve them. Source/frame hashes are checked before
draft export. Narration rejects >2s added hold or <75% unextended source duration
per segment. Missing declared causal evidence requests recapture. Direct manual
editorial drafts are still allowed; no claim of an authenticated approval system.

Actual CLI evidence:

- `automatic-review-queue.json`: all three old proposals require review;
  no eligible narration plan exported.
- `pacing-refusal.json`: actual Kokoro speech12.608s for source2s would require
 10.8667s added hold. CLI exits nonzero, retains WAV and review request, no final MP4.
- `result-review.json`: separate reviewer visually inspected and hashed the
  two source frames. Supports only “Front orthographic view appears.”
- `result-unit.json` -> `watch-instruction-gate` -> `watch-training render` ->
  `watch-narrate`: source2s, speech1.962667s, timeline2.233333s, addedhold0.233333s,
  unextended-source fraction89.552%. MP4 container duration2.276s includes encoding
  overhead. This is result-only, not a recovered causal procedure.
- `result-verification.json`: decoded speech matches the four-word sentence;
  source-picture mean absolute pixel difference0.025488 after lossy encoding.
  Short hold is not covered by the verifier's >0.5s held-frame branch.

Output retained locally:
`watched/teachability-result-voice-01/narrated-training.mp4`
SHA256 `29470e6e87170eda5b584ba0455ac6bc6397c2de1ab5f1516109b5aab8c26c7d`.
No cloud inference, GPU inference or paid credits used for this change's media
checks. Electricity, development and review labor are not metered here.

Validation: doctor33OK/1optionalComfyUIoffline/0fail; corevalidateOK.
`python -m pytest -q -m 'not live_gpu'`:381passed,1Windows symlink skip,
7liveGPU deselected. New tests include six filesystem/contract attacks, five
old-overflow regressions and a mocked auto-orchestration no-render/no-speech
test. These tests are not real video comprehension tests; real media checks above
are separate. No model re-run was needed for the previously reviewed frames.

Containment, not generalized fix: semantic classification/reviewer declarations
can still be wrong; real pixel-motion share, blind action recovery, authenticated
review and manual-versus-assisted time savings are unproved. A short accurate
result description is not yet a reproducible lesson. No source redistribution
permission, procedure publication or main-branch merge is inferred.
