# Independent original-clip repair grade

**Disposition: FAIL the original all-major-events/no-false-claims criterion; partial visual-observation improvement.** Not a successful training-procedure extraction.

Reviewer `/root/inspection_review`, 2026-09-18. Frozen reference: `proofs/watch-real-video/BLIND-REFERENCE.md`, unchanged. Graded `dense-instruct-01/report.json`, SHA256 `2f49e8fbe17dd862bf8a20d84957f957b63ae043e98f92cf4748ebbbcd53b00e`. Read all 61 state records and directly inspected original input JPEGs at clip 0, 8.5, 11.5, 14.5 and 17 seconds in `watched/dense-repair-01/frames/`, supplementing the previously inspected dense reference. No inference rerun or reference edits.

## What improved and what the output actually is

The report contains 61 frame-bound single-image observations and 60 adjacent pixel-change candidates. It does not itself emit semantic recovered event assertions: before/after descriptions are attached to candidates for later review. The following score measures whether the recorded descriptions support the frozen events, not autonomous event recovery. All observations/candidates remain unverified and procedure promotions are zero.

Frame 10 is now correctly described as Blender, not a slide. View labels, slide onset, four-to-five slide sections, and the pointer change are materially better represented than in the failed sparse run. This used 61 calls, dense sampling and a different model variant; it is not an equal-budget comparison or isolated proof of any one fix.

## Frozen ten-event assessment

| Event | Assessment | Reason |
|---|---|---|
| V1 viewpoint changes | Supported | Side/perspective, front orthographic at 1.5-2, then perspective at 2.5 are recorded. |
| V2 zoom-out and right orthographic | Partial | Right orthographic recorded at 5-6; material screen-size reduction is not described. |
| V3 drawn annotation | Partial/contaminated | Blue line recorded at 8.5-9.5, but called an active sculpting stroke or selection line; no trustworthy annotation interpretation. |
| V4 further zoom-out | Missed | Adjacent descriptions do not identify the scale reduction. |
| V5 annotation erasure | Missed/contradicted | Eraser cursor at 11.5 is described as a sculpting brush. Removal sequence is not recovered. |
| V6 return to perspective | Supported | Right orthographic at 12.5 becomes User Perspective at 13. |
| V7 arms unhidden | Partial | `Show Hidden Objects` read at 14.5 and arms/highlights later described, but no clear missing-to-visible arms comparison; invented selection boxes contaminate the description. |
| V8 pencil to arrow | Supported | Pencil at 15.5 versus arrow at 16 is recorded. |
| V9 switcher then slide | Partial | Full slide appears correctly at 17.5, but 17-second switcher thumbnails are misclassified as floating reference windows. |
| V10 fifth point appears | Supported | Four-section description at 19, fifth heading at 19.5 and five sections by 20.5. Fade mechanism is not explicitly described. |

Thus **4/10 supported event representations, 4/10 partial, 2/10 missed**. The supported subset does not imply all statements in those frame records are correct. The system has not itself adjudicated any of these candidates into verified events.

## False-claim lower bound

At least **15 distinct frame-state records** contain directly contradicted claims, using this deliberately conservative, non-exhaustive inventory:

- Ten frames at clip 0, 1.5, 3.5, 5, 5.5, 6.5, 7, 8, 13 and 13.5 explicitly say `Sculpting mode active`; the mode is Object Mode and Sculpting is the workspace tab. This error persists despite an explicit prompt warning.
- 8.5: calls the blue annotation an active sculpting stroke path.
- 9.5: calls the visible solid-shaded mesh wireframe.
- 11.5: calls the eraser cursor a sculpting brush.
- 12: claims the figure is selected and in wireframe.
- 17: calls the operating-system task-switcher thumbnails floating reference windows with tabs/close buttons.

These are **15/61 records with identified false statements**, not a comprehensive count of all incorrect atomic assertions. Recurrent invented selection boxes/handles, cursor identities and some colors would require additional atom-level grading. Assertions of 'no uncertainty' are not evidence that the view was correctly understood. This is model-output error, not observed false promotion by Watch's evidence authority.

## Retained failure and version boundaries

- All 61 vision outputs are structurally present; this is not semantic success.
- **17 of 61 OCR receipts have null TSV**, so those are missing OCR evidence, not successful extraction. The builder identifies Windows text-decoding failure; this review independently confirmed the null count, not the full decoder root cause.
- This process loaded pre-hardening code `e62133b`. Its protocol names observer hash `608a4b0fa9fc0d4e95b987cd654a9ab667c2a7a3c847e6b7eae3f1ec8b5e2b43`. Later fixes must not be retroactively attributed to these artifacts.
- Old result `source_ms` values are clip-relative. Interpret them using the source offset 1800 seconds; they are not original-video timestamps as named.
- No causal replay, verified user input or instructional reproducibility was demonstrated.

## Guard re-review at 6dcaa17

Source inspection confirms read-once vision bytes, exact 2fps timestamp enforcement, inspection receipt-chain checks, source-offset fields, request-option logging/model-digest consistency checks, UTF-8 OCR via stdin with failure accounting, and blank/wholly-unknown observation rejection. Independently reran `watch/tests/test_frame_observer.py`: **12 passed**.

Remaining boundaries: `source.json` is not independently pinned to the original media/offset; pixel comparison hashes then reopens files instead of decoding the already-hashed bytes; transition before/after milliseconds remain clip-relative with generic names. This does not establish hostile concurrent-mutation resistance or cryptographically verified original-source lineage. The code still correctly declines semantic autoacceptance. These guard improvements do not cure the demonstrated model misconceptions.
