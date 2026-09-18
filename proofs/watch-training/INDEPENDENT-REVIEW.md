# Independent source-faithful training review

Reviewer: separate Codex agent `/root/training_review`, 2026-09-18.

Disposition: **bounded draft integration accepted for draft PR review**, not a
merge approval, autonomous lesson-generation claim, or production-readiness claim.
No source files were edited by this reviewer.

## Independently checked

- Read the constitution, Beast contract/capability boundaries, CLAUDE.md rule 8,
  and multi-agent review runbook. Doctor: 33 OK, optional ComfyUI offline,
  zero failing checks. Core: 8 capabilities and 1 pack validate.
- Focused command `python -m pytest tests/test_watch_training.py watch/tests -q -rs`:
  **114 passed, 1 skipped**. The skip is the pre-existing Windows symlink privilege
  test, not a pass. The 11 training tests cover contracts, clock disagreement and
  altered review data; they are not real-media comprehension tests.
- Inspected actual desktop and mobile screenshots in `ui-06`, exported strict
  plan, and browser report: 1280x720 playback advanced to 0.262526 seconds,
  seeking to 10 seconds, one operator-authored segment, no page errors and no
  mobile overflow. The visible interface shows actual Blender footage, adjacent
  stills, measured regions and explicit uncertainty. Browser execution was by
  the builder; reviewer independently inspected its retained artifacts.
- Independently decoded final MP4s with FFmpeg, rather than relying on duration
  or screenshots alone. Short output `watched/training-render-04` contains the
  complete explanatory caption (confirmed by Tesseract on decoded caption pixels).
  Its source-region mean absolute RGB error at output 0.25 seconds against source
  9.25 seconds was **0.2748281973**, consistent with lossy re-encoding.
- Independently verified the final two-segment MP4 in
  `watched/training-multisegment-05/render`: output SHA256
  `f1b0c84b3fefc4e81508a56f2edce8045f23798a5cc26188a22e4a0a1fd67695`.
  Decoded source-region errors at 0.5 and 1.5 seconds were respectively
  **0.1987825521 and 0.1686111111**. All **11 nonempty caption lines** had visible
  light pixels, with none in the final 24-pixel right margin. Visually inspected
  the retained 500-character wide-letter caption preview. Two one-second
  segments retain the 9000ms original-source offset, uniform 1280x1108 output,
  and publication/procedure flags false.
- Reviewed source/frame/state hash checks, path containment, exclusive outputs,
  write-ahead intents and failure receipts. Source text is JSON-escaped and
  displayed as text, not HTML. Captions pass through fixed text filenames with
  expansion disabled, not shell interpolation. No application executor or
  procedure promotion is connected to this draft path.

## Findings and closure

1. **Real rendered captions were missing despite valid MP4/duration.** Reviewer
   observed only the draft heading in render-02 and independently reproduced
   that result by OCR on the decoded MP4 caption region. Windows multiline text
   handling/layout assumptions escaped duration-only checks. Builder changed to
   LF-only, separately positioned single-line text files; final rendered pixels,
   complete short-caption OCR and 500-character multiline test close the named
   fixture. Original failures remain described and retained; no earlier render
   is retroactively called a pass.
2. **UI and Python draft bounds disagreed.** UI accepted sub-500ms intervals and
   weakly checked restored drafts. Inspected repaired duration, caption, state,
   approval and frame-reference validation. Python remains fail-closed.
3. **Variable caption-band dimensions / wide text clipping.** Inspected shared
   maximum band height across segments, conservative wrapping and explicit font
   file. Final multi-segment pixels verify the named wide-letter fixture.
4. **Source/clip clock confusion.** Inspected `clip_stamps`, disagreement
   rejection, new offset regression and actual nonzero-start retained run.
   OmniParser's older source-time labeling and the temporal encoder's zero-based
   frozen-fixture restriction are outside this CPU training path; do not claim
   that arbitrary-offset multimodal fusion was repaired.

## Residual boundaries

- Captions are operator authored and semantically unverified. This is a working
  draft assembly connection, not automatic understanding/narration of arbitrary
  videos or recovery of every silent action.
- Clipstitch is separately registered, not imported or proved to select relevant
  instructional visuals. Unmerged live acquisition work is not activated.
- Local custody hashes detect changes; they are not signatures or protection
  against an attacker rewriting all local manifests and hashes together.
- Source codecs depend on installed browser support; bundled Chromium failed
  this H.264 fixture. Browser proof uses installed Chrome. General multilingual
  typography, long-form edits and arbitrary dimensions/codecs remain untested.
- Many non-frame-aligned intervals can accumulate 30fps rounding; the 150ms
  duration gate fails closed, rather than establishing arbitrary edit accuracy.
- A restored frame reference containing extra fields can still pass UI filtering
  while Python rejects it. This is a draft-export usability residual, not
  execution authority or a source-custody bypass.
- Raw MP4s remain local under ignored `watched/`; published reports/previews do
  not alone permit clean-machine reproduction without the retained source.

## Reviewed implementation snapshot

Reviewed implementation commit: `60dc3060c669b32e7d73ba7b7ee13d639e0f42c2`
(draft PR #37). Independently confirmed all seven files below match their exact
Git blobs byte-for-byte, not just normalized text. Later changes require
rechecking the affected scope; this is not approval of a future PR head merely
sharing a branch name. The builder reported 346 full-suite passes, one skip and
seven live-GPU deselections; reviewer personally executed the 114-test focused
suite above, not that separate full-suite run.

| File | SHA256 |
|---|---|
| scripts/watch_training.py | 39ce5c74dae7636cedcac2b1ad9512990550d5bb4d34c8c5eb2de8c6cca30209 |
| scripts/build_watch_review.py | 54de94eeb44804aeed92a560ac9aac81a9428a161d277068e8b1029e91bc50c9 |
| scripts/render_watch_training.py | b2121896c0ce5203c1ef1b06fa2d8bec5eaeda07b71204a061c0acd22d7ad190 |
| scripts/watch_perception.py | 1f8e92283775a2708cf3272efc2932a9a98e9f093a16afd8be83e8687cad6bd0 |
| watch/training_draft.py | 5674be67a82d1fff150dbcc3ea1d7eb50738d29ab92136a242006c48e074b2d5 |
| watch/review_player.html | 1d338d717166e28f64a7b4caa682a92979797e6d2dd90b627e84ac715693a55f |
| tests/test_watch_training.py | cf423682d3c1fef980b9c8505188216f2d305f1baf07ac742750e447b818c81e |
