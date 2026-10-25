# Independent narration and explanation review

Reviewer: separate Codex agent `/root/training_review`, 2026-09-19.

**Disposition: accepted for bounded draft PR review, not merge approval.**
The retained three-case repair produces coarse explanations consistent with the
inspected screenshots and renders them as synthetic speech over original video.
This does **not** establish generalized automatic lesson accuracy. The earlier
three-case trial contained two semantic failures despite successful assembly.
No source files or previous review reports were changed by this reviewer.

## Personally verified

- Read the implementation of narration, automatic explanation, orchestration,
  and decoded-output verification, under the previously read constitution and
  independent-review protocol. The code-review skill guided boundary inspection.
- Ran `python -m pytest tests/test_watch_narration.py tests/test_watch_training.py -q`:
  **28 passed** (17 narration/explanation tests and 11 preceding training tests).
  Tests include duration limits, audio/source retention arithmetic, attempted
  procedure promotion, fixed causal caution, altered media/segment hashes,
  missing review permission, negative duration and blank narration. These are
  contract/preflight tests, not 28 successful real-video comprehension cases.
- Decoded the original narration MP4 and verified real non-silent audio, its hash,
  and synthetic/held labels. Found that labels covered source application controls.
  Inspected repair: labels now sit in an added lower band; explicit FFmpeg stream
  mapping selects original video and newly generated narration audio.
- Independently verified single-case output
  `watched/automatic-narrated-02/narrated/narrated-training.mp4`, SHA256
  `31faa46f474f8568aa0b20694fb3308cdf761eccfbf0d7495a6392ab54e8221f`.
  Original source-region RGB mean absolute error was 0.1572732205. Held output
  versus the actual final source frame was 0.0688943142; held pictures at 3 and
  5 seconds were identical in the source region. OCR on decoded labels confirmed
  synthetic narration before the hold and an additional held-source label after it.
- Independently decoded the final ROI repair MP4
  `watched/automatic-narrated-roi-04/narrated/narrated-training.mp4` and verified
  SHA256 `241536688fc8834bab908d0a2120ffcae231ca05c98ae796c4190c868710bd63`.
  At 0.5 seconds into each output segment, original source-region errors were
  **0.0253490307, 0.0761371528, 0.1570345052**. At 0.5 seconds into each hold,
  errors versus each final source frame were **0.0848379630, 0.1203642216,
  0.0647424769**. These are measured preservation under lossy re-encoding, not
  byte-identical pixels.
- Inspected the independently transcribed audio receipt at
  `watched/narration-verification-roi-04/report.json`: normalized word-sequence
  similarity 1.0, decoded audio RMS 0.0747334419, matching output hash. The builder
  executed Whisper; reviewer inspected its retained expected/recognized text and
  hash link rather than rerunning inference. ASR is fallible and does not establish
  semantic truth, universal pronunciation, or human listening approval.

## Semantic failure and targeted repair

I personally viewed the actual 1s/2s and 4s/5s frame pairs. They visibly change
from User Perspective to Front Orthographic and from User Perspective to Right
Orthographic, respectively. Before repair:

1. The first explanation reported a purple-to-pink torso color change and missed
   the prominent view change. Treating appearance differences as a material/color
   property change was unsupported.
2. The second reported an unchanged appearance/interface despite a changed view
   label, orientation and grid. This was contradicted by the source frames.
3. The coarse viewport-to-instructional-slide explanation agreed with the known
   17s/18s transition, although the underlying frame observer imperfectly described
   task-switcher thumbnails as reference windows.

ROI repair reuses six retained frame observations with checked frame identity,
records their hashes, and adds upper-left-region OCR with source hash, crop box,
scale, inversion and derived-byte hash. All three repaired **coarse captions**
agree with inspected evidence: Front Orthographic, Right Orthographic, and the
instructional slide transition. Neither input actions nor causes are established.
The code appends a fixed causal-uncertainty statement regardless of model certainty;
perception/transition/procedure confidences remain independent nulls, and plans
remain uncertain, review-required and publication-disabled.

This is a targeted repair after the failed examples were already examined, using
new measurements and comparison instructions. It is **not a blind benchmark,
calibrated 3/3 accuracy claim, or proof of coverage of the entire video**. Earlier
failed artifacts are retained separately; successful speech replication cannot
convert a false explanation into a true one.

## Boundaries and residuals

- The narrator uses fixed local Kokoro `af_heart`, CPU provider checking and
  model/voice hashes. No speaker cloning or new scene imagery is used. Speech
  longer than the source is represented by explicitly labeled real-frame holds.
- Media hashes, review flags, source-duration checks, source-relative intervals,
  exclusive outputs and failure receipts provide local custody/accounting. These
  are not signed manifests or protection from rewriting all local files together.
- Null confidence and draft flags prevent promotion; they do not make generated
  caption text inherently accurate. Automatic mode can still narrate an incorrect
  explanation as an explicitly unverified draft. Human semantic review is required
  before accepting it as instruction.
- The upper-left OCR heuristic and repaired descriptions are established only
  for these named UI examples. Other layouts, languages, occlusion, misleading
  narration, brief events and full-length coverage have not been validated here.
- TTS NaN/silence/provider guards are implemented but not all fault-injected in
  the new suite. Model generation lacks a hard whole-run subprocess deadline;
  per-call network/FFmpeg limits are not an aggregate runtime guarantee.
- Duration checks permit small encoding tolerances; exact sample-level cross-
  segment A/V alignment and large edit lists are not proved. Font/codec/platform
  breadth and rights/publication approval remain open.
- Reviewer did not independently execute the builder's entire repository suite
  or a clean-machine install. No production, scale, or main-branch merge claim.

## Frozen implementation bytes

Reviewed implementation commit: `b94e80103359ffdd22d8fec5eddb7a3945073804`.
Independently confirmed all five files below match their Git blobs byte-for-byte.
Rechecked the final change that defers optional TTS imports until after preflight,
and the integer/nonnegative source-coordinate check; 28 focused tests still pass.
The retained real output preceded these preflight-only changes; no speech/video
generation algorithm changed. A later commit must preserve these bytes or
receive an affected-scope recheck; this report does not approve an arbitrary
later head by branch name.

| File | SHA256 |
|---|---|
| scripts/narrate_watch_training.py | f8bad8c9931440452047f3d9eb14a01a1978123624b975a6c4d81fd5072e3331 |
| scripts/draft_watch_explanations.py | ea800634874dd3bd705ed16d59eacff788796dfae810e1a9e82a8bab0f693085 |
| scripts/watch_training.py | f0a0754066b4a9a062990773a8922e7d873c3f686109784319108448b928cfdc |
| scripts/verify_watch_narration.py | 8f18b5573d67a6b2ef5bc6b48435b05cde2d79368ade5733bbeade3336433bac |
| tests/test_watch_narration.py | bf3a10c85e0ccb48c9af2135547d146550bfc8db860e1547cff0bff14bd3452b |
