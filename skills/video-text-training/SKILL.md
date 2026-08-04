# Video Text Training (OCR Extractor)

**Purpose:** Plugs `watch/evidence/extractors/ocr.py` into a video source,
producing deduped, timestamped on-screen text as EvidenceEvents. This is
now a THIN skill — the schema, dedup, and alignment logic live in
`watch/evidence/`, not duplicated here (correction from the original draft
which had a separate implementation).

## Backends
- `nemo_retriever_local` — NVIDIA NeMo Retriever OCR NIM, runs on DGX Spark,
  no network dependency
- `google_video_intelligence` — Cloud TEXT_DETECTION, fallback/comparison

## What changed from the original draft
- Removed the standalone `scene_sampler.py`, `dedupe_and_align.py`,
  `training_record_builder.py` — these are now `watch/evidence/extractors/
  scene_change.py`, `enrichers/dedupe.py`, `enrichers/timestamp_align.py`,
  used by every extractor, not just OCR.
- `ocr_extract.py` is now `watch/evidence/extractors/ocr.py`, emitting the
  canonical EvidenceEvent shape.
