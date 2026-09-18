# Independent multichannel review — 2026-09-18

Reviewer: separate `/root/inspection_review` agent. Read-only source review,
retained-artifact inspection and CPU regression tests; no inference reruns,
provider calls, source edits or merge. This supplements, not replaces, the
initial INDEPENDENT-REVIEW and frozen semantic grades.

## Disposition

Real retained spatial measurements, detector outputs and temporal features are
present. This is useful additional visual evidence, not autonomous event
recovery, verified instruction generation or a repaired semantic challenge.
Two fusion validation gaps below need correction before broad input-lineage
claims. The observed frozen runs themselves passed the independent hash checks.

## Checks performed

- Focused tests: `python -m pytest watch/tests/test_visual_state.py
  watch/tests/test_pixel_policy.py watch/tests/test_perception_runtime.py -q`:
  **14 passed**. Tests did not run a detector or encoder.
- Independently verified all **122** pixel state bytes against their report
  hashes, matching frame identity and clip time in blender-02/heldout-02.
- Verified **122** OmniParser records refer to those same frames and times,
  and all fused-blender-02/fused-heldout-02 records bind the actual UI and pixel
  state hashes. These are new run-02 receipts, not retrospective validation of
  the older run-01 program against newer guards.
- Verified all **14** encoder windows contain 16 references to the corresponding
  known frames and 1,024 finite components. Squared norms ranged from
  0.9999998880 to 1.0000000783. Recomputed consecutive cosine distances differed
  from retained values by at most 1.05e-7.
- Detector output totals: Blender **4,930 boxes**, held-out **7 boxes**. Reported
  CPU elapsed times: 18.313s and 15.625s. These are proposal counts, not accurate
  element counts. Representative Blender boxes cover property panel rows;
  held-out clip20s includes a document/icon proposal. No function, cursor class,
  clickability or tracking identity is established by these boxes.
- Encoder reports record 84.468s first run and 2.969s second run, each peak
  allocation 686.897MiB. Loading/cache effects make these unsuitable as a
  comparative speed claim. No inference benchmark was rerun independently.

## Does this add evidence?

Yes, but bounded. Regional affine estimates at original clip9.5s are about
0.977 in three tiles, unlike the earlier static-chrome-dominated global scale.
The actual frame-019 diagnostic was visually inspected: viewport grid and body
carry spatial motion tracks and changed components. This supports apparent
image contraction; it does not prove the operator zoom command, a scene-unit
scale change or causal input. Other sampled zoom intervals still yielded no
regional estimate differing from one by more than .01; complete zoom recovery
has not been demonstrated.

V-JEPA distance peaks in overlapping 7.5-second windows add coarse temporal
features. They do not distinguish annotation from sculpting, recover eraser
identity or precisely locate a window switch. This experiment supplies 16
sampled frames per window; the pinned upstream card illustrates 64-frame video
input, so this is not a reproduced upstream evaluation protocol.

Fusion retains the channels side by side. **PixelInspectionPolicy currently
uses only the pixel state**, not UI detections or temporal embeddings. Blender
recommendations: 58 compare_states, 2 increase_density, 1 request_slow_review;
held-out: 57 compare_states, 4 increase_density. These recommendations were not
executed. Thus no measured reduction in inspections, costs, false acceptance
or missed events exists. Three confidence dimensions remain separate; null
measurement confidence and explicitly unestablished zero policy inputs are
not detector-score-derived evidence verdicts. There is no procedure promotion.

## Robustness findings

1. **Fusion report-to-state binding missing at reviewed source.** The state
   file hash is checked, but state.frame_sha256 and state.clip_ms are not
   compared to that report row's sha256 and clip_ms. Temporal membership uses
   the report values while UI membership uses state values. An inconsistent
   report can therefore join different pixel identities. Validate both fields
   and exact chronological report order. The actual 122 records independently
   passed these comparisons; this is an input-validation flaw, not a claim
   that the retained experiment was mixed.
2. **Temporal distance copied without verification.** The vector is checked
   finite and normalized, but distance_from_previous is copied without a
   finite/range check or derivation from adjacent validated vectors. Recompute
   or cross-check it. The actual 12 non-null distances passed independent
   recomputation above.
3. Pixel runner now checks deadline after observation and before final report,
   and passes remaining time to OCR. Decode checks PIL header dimensions before
   OpenCV allocation. These address the earlier principal findings. The new
   encoder/detector scripts have fixed count caps but no wall-clock deadline
   and do not reuse the predecode size guard. Their inference/download time is
   not a bounded production job. Restrict claims to frozen trusted inputs.
4. Encoder revision is pinned and safe tensor loading disables remote code;
   OmniParser retains the downloaded weight hash and upstream license. Temporal
   windows bind input JPEG hashes, not hashes of processed tensors/model weight
   bytes. Pinned revision and local successful output are not an independent
   reproduction or a trustless runtime attestation. Original-video offset
   pinning remains the previously documented gap.

## Licensing boundary

