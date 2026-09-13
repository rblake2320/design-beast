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
beast library people [--label ID|NAME "Name"] [--find NAME] [--confirm FACE NAME] [--reject FACE NAME]
                     [--merge KEEP DROP] [--recluster] [--show NAME]
beast library events                          # time + GPS trips, offline place names
beast library albums [--model qwen3.8:27b]   # group + name; rerun any time, plan picks it up
beast library plan --dest D:\Organized [--no-people]    # emits move: proposals for files placed earlier
beast library watch D:\Photos --dest D:\Organized [--interval 300] [--once]   # unattended
beast library recover [--all] · backup --dir DIR · restore BACKUP · rebuild --dest D:\Organized
beast library --remote --dsn $DSN review --tier fast     # worker on another node: never sees private assets
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

## People — the way a phone does it

Every face is embedded once at ingest (InsightFace buffalo_l, 512-d); matching is dot products
against a few **exemplars** per person, so it is instant and does not drift like a centroid.
Two bands: cosine ≥ 0.55 is assigned automatically, 0.42–0.55 is only a **suggestion** until
you say yes/no; faces that are tiny, blurry or turned away never seed a new person. Naming is a
query: `beast library people --label 24 "Grandma"` (or the People tab) immediately searches the
whole library for her and every later scan matches new faces against named people first.
Corrections stick: `--reject FACE Grandma` is remembered; `--confirm FACE Grandma` becomes an
exemplar; `--merge Grandma 31` folds a stray cluster in; `--recluster` rebuilds the anonymous
people while named ones stay fixed. Search by name: `search "birthday cake" --person Grandma`.

## Unattended operation and recovery (the enterprise part)

`beast library watch D:\Photos --dest D:\Organized` polls, processes only what is new, auto-
applies into albums you have already approved once, and leaves anything that needs a new
album waiting in the Review tab. Every 24 cycles it self-checks and takes a rolling backup
(`<dest>/.beast/backups`, last 7 kept). A failing cycle is logged and backed off, never fatal.

| Failure | What happens | Proven by |
|---|---|---|
| worker/process dies mid-stage | its `running` claims are handed back at the next stage start (`reclaim_stale`) | `test_worker_death_mid_stage_is_reclaimed_automatically` |
| model server down (vLLM/Ollama) | after 5 consecutive connection failures the stage returns its work to `pending` and stops cleanly — nothing is marked `error` | `test_model_server_outage_returns_work_to_pending_not_error` |
| crash mid-copy | copies go to `name.beast-partial` and are renamed into place; `recover` deletes leftovers and the next `apply` redoes them | `test_crash_mid_copy_leaves_no_half_file_and_is_redone` |
| organized file edited by a person | reported as `changed`, never overwritten | `test_changed_organized_file_is_reported_never_overwritten` |
| organized file deleted | `recover` re-approves it; `apply` restores it from the untouched source | same test as mid-copy |
| store corrupted / lost | `backup` (SQLite online backup) → `restore` (integrity-gated); or `rebuild --dest` from `<dest>/.beast/manifest.json`, which lists every placed file with its source and SHA-256 | `test_backup_restore_round_trip_and_integrity_gate`, `test_lost_store_rebuilt_from_manifest_without_recopying` |
| a better decision later (new album name, named person) | `plan` emits `move:` proposals inside the organized tree; `apply` moves atomically, hash-verified, and tidies empty folders | `test_reconcile_moves_files_when_album_changes` |
| private material on a shared queue | folders named private/IDs/passport/medical/tax/bank/insurance and anything the VLM flags `sensitive` are `private`: a `--remote` worker is never handed them or their thumbnails | `test_private_assets_never_reach_a_remote_worker` |

`beast doctor` carries outcome checks for the store: stuck claims (> 1 h) FAIL, error rows WARN,
backup older than 48 h FAIL, batched review server down for > 24 h FAIL (age is tracked in
`session/doctor-state.json`, so a long outage cannot pass as a blip). SQLite runs WAL +
`synchronous=FULL`, so a committed ledger row survives power loss.

Readiness, honestly: every failure class above is reproduced by a test on this machine. What is
NOT yet done is the soak — `watch` running unattended for 24 h with the model server and the
machine deliberately interrupted mid-run — and a multi-node run. Until then the verdict is
**Pilot** (one operator, one box), not Department/Enterprise.

## Video

`.mp4 .mov .m4v .mkv .avi .webm .3gp .mts` are inventoried through one representative frame
(10 % in, via ffmpeg) — same hashes, thumbnail, embedding, review and album path as a photo;
`duration` and `creation_time` come from ffprobe. Live Photos' `.mov` halves therefore land
next to their `.heic`. Not yet: scene-level indexing inside long videos.

## Studio Library tab

`python studio/server.py` → `http://localhost:8787/library`: natural-language search with a
person filter, People (real face crops, type a name + Enter, yes/no on suggestions, "same
person?" merge prompts), Review (approve/reject per album, apply, recover/verify), Status.
API under `/api/library/*` for other agents.

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
