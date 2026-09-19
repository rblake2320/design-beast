# Automatic narrated draft: bounded real proof,2026-09-19

Final local artifact:
`watched/automatic-narrated-roi-04/narrated/narrated-training.mp4`.
SHA256:`241536688fc8834bab908d0a2120ffcae231ca05c98ae796c4190c868710bd63`.

Actual workflow:61 existing frame measurements ->3 separated visual-change
candidates ->6 separately observed source frames ->targeted region OCR ->3
model-written explanations ->real source clips/captions ->local Kokoro speech.
No transcript, manually written event explanations, cloned voice, generated
scene pictures or paid provider used. Fixed causal caution is code-authored.
The repair reused hash-bound observations rather than repeating six prior calls.

## Outcome evidence

- Named repaired transitions:User Perspective->Front Orthographic;
  User Perspective->Right Orthographic; modeling interface->instructional slide.
- Separate reviewer inspected source frames and agreed with these3 coarse
  descriptions. This is targeted repair of known failures, not a blind benchmark.
- Independent CPU Whisper recovered every normalized word in the final MP4:
  sequence similarity1.0. This checks speech content, not truth of the caption.
- Output source-region mean pixel errors:<0.158; held-frame errors:<0.121,
  consistent with lossy encoding. Original footage is not obscured by labels.
- Narration overflow uses a labeled hold of the actual last source frame. Each
  segment retains its real source interval separately from expanded output time.
- Local doctor33OK, optional ComfyUI offline, zero failures after process-local
  FFmpeg PATH setup. No user process stopped or global configuration changed.

## Failed evidence and permanent checks

`failed-multiframe/`:two-image prompting described a character viewport while
the later frame was a slide. Separate-frame observation repaired that coarse case.

`failed-three-segment/`:two of three captions still failed, describing a color
change and no change instead of two viewport orientation changes. Whole-frame
OCR had missed small labels; single-frame model descriptions also missed them.
Duration/ASR/pixel checks could not catch semantic falsehoods. Independent image
review caught this escape. Generic upper-left3x OCR recovered the labels and
comparison then produced the supported coarse descriptions. `roi-repair/`
retains crop boxes, transform hashes, text, prompts and outputs. No field-of-view
label answer was placed in the model prompt or OCR whitelist.

Permanent structural checks: source/segment tamper refusals, positive interval
validation, actual segment-duration checks, explicit audio/video mapping,
CPU-provider enforcement, finite/non-silent waveform checks, unverified state
and review-gate checks, spoken causal caution independent of model confidence,
and decoded audio/source/held-image verification. These do not automatically
certify arbitrary semantics; independent visual review remains required.

17new automated tests use4 valid and5invalid duration cases,6synthetic preflight
fault cases, extra-field refusal and certainty/caution regression. Real inference,
OCR,TTS,FFmpeg and ASR runs are separate unmocked artifact tests. Source media
stays locally retained under watched/; JSON receipts are committed byte-exactly.

No main merge/publication; no arbitrary-video/all-action recovery, hidden-input
causality, complete30s transition recall, long-video scale or production claim.
No confidence dimension was promoted; captions remain unverified candidates.
