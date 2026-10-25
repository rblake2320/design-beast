# Independent bounded-rewind review

Reviewer: `/root/training_review`, 2026-09-19.
Reviewed implementation: `f79ca004be0ec14056ff37b3e94b0069a85f0ed7`.

**Disposition: accepted for the declared scheduling/mechanical draft proof.**
No causal action evidence was established by this review; no merge approval,
efficiency win, generalized action recovery or reproducibility claim is granted.
I edited only this review, not implementation or previous reports.

## Personally checked

- Read `watch/rewind.py`, `scripts/evaluate_watch_rewind.py`, new tests and the
  existing inspection-execution boundary. Ran `python -m pytest
  tests/test_watch_rewind.py -q` against the committed source: **23 passed**.
  Contract, budget and synthetic preflight tests are distinct from real-video
  evidence; they do not measure semantic action recovery.
- Inspected run-02 protocol, seed, first/refinement receipts, pixel-change
  measurements and reports. The shared search window is clip 0..2000ms, with
  16 charged-frame and 60-second caps per arm. The result anchor is supplied by
  a reviewed seed, not automatically discovered or hidden ground truth.
- Independently verified all **30 retained arm-specific JPEG files** against
  their reported hashes, both in the original run-02 directory and committed
  `proofs/watch-rewind/run-02`. They represent **25 distinct image hashes** across
  arms. All run-02 frames are byte-identical to their corresponding run-01 files,
  so direct visual inspection of those exact run-01 bytes applies to run-02.
- Baseline: 16 charged requests, 16 unique timestamps, 1.306155100 seconds.
  Rewind: five coarse requests plus eleven refinement requests, 16 charged total,
  14 unique timestamps, 1.065399200 seconds. The two reused endpoints remain
  charged; they are not presented as free inspections.
- Highest coarse full-frame RGB mean absolute difference is the 1000..1500ms
  interval (4.8080794271). Refinement samples that interval every 50ms rather than
  inferring an action or clearing evidence debt. Final winner and semantic metrics
  remain null; publication and verified-procedure flags remain false.

## Visual evidence and causal boundary

I directly inspected the transition-neighborhood images from both arms, including
rewind 1.00, 1.05, 1.10, 1.15, 1.20, 1.25 and 1.30 seconds, and baseline 1.067,
1.20 and 1.333 seconds. These selected semantic inspections are not a claim to
have manually examined every pixel of every retained frame.

The images show a progression from User Perspective to an intermediate User
Orthographic orientation, then Front Orthographic with the front-facing model
and grid. Rewind samples show the final label by 1.25s; baseline samples show it
by 1.333s. The preceding inspected sample at 1.20s still shows User Orthographic.
Thus the requested sample timestamps bracket the visible final-label transition
at **1.20..1.25s** versus **1.20..1.333s**. Neither is an exact physical onset-time
measurement independent of frame extraction/rounding.

No keypress display, button activation, or other causal input is visible in the
inspected images. The pencil cursor remains near the model; its presence is not
evidence of a click or keyboard shortcut. More intermediate pictures refine a
visible transition, not the cause of that transition. I therefore leave control
and action **unresolved**, and reproducibility **untested**. Absence of visible
input in these samples does not prove that no input occurred between samples.

## Findings and final safeguards

- Reviewed the final seed-end/source-duration bound and the finite bounded
  confidence types; pending/foreign/tampered/out-of-range preflight cases reject
  before FFmpeg. No unsupported confidence values or seed-range promotion were
  accepted by the tested final guards.
- The scheduler only recommends a denser interval. Execution remains in Watch's
  existing bounded executor with source/frame hashes, locking and write-ahead
  receipts. No new action executor, narrator or evidence-promoting authority is
  introduced.
- Run-01 retains its earlier source-byte hashes. Run-02 was freshly executed
  with the strengthened validation/schema version; the earlier artifact was not
  silently relabeled as a run of final code.
- Elapsed time excludes initial source copying/setup and reflects one fixed-order
  known-case run. Cache warming and different measurement work prevent any speedup
  conclusion. Equal caps do not imply equal realized compute or a useful semantic
  advantage. The baseline is a budget-fitted deterministic Watch adapter, not an
  unchanged benchmark of every existing Watch behavior.

## Exact source-byte qualification

The three new implementation/test files match their Git blobs byte-for-byte:

| File | SHA256 |
|---|---|
| watch/rewind.py | 761ab2708011a9110ccbafe75accb822258bc7a09b1182ca630eaf0718418af8 |
| scripts/evaluate_watch_rewind.py | 5b9228e00574efd3dbb53fbe33e97c652fb0804c6839125c1d7d39297fca879b |
| tests/test_watch_rewind.py | fccdaa8f5689cd783c555ba83e247ac1e824c59ab1066bc8214c95f4b86a1ead |

Four of the five execution-protocol code hashes match committed Git blobs.
The inherited `watch/seek.py` is an explicit exception:

- Executed Windows CRLF bytes / protocol hash:
  `bf73063f57ece2a7ff5d46333ec0a6fbe626b64e3e0c27831334bc8b099520d9`.
- Committed LF Git blob:
  `b6cedbd7cfae7b15d8ac162e790a2fb0d06131cad5afc6af397d21e91aba22b2`.
- Independently checked that replacing CRLF with LF produces exactly the Git
  blob, with no other content difference. This is a raw-byte portability
  distinction, not an unexplained code change. Do not claim all five raw
  execution hashes equal Git hashes or rewrite the original protocol hash.

## Remaining proof limits

The builder reports 404 full-suite passes, one Windows symlink skip and seven
GPU-test deselections; reviewer personally ran only the 23-test focused suite
above. No GPU/model/API work was performed by this reviewer. The source MP4 is
not committed; remote readers can inspect the frames but cannot independently
re-decode without the source. No unseen-case corpus, semantic detector, causal
verification, event graph, learned scheduler, calibrated confidence, action
recall, human-time savings or industry comparison is established. Full-frame
pixel change can prioritize an irrelevant visual event. Review/source hashes
are local custody records, not authenticated reviewer identity or a hostile-
filesystem sandbox. Future implementation changes require affected-scope review.
