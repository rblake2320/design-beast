# Watch pixel-state implementation proof

Implementation head: `94ef441`. Follow-up to draft PR #35; original semantic
failures are not overwritten. Two retained 30-second clips, 61 frames each.

## Executed, not just proposed

| Channel | Actual retained execution |
|---|---|
| CPU pixels + persistent state | Forward/backward Lucas-Kanade tracking, gridded replenishment, changed components, regional affine estimates, spatial OCR IDs across 122 frames |
| Fresh OCR | `fresh-ocr-blender-01`: 61 actual Tesseract calls plus tracking via `beast watch-perceive`, 29.688s |
| OmniParser | Pinned Microsoft icon detector ran CPU inference on both sets: 61+61 frames, 18.313s and 15.625s |
| V-JEPA 2 | Pinned Meta pretrained model encoded seven overlapping 16-frame windows per clip; 14 normalized 1,024-D vectors retained |
| Combined Watch state | `fused-blender-03` / `fused-heldout-03`: 122 final records through `beast watch-fuse`, matched frame hashes/times across three channels, bounded inspection recommendations |

The first encoder report includes model download/load and took 84.468s; the
cached-model second report took 2.969s, excluding Python/import startup. Peak
PyTorch allocated GPU memory was 686.897 MiB per run; this is not total device
memory or a throughput benchmark. Admission protected existing workloads; no
user process was killed. Provider charges: $0; electricity/hardware costs unknown.

The CPU `blender-01` / `heldout-01` runs (3.266s / 3.344s) reused existing OCR.
Regional-tracking `blender-02` / `heldout-02` took 6.484s / 8.485s, also with OCR
reuse. Those numbers are not total fresh-observation latency. Later artifacts
remain separate from earlier runs rather than silently replacing them.

## Observed improvement

Independent review found changed regions at the annotation, eraser-area change,
arms reappearance and text-label patch without using model-generated descriptions.
Regional flow measured approximately 0.977 image scale at clip9.5s in three
tiles, where the earlier global affine result was dominated by static UI.
Spatial OCR retained the fifth slide heading at20s and the held-out research
heading at17s with its disappearance from OCR at17.5s.

These are additional measurable inputs. They do not establish a zoom command,
annotation-erasing instruction, correct tool identity, or causal/reproducible
procedure. OCR disappearance may mean an OCR miss. Detector boxes are unverified
candidate UI regions; embeddings are uncalibrated temporal features. The prior
4/10 Blender semantic grade has **not** been replaced with a new semantic pass.

## Boundaries and permanent controls

- Pixel bytes are hashed before decoding; dimensions are checked from the header
  before OpenCV allocation. Frame paths must remain inside their Watch bundle.
- Feature identities require forward/backward agreement; abrupt cuts and long
  gaps reset correspondences. State confidence dimensions remain independent and
  unset; fitting residuals and raw detector/OCR scores are not probabilities.
- Pixel runner rejects budget exhaustion, including after the final computation.
  OCR receives the remaining timeout. Detector/encoder are fixed-count experimental
  runners without whole-run wall-clock deadlines, not arbitrary-input services.
- Fusion verifies actual state hash, report row frame/hash/time, detector frame,
  window member frames, finite normalized vectors, recomputed cosine distances,
  finite in-bounds detector boxes, and bounded scores. Changed receipts/foreign
  frames and forged distances have explicit regression tests.
- Recommendations use the existing `InspectionDecision` contract. UI detections
  without text request OCR; temporal distance >0.1 may request slow review.
  Thresholds are uncalibrated scheduling heuristics. No action executes from
  these recommendations; no semantic or procedure evidence is auto-promoted.
- Core tests install CPU perception dependencies through requirements-dev,
  so CI does not silently skip this lane merely because OpenCV was absent.

## Verification

Full local default suite: **334 passed, 1 skipped, 7 live-GPU tests deselected**
(`tests-final.xml`). The skip is the declared Windows symlink-privilege limitation.
Fourteen new focused CPU cases plus later closure tests cover actual algorithms
and hostile inputs, not mocked model responses. Actual model/CPU runs above are
separate from unit coverage. Core graph validates eight capabilities/one pack.
Doctor:33 OK, optional ComfyUI offline, zero failures after process-local FFmpeg
PATH correction. No system PATH change was made.

Read `INDEPENDENT-REVIEW.md` and `FINAL-REVIEW.md` for pre-fix findings and closure
addenda. The full known-input runs and all negative findings remain retained.
There is no generalization, calibrated accuracy, arbitrary-duration service,
10/1,000/500,000-video readiness, or complete training-video reconstruction claim.

## Dependencies, licensing, reproducibility

Setup/commands: `docs/WATCH-PIXEL-STATE.md`. Temporal Transformers/tokenizers are
in a separate ignored venv; existing global packages were not upgraded. Its
inherited-package conflicts are disclosed, not treated as a clean-build proof.
Model weights remain in external local caches, not committed.

OmniParser revision `6600256cb0f1b07651e3bc86166196307bad7e2d`; actual detector
weight hash/license retained in `weights.json` (AGPL-3.0). This is a detector-only
experiment, not the full Florence-captioning pipeline or a product license approval.
V-JEPA revision `b3c1679b7c34d3255ef3547f27c7b226aefab26f`; model card labels MIT,
upstream code MIT. Verify downstream model/package obligations before distribution.

Review-frame inputs remain committed in `proofs/watch-repair/inputs/`. Local
diagnostic JPEG derivatives are excluded from Git to avoid duplicating original
video frames; measurement records, hashes and generation code are retained.

Failure mechanism addressed: isolated screenshot descriptions discarded temporal
and spatial evidence, while global motion fit could be dominated by application
chrome. The new executable lane preserves those measurements. Remaining semantic
misinterpretation requires a separately evaluated event interpreter/verification
stage. It is not resolved merely by adding these components.
