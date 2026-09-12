# PROOF — library-001: organize a real 399-image folder end to end

Evidence level claimed: **reproduced** (one machine, one real collection, every stage real).
Not claimed: measured at scale, multi-node, precision/recall against a hand-labelled set.

| | |
|---|---|
| Date | 2026-09-12 |
| Machine | Windows 11, RTX 5090 32 GB, Python 3.12, torch 2.10+cu128 |
| Source (read-only) | `C:\Users\techai\Pictures` — 399 files (mostly `Screenshots\`, plus photos) |
| Destination | `C:\Users\techai\Pictures-Organized` |
| Store | SQLite `library/data/beast-library.db` (gitignored) |
| Models | SigLIP2 `google/siglip2-so400m-patch14-384` · InsightFace `buffalo_l` · easyocr 1.7.2 · Ollama `qwen3-vl:8b` (fast) · `qwen3.8:27b` (deep + album naming) · `bge-m3` (text embeddings) |
| Code | branch `agent/library-organizer` on `ab1caf8` (see PR for the exact commit) |

## Commands (as run)

```
python scripts/library.py run "C:/Users/techai/Pictures" --parallel 3       # scan → dedup → embed → dedup → faces → review fast → ocr
python scripts/library.py requeue review_deep
python scripts/library.py review --tier deep --parallel 2
python scripts/library.py albums
python scripts/library.py plan --dest "C:/Users/techai/Pictures-Organized"
python scripts/library.py approve --all
python scripts/library.py apply
```

## Receipts (from the store, not from memory)

| Stage | Result |
|---|---|
| scan | 399 files inventoried, 0 failed; SHA-256 + EXIF + pHash/dHash + 1024px thumbnail per file |
| dedup | 382 clusters, **17 duplicates** (SHA-256 + pHash ≤ 6 + embedding-confirmed with pHash guard). Spot-checked pair `Screenshot 2026-07-04 210217.png` / `…210251.png`: same screenshot, one with a window border — correct |
| embed | 399 × 1152-d SigLIP2 vectors, 0 failed |
| faces | 41 faces → 22 persons; 2 persons with ≥ 3 faces (recurring), Person-5 = 14 faces |
| review fast | 382 representatives, 0 failed, **avg 3.34 s/image** (min 3.0 s, max 13.8 s cold), 17 duplicates skipped by design; 323 flagged `document` (screenshot-heavy folder) |
| ocr | 356 documents read, mean confidence 0.80; 43 non-documents skipped |
| review deep | 10 images (fast confidence < 0.7 or sensitive), avg 15.2 s/image on the 27B model, 389 skipped as already confident |
| albums | per-image VLM names: **304** distinct for 382 images → grouped (152 groups, 37 named once by the LLM) → **21 group albums** covering 325 images + 57 long-tail own names → after synonym consolidation at plan time: **68 albums** |
| plan | 382 `link` + 17 `duplicate` (informational) + 15 `People/Person-N` proposals |
| apply | **397 copied, 0 failed, 17 duplicates noted**; manifest SHA-256 `68b38756e4dca496d33d812cb24b5e9c73cf184e6ab99509f30cabcb2f229e85` |
| verification | random 20 applied copies: 20/20 `sha256(dest) == sha256(source) == stored sha` ; source folder still 399 files (nothing moved/deleted) |

Top albums after plan: Developer Work 136 · AI Chat Screenshots 42 · Software Settings 36 ·
Aircraft Maintenance Docs 20 · Social Media Screenshots 19 · AI Agent Builders 10 ·
Technical Evaluations 10 · Kids Biking 5 · Kitchen Prep 4 · Unreal Engine Projects 4 …
Consolidation merged e.g. `Work Chat Screenshots`, `AI Launcher Screenshots`,
`Workplace screenshots` → `AI Chat Screenshots`; `Social Media Posts` → `Social Media Screenshots`.

## Search receipts

```
> beast library search "kids riding bikes outdoors" -k 3
0.090  …\Screenshot 2026-07-05 175445.png  [Kids biking]  Two children riding modified bicycles on a paved road.
0.089  …\Screenshot 2026-07-05 175421.png  [Kids biking]  A child rides a bicycle in a residential yard.
0.071  …\Screenshot 2026-07-05 175429.png  [Biking screenshots]  A person riding a bicycle on a street.

> beast library search --text 3cx
…\Screenshot 2026-09-06 095109.png  [IT Setup & Credentials]  A screenshot of a 3CX cloud setup confirmation screen …   (found via OCR text)

> beast library search --person 5 -k 3
three chat screenshots, all people=[5]
```

## Tests

- `pytest library/tests/test_library.py` — 6 passed (real SQLite, real images, real file ops; the
  "never touches source" test **caught** that hard links let edits propagate to originals → default
  changed to copy).
- `pytest -m live_gpu library/tests/test_library_live.py` — 4 passed with real SigLIP2, Ollama
  review + OCR, bge-m3 similarity, and InsightFace on a real face image (`BEAST_LIBRARY_FACE_IMAGE`).
- Postgres/pgvector backend exercised on the fixture against container `beast-library-pg`
  (:5436): scan, dedup, exclusive claims, `<=>` nearest, faces — same code path.

## Round 2 (same day) — speed and the "magic" features, measured

| What | Receipt |
|---|---|
| Fast tier, Ollama `qwen3-vl:8b` | 0.31 / 0.93 / 0.94 / 0.96 img/s at 1/4/8/16 concurrency (48 images each) — a hard ceiling |
| Fast tier, vLLM `Qwen3-VL-8B-Instruct-FP8` (Docker, WSL2 env vars) | 0.25 / 0.81 / 1.63 / **7.63** img/s at 1/4/8/16; confirmed **7.60 / 7.59** at 16/32 on 96 images (`bench/results/library-review-20260912-1646.json`, `-1647.json`) |
| Full fast tier on the real library via vLLM | 353 representatives, 0 failed, **46 s wall** (was 7 min), avg 2.0 s latency per image under load |
| Burst stacks (real run) | 18 stacks / 30 member frames detected among the screenshots (frames seconds apart, same size); members skipped from review, still placed |
| Events | 106 time-gap events, 0 with GPS (screenshots carry none) → place naming exercised by test on real coordinates: Asheville NC, Berlin-Mitte, Austin TX resolved offline |
| Tests | 42 passed (8 library incl. burst-stack and GPS-trip tests with real EXIF written by Pillow; 34 repo) |

Adopted from the field sweep: batched serving (vLLM), time+GPS trips with offline reverse
geocoding (PhotoPrism/Google-style), burst culling by sharpness (Excire-style). Deferred
with reasons: ONNX/TensorRT SigLIP2 (74 img/s already, not the bottleneck), Perception
Encoder (needs a measured retrieval win on this data), video, timeline/map UI.

## Honest gaps

- Album quality was judged by reading the names and sample groups, not against a labelled set.
- Self-reported VLM confidence is uninformative on this data (0 of 382 below 0.7 in the fast
  tier); the deep tier therefore mostly fires on `sensitive`.
- 22 "persons" from 41 faces in screenshots includes avatars/thumbnails; grouping threshold
  (0.55) not tuned on real portraits.
- Throughput is for 399 images on one GPU; the multi-node path is tested only on the fixture.
