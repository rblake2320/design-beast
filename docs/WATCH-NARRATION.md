# Automatic visual explanations and narration

Extends PR37's editorial draft workflow; it does not replace Watch or lift its
evidence gates. Narration uses existing local Kokoro assets with a fixed synthetic
voice, never the original speaker's cloned voice.

```powershell
python -m pip install -r requirements-watch-narration.txt
# First prepare an existing source-linked review as documented in WATCH-TRAINING.md.
.\bin\beast.ps1 watch-training auto --review watched\lesson-01\review --output watched\auto-lesson-01 --count 3
# Review teachability/units.json, then export only eligible units:
.\bin\beast.ps1 watch-instruction-gate --review watched\lesson-01\review --units reviewed-units.json --output watched\eligible-01
# Existing edited plans can also be voiced without another visual-model call:
.\bin\beast.ps1 watch-narrate --rendered watched\lesson-render-01 --output watched\voiced-lesson-01 --model-dir D:\ai\tools\kokoro
```

The automatic path selects up to3 separated high-change candidates from actual
pixel measurements, inspects each before/after frame separately through existing
Watch observation and drafts explanations into a teachability review queue.
It no longer renders or narrates unreviewed model proposals. It needs qwen3-vl:8b-instruct
Ollama model and passes the judge resource profile before observations. Speech
and optional Whisper verification use CPU only. No cloud spend was used.

Outputs retain selected-frame IDs, prompts, observations, model responses,
independent confidence fields, source hashes, source/output timing, voice-model
hashes and generated WAVs when the separate narration command is used. The
original footage plays at its original rate. Narration refuses any segment
needing over 2 seconds of additional hold or falling below 75% unextended source
duration. Refusal retains `review-required.json`, measured durations and the WAV;
it does not complete a video. Passing segments may briefly hold the actual last
frame, explicitly labeled below the picture. No source controls are covered.
Unextended source duration is NOT measured moving-footage percentage: the source
may itself contain stillness. `measured_motion_fraction` remains null.

See [WATCH-TEACHABILITY.md](WATCH-TEACHABILITY.md) for triage and evidence limits.

All explanations remain unverified visual observations. The model's claimed
certainty cannot remove the fixed spoken causal-uncertainty statement or the
review/publication gate. Independent visual review remains required before
treating a caption as instructional truth. This is automated draft authoring,
not a claim that every video/action is comprehended correctly.

## Research used, accessed2026-09-19

- [Kokoro ONNX upstream](https://github.com/thewh1teagle/kokoro-onnx): local ONNX
  speech setup, voice assets and examples. Installed0.5.0 source was inspected
  for provider selection; CPUExecutionProvider is explicitly enforced.
- [Kokoro reference implementation](https://github.com/hexgrad/kokoro/blob/main/kokoro/pipeline.py): speech pipeline reference; reused the already-installed ONNX variant.
- [Hugging Face Qwen3-VL guidance](https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/qwen3_vl.md)
  and [technical report](https://arxiv.org/abs/2511.21631): temporal grounding and
  timestamp alignment informed explicit source-time binding. These sources do
  not certify this local model's behavior. Our two-image trial failed; separate
  frame observations followed by comparison repaired the named coarse transition.
- [Tesseract image-quality guidance](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html):
  used targeted rescaling, inversion and sparse-text segmentation to recover
  small upper-left UI view labels missed by whole-frame OCR. Crop coordinates,
  transformed-byte hashes and OCR text are retained; source footage is unchanged.

## Verification and failures

`verify_watch_narration.py` decodes output audio, transcribes it independently
using CPU Whisper, compares words, and checks original/held picture regions.
It is frozen to1280x720 fixtures. Passing ASR does not prove semantic truth or
universal pronunciation. The real proof retains the original wrong automatic
caption separately; it was not voiced as an accepted result.
The three-segment trial initially produced two false/missed explanations despite
preserving all source pixels and speaking its text correctly. Targeted ROI OCR
recovered the two named viewport-label transitions; independent review accepted
all three coarse repaired descriptions. This is repair of already-known cases,
not a blind accuracy benchmark. Use `--reuse-observations EXISTING_EXPLANATIONS`
to reuse matching hash-bound frame observations when repeating only comparison.

The full-video mission is not reduced to this3-candidate batch: long-form
coverage, reinspection scheduling across chapters, broader semantic recall and
false-acceptance tests remain explicit evaluation work. No main-branch merge or
publication is performed by this builder.
