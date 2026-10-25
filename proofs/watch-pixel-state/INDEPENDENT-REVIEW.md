# Independent pixel-state review

Reviewer `/root/inspection_review`, 2026-09-18. Scope: `watch/visual_state.py`, `scripts/watch_perception.py`, focused tests and retained `blender-01` / `heldout-01` measurements. No model calls, source edits or changes to prior references/grades.

## Initial disposition

**The new spatial/temporal records add concrete inspectable evidence beyond generated descriptions. They do not close the failed semantic challenge.** Two robustness issues require repair or an explicit narrower operating boundary: the runtime deadline is checked only before each frame, and the decoded-image size limit is applied after decoder allocation.

Independent execution: `python -m pytest watch/tests/test_visual_state.py -q` yielded **6 passed**. These include controlled feature translation, scaling, reset, text matching and rejection tests; they are not real-video semantic validation.

Independently checked **all 122 state-file hashes** against the two reports; all matched. The initial runs report approximately **3.266 seconds** and **3.344 seconds** for 61 frames each. Both reused previously computed OCR receipts. These times therefore measure pixel/state processing and receipt writing, **not full OCR-plus-perception latency** and not 61-frame model inference.

## Evidence gained, checked against visible frames

Directly viewed the diagnostic images for Blender clip 8.5, 11.5, 14.5 seconds and held-out clip 16.5 seconds, and inspected selected state records against the frozen visual references.

- At Blender 8.5 seconds, changed-region rectangles localize the annotation/cursor area; at 11.5 they localize the eraser/body area. At 14.5 they cover both reappeared arms and the operator-label region. These are coordinate-bearing pixel differences, **not diagnoses of drawing, erasing or unhiding**. The prior generated descriptions could misname these same objects; the new measurements retain where the pixels actually changed without that vocabulary error.
- Frame hashes, adjacent-frame hashes, feature correspondences, forward/backward error and track age permit more direct auditing than prose alone. Track IDs refer to image features, **not identified UI objects**.
- OCR observations now carry spatial boxes, raw scores and exact-text/overlap-linked IDs. In the slide sequence, the fifth heading first appears in this extracted text state at clip 20.0 seconds; the reference sees a faint appearance earlier. Do not claim exact onset recovery.
- Held-out clip 17.0 contains a spatially localized research heading; it disappears from the text state at 17.5. This is useful evidence of OCR-observed text change, not proof that every text disappearance is a real scene edit.
- Large scene changes to the slide at 17.5 and the held-out graphic/presenter boundaries reset feature correspondence. Other difficult changes can yield no reliable tracks without exceeding the global reset threshold; the absence of tracks is explicitly recorded as uncertainty.

All three confidence dimensions remain null, and evidence class is `pixel_measurement_not_semantic_verdict`. No semantic acceptances or procedure promotions are recorded.

## Important limitations observed in the actual runs

1. **Whole-frame affine scale is dominated by the static interface.** It remains approximately 1.0 through known Blender viewport zoom changes. The many stable menu/panel features explain this behavior. This is not zoom detection and must not become an inferred object/view scaling instruction. Region-conditioned motion estimation would be a separately evaluated extension.
2. **Exact OCR text tracking fragments.** Strings and boxes change with OCR segmentation/noise, causing appeared/disappeared IDs even when the UI is stable. The recorded `Object` token inspected at clip 0 is a menu item, not reliable recovery of the mode dropdown. No verified Object Mode versus Sculpting distinction is established.
3. **OCR errors remain evidence uncertainty.** Example: the held-out document icon is read as `&` beside the correctly read research heading. Raw OCR scores are not calibrated probabilities; score filtering does not prove text truth.
4. **Sparse samples remain sparse.** Two frames per second, point trajectories and connected components cannot prove an unseen click, shortcut, causal action or reproducible procedure.
5. Diagnostics add rectangles/lines to derivative images. They are useful for review but must never be mistaken for source overlays or fed back as original perception input. The script explicitly keeps them separate.

## Concrete robustness findings at initial review

- `watch_perception.run` checks elapsed time only at loop entry. Final-frame OCR, tracking or encoding can exceed `max_seconds` and still produce a success report; fresh OCR has a separate 30-second timeout rather than the remaining run deadline. Check the deadline after work/before successful completion and bound blocking work with the remaining budget if claiming a hard deadline.
- `decode_verified` calls `cv2.imdecode` before enforcing the 16-million-pixel cap. A large compressed image can force large allocation before rejection. Bound encoded input and inspect dimensions before full decode; retain an after-decode consistency check.
- Original source/offset lineage is not newly established: this script hashes the supplied timeline and verifies each frame against it, rather than independently proving that the timeline belongs to an immutable original video. This matches the existing documented limitation, not a new semantic authority.

No source was modified by the reviewer. This review does not authorize a merge or replace the earlier failed/partial semantic grades.
