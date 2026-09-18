# Watch repair research and falsifiable hypotheses

Sources inspected 2026-09-18. This is targeted primary-source research, not a claim
to have searched every publication or all world data. External benchmark claims
are not local proof. No PhoneClaw/SemIf/other upstream repository was modified.

## Hypotheses and probes

1. Multi-image output indices are not reliably bound to pixels. Prediction:
   identical individual source frames are recognized correctly when isolated.
   `binding-probe` supports this on the decisive10s and20s inputs through BOTH
   generate/chat routes. Thus changing API routes alone is not the fix.
2. Sparse inspection misses events independently of perception. The failed run
   supplied only8 distinct images; its25-frame reinspection discarded21 images
   before inference. Dense replay must account for every retained frame and expose
   failed/missing observations, not claim coverage merely from extraction.
3. Local reasoning/readout configuration contributes repetition and invalid
   envelopes. Installed default8B uses qwen3-vl-thinking renderer/parser. The
   thinking field contains the structured answer; schema grammar rejects nested
   constraints. Compare the explicit instruct model and finite single-frame
   responses. No unsupported assumption that a different model solves everything.
4. Before/after contact sheets alone may not solve grounding. `pair-probe` fails
   to identify the lower slide; retain that negative rather than promote it.
   `gemma-state-probe` also misdescribes the input. These are failed candidates.

## Primary sources and adopted / deferred ideas

- Qwen3-VL official implementation:
  https://github.com/QwenLM/Qwen3-VL — explicit temporal alignment, separate
  Instruct/Thinking variants, published non-greedy evaluation settings. Adopt
  code-bound frame identity and test the explicit instruct variant with its
  recommended sampling parameters; do not infer benchmark parity.
- https://ollama.com/library/qwen3-vl:8b and
  https://ollama.com/library/qwen3-vl:8b-instruct — installed default digest matches
  published default; a new separate instruct model is downloaded without replacing
  existing models. Preserve renderer/parser and model identities in receipts.
- https://docs.ollama.com/capabilities/vision and
  https://docs.ollama.com/capabilities/structured-outputs — base64 image transport,
  chat message binding, JSON/schema output followed by independent validation.
  Local compatibility still requires real calls; documentation is not runtime proof.
- Qwen technical report https://arxiv.org/abs/2511.21631 — temporal modeling does
  not remove the need to bind each supplied frame to time explicitly.
- https://arxiv.org/abs/2605.21954 — reports a perception/generation gap in temporal
  localization and attention-derived interval restriction. This motivates narrow
  observations, but attention-head extraction requires a different native runtime;
  not implemented or claimed here.
- VideoTree https://arxiv.org/abs/2405.19209 and VideoAgent
  https://arxiv.org/abs/2403.10517 — adaptive inspection and external evidence
  selection. Defer efficiency optimization until dense correctness baseline passes.
- https://github.com/microsoft/OmniParser and
  https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
  — structured GUI elements/OCR are complementary to general VLM reasoning.
  Use already-installed CPU Tesseract as a separate evidence channel initially;
  no claim of OmniParser-grade element grounding without its implementation/tests.
- https://github.com/PaddlePaddle/PaddleOCR — alternative OCR upgrade candidate;
  do not add a large dependency before measuring the current OCR failure set.
- https://ai.google.dev/gemma/docs/capabilities/vision/video and
  https://ai.google.dev/gemma/docs/core/model_card_4 — alternative video-capable
  architecture. Installed Gemma4 single-frame probe failed; capability documentation
  does not override that local negative result.

## Complete-fix acceptance boundary

Preserve the old FAIL. Pin the repaired observer before grading the held-out
rn8jhDQo6GI300–330s window, with a blind independent reference. Require correctly
grounded observed transitions, no unsupported causal promotion, bounded failure
handling, and retained exact inputs/results. A passed local replay alone is a
same-case repair, not generalization. If semantic errors persist, do not report
complete fix just because every frame has a response.