The retained OmniParser `weights.json` contains the actual detector AGPL-3.0
text. Do not call the optional detector universally permissive or regard
non-vendoring as product licensing approval. The pinned [V-JEPA HF model
card](https://huggingface.co/facebook/vjepa2-vitl-fpc64-256/blob/b3c1679b7c34d3255ef3547f27c7b226aefab26f/README.md)
labels its artifact MIT; [upstream code license](https://github.com/facebookresearch/vjepa2/blob/main/LICENSE)
is MIT. This review identifies source metadata, not legal clearance for every
dependency, weight derivative or distribution/service configuration.

## Reviewed source SHA-256

| File | SHA-256 |
|---|---|
| watch/visual_state.py | 3c5e50562599c624a120c376dab4342e1c4a8ad49ec6067ec2372f8b926d4a80 |
| scripts/watch_perception.py | b49f482f8eb9a9fa1f31384c7b821aa302cf4f404ce0fd04b52ce10a6c9c902e |
| scripts/watch_temporal_encoder.py | 50cb1db6017617792c233226ee867fae28937ba1253a3717f417eed2cdfaeed0 |
| scripts/watch_ui_regions.py | 45a44633dd633ef409806c255eb658674c1f5be63bfbf82deaaec7e16adfd77c |
| scripts/fuse_watch_state.py | 6a35f0f8e5b16ad6d25238e4b34e170eb740b8ea62d40d3a7b7ad000d3ed76a4 |
| watch/pixel_policy.py | 756f9b2336780801a5c8011a75c1cd94c2a6255b88d63723da988237c049caef |

Later source changes require a separately identified addendum. No previous
semantic failures are regraded as a pass by these measurements.

## Closure addendum — exact commit 94ef441

Independently reviewed commit `94ef441f494b7fbc10877f54c7b6a6c286da5dfd`.
The checked production files and regression tests matched that commit after
normalizing checkout line endings. Earlier observations above remain historical;
this addendum supersedes only their stated open source findings and policy-input
description.

**Both specific fusion findings are closed for this bounded experimental lane.**
Fusion now requires the actual state's frame hash and clip clock to equal the
corresponding report row. It requires the first temporal distance to be absent,
recomputes subsequent distances from the validated vectors, and rejects
nonfinite or discrepant values (tolerance 1e-5). Region boxes/scores are finite,
bounded and exact-schema validated. Regression cases reproduce a modified state
with an updated state-file hash but inconsistent report identity, and a forged
temporal distance; both fail closed.

The same focused command listed above now independently passes **17 tests in
0.61s**. No detector/encoder inference was rerun.

Independently rechecked **122 run-03 records**, including all three component
report hashes in each fusion intent, state/report/fused frame identity and clock,
pixel-state hashes, UI-record hashes and every included temporal-window hash and
coverage interval. `fused-blender-03` binds `fresh-ocr-blender-01`, not the reused
OCR pixel run; `fused-heldout-03` binds `heldout-02`. Both final reports retain
zero inspection executions, semantic acceptances and procedure promotions.

The policy now genuinely consumes UI proposal count and temporal distance as
inspection scheduling inputs. Actual run-03 recommendations were:

| Run | increase_density | compare_states | request_slow_review | run_ocr |
|---|---:|---:|---:|---:|
| Blender | 2 | 35 | 24 | 0 |
| Held-out | 4 | 39 | 13 | 5 |

The `.1` temporal scheduling threshold is an uncalibrated heuristic; it is not
an evidence gate. The policy preserves the three independent confidence inputs,
and does not execute these recommendations. No benefit or optimality claim is
established by different recommendation counts. Existing no-deadline limits for
model runners, licensing qualifications, original-offset custody limit and
unresolved semantic grades remain. Updated WATCH-PIXEL-STATE documentation
explicitly records the model-runner deadline and licensing limitations.

Reviewed repaired SHA-256:

- scripts/fuse_watch_state.py:
  `aef4b48d0fd2a026b4491ebe0af28f9570bfd1f31ca69ef3ee11c43b725f51fc`
- watch/pixel_policy.py:
  `6503552eaa2ff517b2d12cdcb0f97e7fb2f7964f69569194f3c86c8b274fb740`
- watch/tests/test_perception_runtime.py:
  `59f18aec6aae8c10c159faf5b401b3d246edccbacaf10b9c639593e506be429f`
- watch/tests/test_pixel_policy.py:
  `ddc5d07ed4195593431f44fea85e3b45c8875a72ded8c486377b48f5f5a940d8`

Disposition: no remaining blocker identified in these specific repairs for
retained-input, recommendation-only experimentation. Not general-input hardening,
semantic success, deployment approval, or permission to merge.

## Git-byte portability addendum — eee4ce6

Independently checked exact commit
`eee4ce683af8b55244cb51fc4eafa19a1269bc1b` using raw `git cat-file --batch`
blob bytes, not PowerShell text conversion. All **2,254 committed JSON files**
in the two protected proof trees equal the retained local bytes. All **305
pixel-state report hash links** across the five pixel runs match their committed
state blobs. Both run-03 fusion intents and all **122** fused records' pixel,
UI and temporal-window links also match committed blobs.

All six measured implementation files contain LF-only committed bytes, equal
the working files and equal commit94ef441 after line-ending normalization.
Their hashes match the reviewed hashes above. The blender-02, heldout-02 and
fresh-ocr-blender-01 implementation receipts match committed visual_state.py.
This confirms source-algorithm continuity for this packaging repair, not a new
inference result.

The added `watch/tests/test_evidence_git_bytes.py` independently passed:
**1 passed in 1.78s**. No previous inference or previously passed focused suite
was rerun. `.gitattributes` disables JSON text normalization in the two proof
trees and enforces LF for the six measured source files. The identified
committed-byte portability defect is closed for this reviewed scope. No new
semantic or deployment claim follows.
