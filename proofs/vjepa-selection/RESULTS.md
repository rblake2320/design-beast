# V-JEPA: selection replay result

SOUL-OUTCOME: V-JEPA 2 did not beat the pixel-change comparator on these two
retained recordings. Keep it experimental; do not make it Watch's default.

| Selected footage contains complete reference interval | Uniform | Pixel change | V-JEPA 2 |
|---|---:|---:|---:|
| Blender (10 reference changes) | 4 | 5 | 6 |
| Presenter/graphics (5 reference changes) | 2 | 5 | 2 |
| Total | 6/15 | **10/15** | 8/15 |

Each arm receives two 16-image windows per clip. These are evidence-availability
counts, not claims that a model identified the events. The comparator uses
Watch's retained perceptual-hash signal with this experiment's window ranking;
it is not a benchmark of the entire deployed Watch pipeline. References are
earlier independent agent visual judgments, not absolute human ground truth.

V-JEPA's Blender windows retain annotation removal and later UI changes; its
presenter windows retain the scene cuts but omit three internal graphic changes.
The pixel arm covers all five presenter/graphics reference intervals. All arms
exclude the first window because it lacks an embedding predecessor; the first
two Blender intervals cannot fit any eligible window. Their misses remain in
the denominator. No tuning or reference correction followed the result.

## Executed comparison and costs

- run-01: original executed scorer and frozen selections.
- run-02: adds the missing union-duration accounting promised in PLAN.md;
  selection and coverage counts are unchanged. Historical run-01 is retained.
- Both read exact committed bytes at a7d8faeca4ede6ff1f540ba14737b6ccdb1285ed:
  122 images, 14 embedding records, timelines, reports and independent references.
- 15 focused adversarial/deterministic tests pass; all 49 Watch tests pass.
  JUnit receipts are retained. Targeted Ruff check passes.
- No new GPU/model/provider calls. New provider charges: $0. Replay wall time
  is in each report and includes Git reads/hash verification, not inference.
- Historical V-JEPA inference used 112 image presentations / 61 unique images
  per clip. Its recorded runs took 84.468s (initial load/download) and 2.969s
  (cached), each with 686.897 MiB peak PyTorch allocation. These are historical
  receipts, not a matched latency comparison or total GPU-device consumption.
- Equal review-window budget is NOT equal total compute. All 61 source frames
  had already been analyzed to produce each case's model features.

## Research and disposition

The [official repository](https://github.com/facebookresearch/vjepa2) now offers
V-JEPA 2.1, including an 80M ViT-B backbone. Its
[paper](https://arxiv.org/abs/2603.14482) focuses on dense visual features.
That is a different candidate from the V-JEPA 2 global pooled embeddings tested
here. This replay supplies a measured reason to test spatial/local temporal
features instead of assuming that a newer encoder improves tutorial recovery.

No production wiring, narration, procedure promotion, existing PR modification,
or model download was performed by this replay. The prior GPU inference is
genuine retained work, correcting the earlier history lookup that missed it.

## Environment and recovery

FFmpeg/FFprobe discovery passed after adding the already-installed WinGet bin
directory to the child shell's PATH only. No machine-level setting changed.
Doctor: 31 OK, optional ComfyUI offline, Ollama unavailable. Neither service is
needed for this CPU artifact replay. Core validation passes (8 capabilities,
1 pack). Dirty original worktrees were untouched.

Implementation lives on codex/vjepa-watch-20260927, based on origin/main 1a7f7ab.
Original artifact commit is reachable on origin/codex/watch-relationships-20260919.
From this branch, after fetching that source branch if necessary:

```powershell
python scripts/benchmark_vjepa_selection.py --source-repo . --output proofs/vjepa-selection/recheck-01
python -m pytest watch/tests/test_vjepa_selection.py -q
```

Choose a new output directory on every replay. Outputs are local until explicitly
committed; no private media are copied. The input inventory records exact Git-blob
hashes. Narrow .gitattributes rules preserve proof bytes across checkouts.

Next candidate experiment: spatial V-JEPA 2.1 features versus this stronger pixel
baseline on a newly frozen set, targeting recovered input/control/result evidence.
This result does not justify replacing the pixel baseline.

## Review follow-up

The independent reviewer reproduced all coverage counts, checked 142 source blobs
and recomputed perceptual hashes from all 122 JPEGs. Its original review is retained.
The PLAN resume-path typo is corrected with an explicit erratum. The original
run-01 source was reconstructed from the one subsequent accounting-only change;
`run-01/implementation.py` hashes exactly to its original intent's
`c759b07107b32445e539660843d39dd1db877886c4c180df6f792b2a7e187c07`.
It is historical source evidence, not a standalone runnable entrypoint from that
archive location. Use the current script for replay.

Six additional tests cover the case-level storage path and hostile inputs plus
real Git failure retention/output collision. Those tests use synthetic storage
fixtures, not real model inference; the two source-backed replays above are the
real-artifact checks. Latest Watch suite: **55 passed**, retained separately in
watch-tests-reviewed.xml. The original 49-test receipt is not overwritten.
Reference-table transcription remains manually independently verified; no claim
of an automated natural-language reference parser is made.
