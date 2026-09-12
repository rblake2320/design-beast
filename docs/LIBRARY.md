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
| 2 dedup | union-find | exact (SHA-256) + near (pHash ≤ 6 bits, dHash guard) + embedding-confirmed (cosine ≥ 0.965 **and** pHash ≤ 18) clusters; representative = largest. A near-identical pair that is a *distinct capture* (same dimensions, different bytes, EXIF 1–90 s apart) is a burst frame, not a duplicate | CPU |
| 2b stacks | Laplacian sharpness (OpenCV) | burst = same scene (pHash ≤ 20 or embedding ≥ 0.90) within 90 s; every frame is kept and placed under `<album>/<YYYY-MM>/stack-<best>/`, only the **sharpest** frame is reviewed and shown first | CPU |
| 2c events | time + GPS, `reverse_geocoder` (offline GeoNames) | new event when gap > 6 h or GPS moves > 25 km; consecutive same-place events ≤ 48 h apart merge into a trip; events with ≥ 3 photos and GPS are named `"Asheville, North Carolina - June 2025"`, photos without GPS in the same window ride along | CPU |
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

### Batched fast tier (vLLM) — the 10-20× knob

Ollama serves one image per request; vLLM batches them. On this box (Docker Desktop, WSL2):

```powershell
docker run -d --gpus all --name beast-vllm --ipc=host -p 127.0.0.1:8021:8000 `
  -v "D:\Models\huggingface\hub:/root/.cache/huggingface/hub" -e HF_HUB_OFFLINE=1 `
  -e VLLM_USE_V2_MODEL_RUNNER=0 -e VLLM_WSL2_ENABLE_PIN_MEMORY=1 `
  vllm/vllm-openai:latest --model Qwen/Qwen3-VL-8B-Instruct-FP8 --max-model-len 8192 `
  --limit-mm-per-prompt '{"image":1}' --gpu-memory-utilization 0.5 --max-num-seqs 16
```

Then `BEAST_LIBRARY_REVIEW_URL=http://127.0.0.1:8021/v1/chat/completions` (or `library_review_url`
in `beast.config.json`) and `beast library review --tier fast --parallel 16`. The two WSL2 env
vars are required: without them the engine dies with `RuntimeError: UVA is not available`
([vllm#43381](https://github.com/vllm-project/vllm/issues/43381),
[vllm#47387](https://github.com/vllm-project/vllm/issues/47387)). Measured numbers:
`bench/results/library-review-*.json` (`python bench/library_review_bench.py`).

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
- Throughput on this box, measured 2026-09-12 (`bench/results/library-review-20260912-*.json`,
  48–96 real thumbnails): every non-VLM stage is fast — SigLIP2 74 img/s, InsightFace 22 img/s,
  inventory 36 img/s/thread, easyocr 0.9 img/s (documents only). The VLM fast tier is the
  only slow stage: **Ollama `qwen3-vl:8b` caps at 0.96 img/s** regardless of concurrency
  (0.31 at 1, 0.93 at 4, 0.96 at 16); **vLLM `Qwen3-VL-8B-Instruct-FP8` reaches 7.6 img/s at
  16 in flight** (0.25 / 0.81 / 1.63 / 7.63 at 1/4/8/16; 7.59 at 32 with `--max-num-seqs 16`).
  Full fast tier on the 353-representative real library: 7 min (Ollama) → **46 s** (vLLM).
  50k images ≈ 14 h → < 2 h. Deep tier (27B, ~3% of images) and easyocr on document-heavy
  folders are the next ceilings. Multi-node not yet measured.
- FP8 `Qwen3-VL-8B` via vLLM under-sets the `document` flag versus Ollama's Q4 model (155 vs
  323 of 382 on the screenshot folder); OCR routing therefore also honours `text_present`
  and the `screenshot` category (366/382 routed).
- HEIC needs `pillow-heif`; RAW formats are not inventoried.
- SigLIP2's text tower is not used for name-to-name similarity (its text-text cosines are
  anisotropic — unrelated names scored > 0.85 in testing); bge-m3 via Ollama does that.
