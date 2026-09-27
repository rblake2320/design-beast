# V-JEPA selection replay — frozen before scorer execution

Question: do retained V-JEPA 2 features select more useful review footage than
uniform selection and Watch's retained perceptual-hash changes?

This is a retrospective known-case comparison, not a blind holdout. Existing
independent references and model distances have already been inspected. No
threshold fitting, reference edits, new inference, narration or causal acceptance.

Input commit: a7d8faeca4ede6ff1f540ba14737b6ccdb1285ed in design-beast.
Cases: dense-repair-01 (Blender), heldout-repair-01 (presenter/graphics).
Use six eligible windows starting 4, 8, 12, 16, 20, 22.5 seconds; each contains
16 retained images spaced 0.5 seconds apart. Initial window has no predecessor
distance and is ineligible for ALL arms. Each arm chooses two windows (32 review
image presentations, overlaps charged twice).

- Uniform: center quantiles, windows 2 and 5.
- Pixel: descending mean within-window consecutive perceptual-hash Hamming change.
- V-JEPA: descending cosine distance from preceding validated normalized vector.
- Ties: earlier window first.

Endpoint: number of frozen reference intervals fully contained in a selected
window. This is evidence availability, not event recognition. Also report union
duration, unique images and full selection list. Success: V-JEPA strictly exceeds
BOTH comparators in aggregate without lowering either case's coverage relative
to either comparator. No speed conclusion from cached feature replay.

All arms use identical candidate windows and review budget, NOT equal compute.
V-JEPA's original extraction used 7 x 16 = 112 encoder image presentations per
case; unique source images must be counted. Pixel preprocessing uses 61 frames.
Report original inference timings separately, never as this run's timing.

Verify image bytes, timeline membership, vector finiteness/norm, and recompute
distances. Read all artifacts directly from the fixed Git commit, hash the exact
bytes parsed, retain an input inventory. Never modify historical artifacts.

Research: https://github.com/facebookresearch/vjepa2 and
https://arxiv.org/abs/2603.14482 (accessed 2026-09-27). V-JEPA 2.1 provides newer
dense features; this replay first tests the already-run V-JEPA 2 configuration.
Official upstream inspected at 204698b45b3712590f06245fbfba32d3be539812.
Windows checkout warned about vitG/vitg config filename collisions; upstream
clone is ignored and no checkpoint from that clone has been executed.

Resume: run scripts/benchmark_vjepa_selection.py --source-repo <checkout containing
the input commit> --output <new directory>. Existing outputs are never overwritten.
Then run watch/tests/test_vjepa_selection.py and obtain independent review.

Review erratum: the original committed plan named the wrong tests directory.
Only that resume path was corrected after run-02; protocol and scores unchanged.
Original protocol bytes referenced by run intents remain in commit f4591a3.
