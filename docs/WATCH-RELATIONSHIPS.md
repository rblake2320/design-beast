# Input, control and result experiment

This experimental worktree is stacked on PR42 at
`4a7207b8ef758d7a4f14e0339cfb09239ec05283`. It does not change the preceding PRs,
doctrine, narration, accepted causal chains, or Watch publication authority.

## Reproduce

Install the existing development/perception requirements plus Python Playwright
and Chrome. Put FFmpeg/ffprobe and Tesseract on PATH, or supply the OCR path.

```powershell
python scripts/doctor.py
python scripts/beast_core.py validate
python scripts/record_watch_relationships.py --output watched/NEW-CAPTURE
python scripts/prepare_watch_relationships.py --root watched/NEW-CAPTURE
# Independent reviewers label native frames BEFORE any observer run.
# Do not reuse old labels for a new browser recording.
python scripts/evaluate_watch_relationships.py --root watched/NEW-CAPTURE --labels-a LABELS-A.json --labels-b LABELS-B.json --output watched/NEW-RUN
python scripts/score_watch_relationships.py --run watched/NEW-RUN --labels-a LABELS-A.json --labels-b LABELS-B.json --output watched/NEW-RUN/SCORE.json
```

All output destinations are exclusive. An interrupted output is retained and must
not be resumed by blindly repeating the command. Sources are isolated browser
recordings of a local instrumented app, not downloaded third-party tutorials.
`prepare` retains native JPEG frames and ffprobe PTS for visual labeling; those
frames and label contents are not inputs to the observer. It reads video through
explicit Watch inspection requests. Telemetry is withheld until visual freeze.

## Evidence vocabulary and limitations of this experiment

The observer records indicator hits, candidate events, pressed-region bounds,
control text (including the prior unoccluded supporting frame), result text,
and temporal candidates as different fields. Conflicting control readings in one
held spatial event preserve uncertainty rather than manufacturing two inputs.
Pointer-covered words cannot become cached control identities. Cached labels
must precede their use, even when execution inspects time out of order.

All causal-sufficiency labels in this ten-case corpus are unknown. Therefore its
causal score measures required abstention only. An Inspect press followed by a
timer-driven Saved result is order-compatible, but never accepted as causing
Saved. No procedure or executable instruction is produced.

Final observer uses a border-free crop mosaic plus source-global view for one
OCR call per inspected frame. Crops are derived from the checked snapshot, their
word coordinates map back to source coordinates, and transformation code is
hashed. This is an original Python combination of existing OpenCV/Tesseract
techniques, not a new OCR model or a general-purpose UI detector. The yellow
pressed-state and magenta-pointer segmentation are fixture-specific.

Tesseract's [official quality guidance](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
documents segmentation-mode and border/cropping considerations. A direct probe
showed PSM6 could read the missed status, while bordered button text remained
bad. Border-free panels and an earlier unobscured control observation repaired
the measured failure; changing language confidence would not have done so.

## Budgets and execution lineage

Each arm is capped at16 requested output frames,16 OCR calls,0 model tokens and
120seconds. Internal codec-frame decode work is unmeasured, not claimed equal.
Native source recording is25FPS. Requested timestamps are scored with the
predeclared40ms native-frame tolerance. Both arms omit the last80ms to avoid
seeking beyond the last decodable presentation; exact intervals are retained in
the repaired reports. No full-spatial/temporal coverage claim follows from16frames.

The initial protocol uses16 uniform baseline requests and5 coarse conditional
requests plus11 pixel-change-focused requests. Later, explicitly known-case
repairs use5 coarse +2 early control-context +9 result-bracket requests when debt
remains. These are NOT retroactively called the frozen algorithm or a fresh
blind experiment. A stop applies to temporal-candidate completeness only, never
causal sufficiency. If no result bracket exists, bounded pixel-change fallback
remains. This experimental runner is not activated in production Watch.

Repair runs retaining `--baseline-from` reuse already-executed baseline artifacts
with per-arm reuse receipts. They do not rerun or attribute the baseline to the
new code, and do not support a fresh paired timing or superiority claim.

The final known-case tie leaves the single-native-frame input missed by both
methods. Under this result, a requirement for two extra events cannot pass when
baseline missed only one. Keep the graduation FAIL; do not lower the threshold
or choose a winning subset. Further superiority testing needs a new frozen set.
