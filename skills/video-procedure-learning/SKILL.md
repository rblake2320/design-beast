# Video Procedure Learning

**Purpose:** Turns an authorized screen-recording/tutorial video into an
auditable, evidence-backed procedure — the actual product, not just text
extraction. Consumes `watch/evidence/` extractors (scene_change, ocr,
ui_state) and compiles output through `exporters/skill_bundle.py`.

## Pipeline
```
source_manifest (media-provenance) 
  → scene_change.py (adaptive frame selection, reuses existing sampler)
  → ocr.py (on-screen text per selected frame)
  → ui_state.py (classifies action across a frame WINDOW, not single frame)
  → dedupe.py + timestamp_align.py
  → ProcedureClaim compilation (one step per detected action)
  → evidence_gate.py (blocks unapproved inferred/uncertain claims)
  → skill_bundle.py (Beast's existing skill-validation contract format)
  → human review UI (approve/edit/reject + replay result)
```

## Review states enforced end-to-end
observed → inferred → uncertain → verified_by_execution → rejected
A step is never presented as verified unless Beast actually replayed it.

## Reuses (does not duplicate)
- Beast's existing adaptive/dense sampler and CUDA-indexed frame index
- Beast's existing exact-replay manifest format for skill_bundle output
- watch/evidence canonical schema for every emitted event
