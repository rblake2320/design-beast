# Independent native-frame action recovery review

Reviewer: separate `/root/training_review` agent. Date: 2026-09-19.
Reviewed implementation commit: `2bd1b71579a6ca4283f7e506f846ad674d3fe69e`.
Scope: this known Blender recording, clip interval `[0, 2)` seconds, and the ten retained counterbalanced timing pairs. No implementation edits, model inference, narration, or merge performed by reviewer.

## Tested verdict

**Action recovery: FAIL.** Exhaustive native-frame visual review did not recover an identifiable initiating input plus its activated control plus the resulting viewport change. The visible result is supported; its causal user input is not recovered. This is an attempted test with a negative result, not an unattempted disclaimer. It does not mean no action occurred, nor prove that action recovery is impossible in other recordings or outside this interval.

**Local extraction timing criterion: PASS.** Independently recomputed from all ten pair receipts: rewind faster in 10/10 pairs; median paired reduction `0.15289607716824966` (15.2896077%). This meets the retained protocol's at-least-8/10 and at-least-10% criterion. This is not a pass for causal recovery or end-to-end video comprehension.

## Actual visual coverage and findings

I viewed all ten `native/sheet-01.jpg` through `sheet-10.jpg`, covering all 60 decoded frames in chronological six-frame groups. Each sheet uses six 640x360 full-screen images, without region cropping. I additionally inspected native 1280x720 frames 35, 36, 37, 38 and 39 to resolve the transition labels and controls. Thus all frames were visually covered through sheets; not every frame was separately opened at full native size.

Regions inspected throughout the sheets: central viewport/model and pencil cursor; upper-left view labels and tool options; top menus/workspaces/header; left tool strip; upper-right view-axis gizmo; right outliner/properties; bottom status bar. Full-size transition checks included the same regions.

- Frames 1–35 show the oblique/side model view; frame 35 at `1.133333` seconds reads **User Perspective (Local)**.
- Frame 36 at `1.166667` reads **User Orthographic (Local)** and begins the visible change in viewpoint.
- Frames 37 (`1.200000`) and 38 (`1.233333`) still read **User Orthographic (Local)**, with progressively frontal orientation.
- Frame 39 at `1.266667` reads **Front Orthographic (Local)** with the front grid. This result persists through frame 60 at `1.966667`.
- The pencil-shaped cursor is beside the model, not visibly activating the view gizmo or a menu. I found no displayed keystroke, click indicator, depressed control, physical input-device view, or visible menu-selection sequence that identifies the initiating input.

The native recorded label-change bracket is therefore `(1.233333, 1.266667]` seconds. Earlier sparse extraction requests at 1.20/1.25 seconds were request coordinates, not exact decoded-frame PTS, and must not replace this native timestamp bracket. Neither label change nor viewport rotation proves a particular keyboard shortcut, mouse action, or other cause. Control/action debt remains unresolved; no verified procedure follows from this review.

## Receipt and timing verification

I independently checked all 60 JPEG hashes against the native manifest (zero mismatches), all timestamps against the ordered 30 fps grid from 0 through 59/30 (zero mismatches within one microsecond), and the actual source SHA256. Every file in the retained `proofs/watch-rewind-outcome/run-01` copy matched its corresponding local run file byte-for-byte.

All ten pair report arm times exactly match their top-level timing entries. Recomputed `1 - rewind_seconds / baseline_seconds` matches every retained reduction; sorted midpoint median agrees with the reported value. Pair protocols alternate baseline-first and rewind-first five times each, matching actual report arm order. Both arms charge 16 frames with a 60-second cap. Baseline retains 16 unique requested frame paths; rewind retains 14 due to reused coarse/refined timestamps. The latter does less unique extraction work, an important contributor/confound: this is not a claim of faster processing for equal unique decode counts. Setup/copy, full native review, reasoning and narration are outside the timed unit. Ten repetitions of one warm known fixture are not ten independent videos or a generalized speed benchmark.

## Source review and tests

Read `scripts/prove_watch_rewind_outcome.py` and the `reverse_order` implementation/test diff. The two possible execution orders are actually used, not only recorded. The outcome script retains its protocol before execution, checks native count correspondence, hashes source before/after, preserves failures, and leaves publication false. No code path promotes the timing pass into a verified action.

Reviewer ran `python -m pytest tests/test_watch_rewind.py -q`: **24 passed**. The builder's broader full-suite result was not independently rerun here.

No blocking implementation defect found for this named 30 fps, zero-origin, two-second fixture. Generalization limitations: sheet production is hardcoded to ten sheets/30 fps; timestamp selection checks `<2` without an explicit nonnegative predicate; ffprobe examines the whole input; the new regression checks the reverse-order default/signature rather than exercising both execution orders (actual retained runs supply that evidence here). These do not invalidate the verified fixture, whose 60 timestamps are nonnegative and accounted for, but this script should not be represented as a general arbitrary-video coverage harness.

The run report intentionally still says `awaiting_native_frame_review`; this separately authored review supplies the completed **FAIL** action verdict without rewriting the builder's original receipt. The failure blocks any claim that this tested interval yielded a recovered causal instructional action. It does not block retention of a correctly labelled result-only observation or the narrowly measured timing result.

## SHA256 bindings

The following three reviewed source files match both working-file bytes and Git blob bytes at the named commit:

| File | SHA256 |
| --- | --- |
| `scripts/prove_watch_rewind_outcome.py` | `2384f591252b302dab6575cc65e73946f2a844a9b3579f22bd634f9af0ba6263` |
| `scripts/evaluate_watch_rewind.py` | `94a1177426a4dcfae56c814ba535b5688f28d6b71a5f24d5e49694c7e9e2731f` |
| `tests/test_watch_rewind.py` | `19cf767f2c4828af9185e00e41ac6094c1f6b6104d33d9e95db8a726e23df841` |
| Actual source MP4 | `46ca6a61fa8cd4802284014fa091570e933403da1767d03f92108a6d4a78b8b1` |
| Native manifest (contains all 60 frame hashes) | `cc191ab3319698bdaf288b82ae2d5dafc6bb15dbece179b5f56ede723d2223d2` |
| Run protocol | `69c3cc437239922872d48147298936390d4f9a39da1119a2b63ab3db692c08d9` |
| Run report | `75846cd9388ff9364062e1abb984489a85ed17885a0c667c157753f4a55342ac` |

Per-pair execution hashes describe actual on-disk source bytes. The previously documented inherited `watch/seek.py` CRLF-vs-Git-LF distinction remains; this review does not claim all inherited execution hashes equal Git blob hashes.

Final disposition: **retain the local timing PASS and actual causal-input recovery FAIL, separately. No procedure promotion or generalized capability/merge approval.**
