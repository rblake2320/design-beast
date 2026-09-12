# Beast Library — organize a media collection you already have

`beast library` turns a folder of photos, screenshots and scans into a deduplicated,
searchable, people-aware, album-organized library — entirely local, with the source
tree treated as read-only and every file operation approval-gated and hash-verified.

Evidence level: **reproduced** (2026-09-12, 399 real photos on one RTX 5090 —
`proofs/library-001-pictures/PROOF.md`). Not yet measured at 10k+ images or across nodes.

## The pipeline

| Stage | Component | What it does | Runs on |
|---|---|---|---|
| 1 inventory | Pillow, hashlib, imagehash | SHA-256, EXIF (date/camera/GPS), dimensions, pHash/dHash, 1024px JPEG thumbnail **stored in the DB** | CPU |
| 2 dedup | union-find | exact (SHA-256) + near (pHash ≤ 6 bits, dHash guard) + embedding-confirmed (cosine ≥ 0.965 **and** pHash ≤ 18) clusters; representative = largest | CPU |
| 3 embed | SigLIP2 SO400M/14-384 | 1152-d image embeddings, batched, fp16 | GPU |
| 4 faces | InsightFace buffalo_l | detect ≥ 40px faces, 512-d embeddings, greedy centroid grouping (cosine ≥ 0.55) into unlabelled persons | GPU |
| 5 review fast | Ollama `qwen3-vl:8b` | every cluster **representative** → JSON (schema-forced, thinking off): caption, categories, objects, people_count, scene, quality, document, text_present, sensitive, suggested_album, confidence | GPU (any node) |
| 6 ocr | easyocr | only images the review called a document/screenshot/receipt (or `--all`) | GPU |
| 7 review deep | Ollama `qwen3.8:27b` | representatives with fast confidence < 0.7 or a sensitive flag (or `--all`) | GPU (any node) |
| 8 search | SigLIP2 text tower | text→image, image→image, filters: person, date range, album, OCR/caption keyword | GPU |
| 9a albums | SigLIP2 image + bge-m3 caption embeddings → scipy average-linkage (cosine 0.30) → `qwen3.8:27b` names each group ≥ 3 **once**, seeing the names already chosen | first real run gave 304 names for 382 images when asked per image; grouping first makes names consistent by construction. Small groups borrow the nearest named album (cosine ≥ 0.70) or keep their own review name | GPU |
| 9b plan | bge-m3 (Ollama) + rules | album = albums-table name, else consolidated `suggested_album` (synonyms merged at cosine ≥ 0.80, most frequent spelling wins), else `Unsorted`; every album split by `YYYY-MM`; `People/<name>` links for recurring people; duplicates recorded, never placed | CPU |
| 10 apply | copy (opt-in hardlink), SHA-256 verify, ledger | only **approved** proposals; existing different file → hash-suffixed name; source untouched | CPU |

Duplicates never reach a model: the representative's verdict covers its cluster, which is
where most of the compute saving comes from. Thumbnails live in the store so a review
worker on a DGX Spark needs only the DSN and its own Ollama — not your filesystem.

## Store

- Default: SQLite at `library/data/beast-library.db` (gitignored). Vectors are float32
  blobs; search is a brute-force cosine in numpy — fine to ~100k images.
- Shared: `--dsn postgresql://…` or `BEAST_LIBRARY_DSN`. pgvector `<=>` search, workers
  claim with `FOR UPDATE SKIP LOCKED`. Dev container on this box:
  `docker run -d --name beast-library-pg -p 127.0.0.1:5436:5432 -e POSTGRES_DB=beast_library -e POSTGRES_PASSWORD=… pgvector/pgvector:pg16`
  (DSN kept in `~/.beast_library.env`, never in the repo).

Tables: `assets`, `thumbs`, `embeddings`, `faces`, `persons`, `ocr`, `reviews`, `queue`,
`proposals`, `ledger`. Every stage is a queue row per asset (`pending → running → done |
skipped | error`); `beast library requeue STAGE` resets `running`/`error` after a crash.

## Commands

```powershell
beast library run D:\Photos --dest D:\Organized [--parallel 3] [--no-faces] [--no-deep]
beast library scan D:\Photos            # incremental: unchanged size+mtime are skipped
beast library dedup [--no-embeddings]
beast library embed | faces | ocr [--all]
beast library review --tier fast|deep [--parallel N] [--all] [--ollama http://spark-1:11434/api/generate]
beast library search "sunset over water" [-k 20] [--person 5] [--from 2024-06 --to 2024-08] [--text invoice] [--like ref.jpg]
beast library people [--label ID "Name"]
beast library albums [--model qwen3.8:27b]   # group + name; rerun any time, plan picks it up
beast library plan --dest D:\Organized [--no-people]
beast library proposals [--status pending] [--album "Beach trip"]
beast library approve --all | --album X | 12 13 14      (reject: same forms)
beast library apply [--hardlink]
beast library status
```

Multi-node: run `scan/dedup/embed/faces` on the machine that can see the files, then
`beast library --dsn $DSN review --tier fast --worker spark-1` on each Spark against its
local Ollama. Deep tier is the same command with `--tier deep`.

## Guarantees and their tests

| Guarantee | Where enforced | Test |
|---|---|---|
| source tree never written | inventory/organize only read `path`; apply writes only under `--dest` | `test_plan_approve_apply_never_touches_source_and_is_idempotent` (hashes every source file before/after) |
| nothing overwritten | `apply` hash-checks an existing dest; different content → `_<sha8>` suffix | same test (plants a foreign file at a destination) |
| nothing placed without approval | `apply` selects `status='approved'` only | same test |
| every copy verified | `sha256(dest) == asset.sha256` else the proposal errors and is ledgered | same test |
| duplicate = same picture, not similar picture | embedding edge requires loosely-related pHash (`EMBED_PHASH_GUARD`) | `test_dedup_folds_exact_and_resized_copies_into_representative`; live: two distinct images stay two clusters |
| exclusive work claims | SQLite `BEGIN IMMEDIATE` / PG `SKIP LOCKED` | `test_queue_claims_are_exclusive_and_requeueable`; PG exercised in PROOF.md |
| real models, real service | live tests hit SigLIP2, Ollama, easyocr, InsightFace and **skip visibly** when absent | `pytest -m live_gpu library/tests/test_library_live.py` |

Why copy, not hard link, by default: a hard link shares bytes, so editing the organized
file edits the original. The test suite found this (the "never touches source" test
failed under hard links); `--hardlink` remains as an explicit opt-in for read-only libraries.

## Known limits (honest)

- Album names come from a VLM: consistent, not canonical. Consolidation merges synonyms,
  it does not know your family's names for events. Label people with `people --label`.
- Confidence is self-reported by the model; the deep tier re-checks the low end, it does
  not calibrate it.
- Throughput on this box (`qwen3-vl:8b`, 3 parallel): ≈ 3 s per representative after
  warm-up. A 50k-image library is a multi-hour job on one GPU — that is what the shared
  queue and the Sparks are for. Not yet measured: see `next_test` in
  `beast/capabilities.json`.
- HEIC needs `pillow-heif`; RAW formats are not inventoried.
- SigLIP2's text tower is not used for name-to-name similarity (its text-text cosines are
  anisotropic — unrelated names scored > 0.85 in testing); bge-m3 via Ollama does that.
