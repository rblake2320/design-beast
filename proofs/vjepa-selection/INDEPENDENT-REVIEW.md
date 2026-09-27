# Independent bounded review

Reviewer: `/root/vjepa_review`, 2026-09-27. Reviewed implementation commit
`f4591a3be0e98753513992b8ebf1d7bb63e0ab5f`; source artifacts read directly from
`a7d8faeca4ede6ff1f540ba14737b6ccdb1285ed` in
`D:/content/design-beast-relationships`. This review grants no approval,
readiness tier, merge authorization, semantic recovery, or production speed claim.

## Observed result

The frozen retrospective interval-containment result is reproduced:

| Case | Uniform | Pixel change | V-JEPA | Reference intervals |
|---|---:|---:|---:|---:|
| Blender | 4 | 5 | 6 | 10 |
| Presenter/graphics | 2 | 5 | 2 | 5 |
| Total | 6 | 10 | 8 | 15 |

V-JEPA selection graduation is correctly FAIL: it loses to pixel change overall
and on the second case. These counts describe full reference intervals contained
in selected sampled windows. They do not demonstrate recognition, semantic
recovery, causality, continuous-frame coverage, procedural acceptance, or faster
production Watch operation. The second case's historical name `heldout` does not
make this retrospective selection experiment blind.

## Independent execution and artifact checks

- `python -m pytest watch/tests/test_vjepa_selection.py -q`: exit 0;
  15 passed in 0.92 seconds. Tests are deterministic helper tests, without models.
- `python scripts/benchmark_vjepa_selection.py --source-repo D:/content/design-beast-relationships --output C:/Users/techai/AppData/Local/Temp/vjepa-independent-3c90a5f9549e49fd93c883c22bfbd395`:
  exit 0; replay wall time 8.716452099964954 seconds. This is CPU replay timing.
- A separate inline verification program fetched every inventoried blob with
  `git show <fixed-commit>:<path>`: all 142 lengths and SHA-256 values match;
  the fresh inventory equals run-02's inventory.
- Independently decoded all 122 JPEG blobs with Pillow and recomputed the
  8-by-8 grayscale average hashes used by Watch: zero timeline hash mismatches.
- Independently recomputed predecessor vector dot products using `math.fsum`:
  maximum stored-distance discrepancies were 6.939320396082138e-08 (Blender)
  and 1.0456042576212354e-07 (presenter/graphics), below scorer tolerance.
  The replay also validated all 14 window memberships and vector norms.
- Manually compared all 15 hardcoded intervals with the two references read
  from fixed Git blobs. Blender source intervals minus 1800 seconds and the
  heldout clip intervals match exactly.
- Independent containment calculation returned Blender hits
  uniform [4,5,6,7], pixel [6,7,8,9,10], V-JEPA [4,5,6,7,8,9];
  heldout hits uniform [1,5], pixel [1,2,3,4,5], V-JEPA [1,5].
- Fresh report equals run-02 after removing only `replay_wall_seconds`.
  Fresh protocol and implementation hashes equal run-02's intent hashes.
  run-01 differs by missing union durations and elapsed timing; selected
  windows and coverage counts are unchanged.
- `python scripts/doctor.py`: exit 1, 29 OK, 1 optional degraded, 3 failing.
  ffmpeg and ffprobe were not found by the doctor; Ollama was unavailable;
  ComfyUI server was optionally degraded. These paths were not used by the
  successful CPU replay. No GPU inference or provider call was performed.
- Knowledge services: MemoryWeb health OK and search yielded unrelated context;
  UltraRAG health OK with its MemoryWeb integration reporting 401; search failed
  with an HTTP error. Neither supplied evidence used for this verdict.

## Findings and limits

1. Low severity, reproducibility instructions: PLAN.md names nonexistent
   `scripts/tests/test_vjepa_selection.py`; the actual test is
   `watch/tests/test_vjepa_selection.py`.
2. Test gap: the 15 tests exercise helpers but do not execute `case`/`run`
   against hostile bundles. Add focused integration coverage for corrupted
   image bytes, window membership mismatch, forged distances, missing/malformed
   blobs, output directory collision, and failure-receipt preservation. The
   actual frozen positive path was executed independently in this review.
3. Test gap: reference intervals are manually copied into code. Hashing the
   Markdown establishes custody but does not enforce correspondence between
   those bytes and the hardcoded labels. All labels match today; a machine
   readable frozen reference or explicit correspondence regression would
   detect future drift.
4. Historical reproducibility limit: run-01 has a different implementation
   hash without its original source revision retained in this proof bundle.
   Its coverage matches run-02, but exact run-01 source replay is not established.
   run-02 matches the reviewed implementation exactly.
5. The scorer trusts retained perceptual hashes instead of recomputing them
   from the verified image bytes. This review independently recomputed them and
   found no mismatch. That link is currently reviewer evidence, not an enforced
   scorer check.

No correctness defect was found in the frozen 6/10/8 arithmetic. Only these two
known clips and the specified 32 image-presentation selection budget were tested.
No model performance generalization or downstream visual review was performed.
