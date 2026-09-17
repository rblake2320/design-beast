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

## Round 3 — durability, people, and the second real library

**Second real library (`D:\OneDrive\Pictures`, 1,392 files, own store `library/data/onedrive.db`,
dest `D:\Photos-Organized`):** 1,359 assets inventoried (HEIC included), 80 duplicates, **85 burst
stacks / 127 frames**, 149 faces → 84 people (9 recurring), 1,155 fast reviews via vLLM in ≈ 3 min,
1,042 OCR'd, 18 deep, 301 time events (only 1 file carried GPS — this export has no location data,
so place naming is exercised by test, not here), 317 groups → 104 named once → **116 albums**
(Python Selenium Tutorials 169, AI Agent Hive Screenshots 155, Election Tracking 95, Martial Arts
Gear 65, Fantasy Character Art 56 …). Applied: **1,305 files, 0 failed**, 80 duplicates noted,
manifest `fd18962e…`, 30/30 random hash checks, source still 1,392 files, 122 stack folders,
`People/Person-N` for 9 recurring people, backup 115 MB in `D:\Photos-Organized\.beast\backups`.
Mid-run I killed the process during OCR on purpose; `recover` reclaimed the 1 running row and
the remaining stages resumed with no rework.

**People (phone-style):** on the first library, faces v2 grouped 41 faces → 17 people; naming
person 24 (`--label 24 Test-A`) returned all 14 photos and `search --person Test-A` works by
name; the live InsightFace test passes on a real face image. A "same person?" check on three
visually similar YouTube-thumbnail persons measured exemplar cosines 0.145 / −0.087 / 0.079 —
the model says different people, and on inspection it was right.

**Fault-injection tests (all real, `library/tests/test_recovery.py`):** worker death → reclaimed;
model server down → work returns to `pending`, nothing marked error; crash mid-copy → no half
file, redone; edited copy → reported, never overwritten; backup/restore round trip with an
integrity gate; lost store rebuilt from the manifest without re-copying; album change → atomic
verified move; private folders never handed to a remote worker; video via a real ffmpeg frame.

**Soak (`bench/library_soak.py`, watch mode + live faults), honestly:**
- Run 1 (40 min): reported "pass" but **no fault ever fired** — a scheduler bug (`dict.pop` in the
  condition). Discarded as evidence.
- Run 2 (25 min): faults fired. kill → supervisor restart 5 s later; vLLM stopped → the next two
  cycles reviewed with Ollama `qwen3-vl:8b` (loud fallback in the log) → back on vLLM after
  `docker start`; 11 cycles, 0 loop errors, integrity ok. **Verdict FAIL**: the simulated owner
  approval never ran (another script bug), so 0 files were placed and the partial-file fault
  had no target. `bench/results/library-soak-20260912-1825.json`, `-…-19xx.json`.
- Run 3 (25 min): approval step ran (12 approved) but **still 0 placed** — this time a real product
  defect: every watch cycle re-plans, and the proposal upsert reset `approved` back to `pending`.
  Fixed in `store.put_proposal` (an approval survives a re-plan unless dest or album changed) with
  regression test `test_approval_survives_a_replan_unless_the_proposal_changed`. Verdict FAIL, kept.
- Run 4 (25 min, `bench/results/library-soak-20260912-1948.json`): **unattended operation
  worked** — 102 photos fed in batches, 76 auto-placed across cycles (one via a reconcile move),
  34 held for approval because their albums were new, 69/69 placed files hash-verified by
  `recover`, 18 cycles, 0 loop errors, kill → restart in 5 s, vLLM outage → 3 cycles on Ollama →
  back. Verdict FAIL only because the partial-file fault found no `*.jpg` target in a PNG
  seed set (harness glob) — the class itself is covered by `test_crash_mid_copy_…`.
- Run 5 (20 min, `bench/results/library-soak-20260912-2010.json`): **PASS with every fault
  fired** — owner approval at 2:30 (12), watcher killed at 5:00 → restarted 5 s later (1 stale
  claim reclaimed), vLLM stopped 8:02 → cycles fell back to Ollama with the loud warning →
  vLLM restarted 12:03 → back on the batched tier, a placed file replaced by a `.beast-partial`
  at 16:03 → `recover` removed the partial, re-approved the missing file (verify 5 checked:
  4 ok, 1 missing_reapproved) and it was restored; 84 photos fed, 5 auto-placed (this run's
  first approval covered few albums; 85 held for approval as designed), 0 unplaced, 0 wrong
  hashes, 0 partials left, 13 cycles, 0 loop errors, integrity ok.

Verdict after five runs: every failure class is now proven both by a unit test and by a live
fault under watch mode on this machine. Still open for a higher tier: a 24 h run, a ≥10k-image
library, and a DGX Spark worker on the shared pgvector store — **Pilot** stands.

## Honest gaps

- Album quality was judged by reading the names and sample groups, not against a labelled set.
- Self-reported VLM confidence is uninformative on this data (0 of 382 below 0.7 in the fast
  tier); the deep tier therefore mostly fires on `sensitive`.
- 22 "persons" from 41 faces in screenshots includes avatars/thumbnails; grouping threshold
  (0.55) not tuned on real portraits.
- Throughput is for 399 images on one GPU; the multi-node path is tested only on the fixture.
