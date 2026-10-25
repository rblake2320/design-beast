# Watch spatial and temporal perception lane

Experimental local measurement lane, extending retained Watch bundles. No
transcripts, model-authored procedure claims or automatic action execution.

## Implemented components

- `watch/visual_state.py`: verified pixel decoding, connected changed regions,
  spatial OCR lines with persistent identities, forward/backward checked
  Lucas-Kanade feature tracks, global and regional RANSAC scale estimates,
  scene/gap resets and explicit uncertainty. Independent confidence dimensions
  remain null rather than being invented from tracking fit scores.
- `watch_ui_regions.py`: pinned Microsoft OmniParser-v2 icon detector on CPU.
  This uses the detector only, not its Florence captioning model. A box is not
  a known button function or an inferred cursor identity.
- `watch_temporal_encoder.py`: pinned Meta V-JEPA 2 model, genuine 16-frame
  clip inference, pooled 1,024-dimensional embeddings and consecutive-window
  cosine distances. These are uncalibrated features, not GUI event labels.
- `fuse_watch_state.py`: verifies frame identity across channels and retains
  explicit window coverage, feature references and bounded inspection
  recommendations. `PixelInspectionPolicy` implements the existing Watch
  recommendation contract; no recommendation executes an action or promotes
  observations into procedures.

The fusion scheduler uses detector presence without readable text to recommend
OCR, and temporal-window distance above 0.1 to recommend slower review after
tracking is established. This is an uncalibrated scheduling heuristic, not an
evidence-confidence or event-acceptance threshold.

## Setup

CPU pixel lane: `python -m pip install -r requirements-watch-perception.txt`.
OmniParser experiment additionally needs `requirements-watch-ui.txt`.

Use a separate Python environment for temporal inference. The verified host
already had PyTorch 2.10.0+cu128 and compatible torchvision, so this run used:

```powershell
python -m venv --system-site-packages .venv-watch-temporal
.venv-watch-temporal/Scripts/python.exe -m pip install transformers==4.57.1
```

This leaves the shared Transformers 4.51.3 unchanged. It inherits unrelated
host packages, so pip reported incompatible requirements for inherited
llm-guard/nemo-curator/docling packages; those are not used by this lane. This
environment is not a clean install proof. On another host, use an isolated venv,
install hardware-compatible torch/torchvision, then
`requirements-watch-temporal.txt`. No global package upgrade is required.

## Run the real CLI

```powershell
./bin/beast.ps1 watch-perceive --bundle watched/dense-repair-01 --output NEW_PIXEL_DIR
./bin/beast.ps1 watch-ui-regions --bundle watched/dense-repair-01 --output NEW_UI_DIR
./bin/beast.ps1 watch-temporal --bundle watched/dense-repair-01 --output NEW_TEMPORAL_DIR
./bin/beast.ps1 watch-fuse --pixels NEW_PIXEL_DIR --ui NEW_UI_DIR --temporal NEW_TEMPORAL_DIR --output NEW_FUSED_DIR
```

Every output directory must be new. A failure keeps its intent and partial
artifacts, publishes no successful final report, and is not auto-resumed.
`watch-perceive --ocr-root DIR` reuses hash-linked OCR receipts; its time excludes
prior OCR computation. Without that argument it runs Tesseract on verified
bytes. Current detector/encoder experiments require the frozen 61-frame case;
this is not arbitrary-duration video support. The pixel lane allows 2..96 frames.
The detector and encoder have fixed input/count caps, but no whole-run wall-clock
deadline; only the pixel runner has elapsed-budget failure accounting. They are
frozen-input experiments, not hardened arbitrary-input services.

The encoder checks the existing `judge` resource profile before loading and
again before moving the model onto the GPU. It caps its process allocator at
6,144 MiB. This is a point-in-time admission, not an exclusive GPU reservation.
CPU tracking caps OpenCV at two threads; detector/encoder use four torch threads.
No user workload is stopped.

## Data and licensing boundaries

Model revisions are explicit constants in the two scripts. Downloads stay in
local Hugging Face caches; neither model weights nor third-party implementation
code is vendored into this repository. The chosen OmniParser detector's actual
retained upstream license is **AGPL-3.0**, not the license of a newer detector
mentioned in its README. Review licensing before shipping it as part of a
distributed/service product. This experiment does not approve product licensing.
The V-JEPA HF card labels its model MIT and upstream repository code has an MIT
license; model/package licensing still requires review before product distribution.
No universal downstream licensing compatibility is asserted here.

Diagnostic overlay JPEGs are derivatives for human review only, never fed back
as original pixels. They remain local and are reproducible from committed source
frames, measurement records and code. State/intent/report evidence is committed.

## What the live tests do and do not establish

Two existing 30-second clips were measured; this is follow-up on known inputs,
not a fresh blind test. Frames are sampled at 2fps, so intermediate events can
still be missed. Grid-tracking measurements locate changed regions; they cannot
tell whether an input was a click, shortcut or an automatic application update.
OCR fragment changes are not proven text appearance/disappearance. Flow may
lose tracks under occlusion, large changes or textureless regions. Regional
scale is apparent image motion, not proof of object scaling or a zoom command.

The V-JEPA windows span 7.5 seconds at this sampling rate and overlap. Their
distances cannot localize an exact event timestamp or establish causality.
Pooling can lose fine UI detail. The model was not fine-tuned on this interface.
OmniParser false positives and missed elements remain possible.

See `proofs/watch-pixel-state/PROOF.md` and independent review. None of these
measurements revises the earlier failed semantic challenge into a pass.

## Primary implementation references

- https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html
- https://docs.opencv.org/4.x/d9/d0c/group__calib3d.html
- https://github.com/microsoft/OmniParser
- https://huggingface.co/microsoft/OmniParser-v2.0
- https://github.com/facebookresearch/vjepa2
- https://huggingface.co/docs/transformers/en/model_doc/vjepa2
