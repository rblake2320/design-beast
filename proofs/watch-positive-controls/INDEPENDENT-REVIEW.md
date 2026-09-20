# Independent positive-control review

Reviewer: `/root/training_review`, 2026-09-19. Reviewed actual `watched/positive-comparison-01` plus the four source review bundles. Implementation was uncommitted atop `41adb047eb3cbe97aa229e26247e33733e9a5469` when inspected; execution hashes below bind the reviewed bytes. No implementation edits, new inference, or merge approval.

## Verdicts

**Explicit visible input-indicator recovery: PASS on these controls.** Both arms recover the three positive case events with correct kind/key and emit no proposal on the one matched negative clip.

**Rewind graduation: FAIL.** The declared requirement is more recovered independently labelled events than baseline without more false inputs. Both recover three; a tie is not graduation. Additional frame hits do not represent additional events.

| Case | Frozen visible label | Baseline frame hits / events | Rewind frame hits / events | Wrong kind/key |
| --- | --- | --- | --- | --- |
| 01 | Mouse DOWN over Save | 4 / 1 | 3 / 1 | 0 / 0 |
| 02 | Key S DOWN | 3 / 1 | 1 / 1 | 0 / 0 |
| 03 | Mouse DOWN over Save, delayed result | 3 / 1 | 7 / 1 | 0 / 0 |
| 04 | No input visible in retained samples | 0 / 0 | 0 / 0 | 0 / 0 |

One positive event per case is the fixture's declared unit; duplicate images or repeated DOWN frames do not increase recall. False-input cases are zero for both arms within these four controls. This is neither a population error-rate estimate nor proof of causal-chain recovery. The detector reads an explicit textual indicator rendered in the real test application; it does not detect an otherwise invisible mouse press in arbitrary footage.

## Independence and actual artifact checks

I authored and froze `BLIND-LABELS.json` before reading scheduler outputs, recorder/fixture code, or private telemetry. Its current SHA256 remains `9f7b26a9efc0eb548b514c3f21860b56aaf0a7d1d129ea74e747bd089e324017`, matching the comparison's write-ahead protocol. The original file was not revised after unblinding. Blind coverage was all 50 supplied full-frame sparse JPEGs, whose hashes and source hashes were checked.

After unblinding, I inspected all eight OCR arm reports and personally viewed all 13 distinct positive-hit JPEG contents across their repeated proposals. Every positive image actually displays the recognized DOWN indicator; keyboard images display S, not another key. I additionally viewed five actual negative-arm images (beginning and around the result change across both arms), alongside the previous complete nine-frame sparse negative review. I verified all 120 extracted arm-frame file hashes against arm manifests; no mismatch. Negative reports contain no proposals. I did not rerun OCR or exhaustively decode the full recordings.

Each baseline arm uses 16 OCR calls and each rewind arm 14, matching its unique supplied frame count. Both have 16 charged sampling requests and identical declared maximum caps: 16 requests, 16 decodes, 16 OCR calls, zero model tokens, 60 seconds sampling and 60 seconds OCR. OCR phase times are under 60 seconds. Fewer unique frame paths mean less actual OCR work in rewind; equal caps are not equal consumed work. No VLM/GPU recovery was performed.

Independently ran ffprobe on all four actual source files: all are **1280x720, 25/1 fps**, not 60 fps. Cases 01–03 are WebM content copied under a `.mp4` filename by the preparation script; decoders identify the content successfully, but that extension does not establish MP4 container format.

## Unblinded fixture provenance

Read recorder, preparation script, HTML fixture and private telemetry only after labels froze. The recorder uses real Playwright mouse/keyboard events in a headless Chrome page and retains actual browser video. DOM handlers render DOWN text at the time of events, rather than painting it onto the video afterward. Telemetry reports trusted pointer down/up and save request for 01/03, and trusted S keydown/up and save request for 02. Result-visible entries correctly have `trusted:false` because they are programmatic timer callbacks, not input events.

The fixture saves on click or S keyup, not on the DOWN indicator itself. Consequently the OCR output cannot establish the actual save-triggering release/click or causal chain. The trusted telemetry and inspected fixture code substantiate the controlled test's intended event chain independently of OCR; they are not pixels-only recovered evidence and were not given to the recovery code.

Case 04's trim receipt identifies case 03 source hash `1c72f39a4655ad2f568da96cce5347d88658dfcea6c47185e339e4e48ae92b57` and removes the first 2 seconds. The parent sparse images show DOWN at request times 1.25/1.50 and no DOWN at 1.75/2.00; the trimmed clip starts after that visible input and retains the delayed result. The preparation command and matched parent hash support this negative's construction. DOM `performance.now()` timestamps and video PTS have no retained exact clock bridge, so I do not subtract those clocks to claim an exact native input onset. This negative establishes missing input within the retained evidence, not that no action occurred.

## Code review and tests

Read `observe_watch_input_overlays.py`, `compare_watch_positive_controls.py`, `score_watch_positive_controls.py`, recorder/preparer and fixture. Recovery code reads frame pixels, not private DOM/telemetry or blind-label contents; comparison hashes labels only. The separate scorer consumes labels afterward and deduplicates case-level proposal kinds, correctly yielding a tie/FAIL here. Frame containment/hash checks precede OCR, requests have remaining-time timeouts, failures are marked incomplete, and publication/causal acceptance remain false.

Reviewer ran `python -m pytest tests/test_watch_input_overlays.py tests/test_watch_rewind.py -q`: **32 passed**.

No blocking defect found for retaining this named-control result. Residual limitations prevent broader claims:

- Parser matches phrases in concatenated full-frame OCR text without spatial-block, quoted-text or negation reasoning. A tutorial merely displaying those words could create a proposal. Current outputs are proposals, not accepted causal facts.
- OCR intent hashes the report via a second read after parsing; concurrent mutation could make its recorded report digest differ from parsed bytes. No mutation was observed in these retained artifacts. Read/hash once would harden custody for adversarial use.
- Frame hashing and final receipt work are outside subprocess timeouts; there is no final deadline assertion. Observed runs are safely below cap, but the code is not a strict whole-process resource sandbox.
- Scoring is one labelled event per case and matches kind/key, not event-time alignment. It must not be reused unchanged for multi-event recordings or precise temporal recall.
- Four controlled clips (one derived from another) with visible held-input overlays are not a blind natural-video/generalization benchmark. Human result anchors remain supplied.

## Execution bindings

| Artifact | SHA256 |
| --- | --- |
| `scripts/observe_watch_input_overlays.py` | `4989ebd3f14cc62b64642ba9238f06252d88f45d48c4772e16b68a83eee32534` |
| `scripts/compare_watch_positive_controls.py` | `63998d2d8669a3846527d37cc2ea6089034292df27ebe3136b86606ea9702d53` |
| `scripts/evaluate_watch_rewind.py` (protocol binding) | `94a1177426a4dcfae56c814ba535b5688f28d6b71a5f24d5e49694c7e9e2731f` |
| Comparison protocol | `8902f3d68012fc79c1c853bcc92e622774f7a4b336eec1c19f8108b6322b04e3` |
| Comparison report | `e60cb8172e79259dcd2a3a850270989e5b69d3b30ea2b06f269991b1c7d4f4e3` |

Source and blind-frame hashes are retained in the unchanged blind-label artifact. This review approves retaining the measured indicator PASS and rewind-graduation FAIL separately; it does not certify a recovered causal instructional procedure or authorize merging.

## Independent custody-guard follow-up (2026-09-19)

Read the changed observer, scorer and regression. The earlier double-read report custody finding is now addressed: observer parses and hashes the same report snapshot; it reads each image once, checks that snapshot's hash, and supplies those exact bytes to Tesseract stdin. Thus a later file replacement cannot substitute different pixels after hash validation. The scorer similarly parses and hashes single snapshots of labels and comparison report. This is not a claim of comprehensive hostile-filesystem isolation.

Reviewer ran the focused overlay tests: **9 passed**, including a regression that replaces both the frame file and report after snapshot acquisition and verifies the original pixel bytes are sent and original report hash is retained. No media or OCR rerun was performed by reviewer.

Inspected the builder's bounded real follow-up `ocr-custody-check-01`: 16 OCR calls, four mouse-down frame proposals, about 1.797 seconds, zero model tokens/GPU calls and zero accepted causal chains. Programmatically compared all four proposal objects with the original case-01 baseline report: exactly equal. These four frame hits still mean one input event. Inspected `SCORE-CUSTODY-CHECK.json`: each arm remains three recovered positive cases, zero false-input cases and one correct negative; graduation remains **FAIL**. Its label and original comparison-report hashes match the previously reviewed artifacts.

The complete eight-arm comparison was executed under the original observer hash above, **not** under the new guard. Only the affected case-01 baseline OCR path was rerun with the guard, plus rescoring of the retained full comparison. Original evidence was preserved and is not retroactively attributed to new code. Final scoped verdict remains **indicator recovery PASS; rewind graduation FAIL**. Other semantic/resource/generalization limitations above remain.

| Follow-up artifact | SHA256 |
| --- | --- |
| Guarded `scripts/observe_watch_input_overlays.py` | `e79324b25b86d65a7857138d8f5743a84164c687271fb6471ec05bcc61f41640` |
| Snapshot `scripts/score_watch_positive_controls.py` | `d2e08219a86f2ce4738d93d6054ab20f3948c5e49f377360c9020d891dc58cf7` |
| `tests/test_watch_input_overlays.py` | `355559fbc22d3dd4e5600ae7e992b4a923a599c5e9c28b7fa462ab4e9d2acff9` |
| `ocr-custody-check-01/report.json` | `321557982ecb3f0359113ec963fc9695af776a9ee0124e2468086fadbe0273ea` |
| `SCORE-CUSTODY-CHECK.json` | `80a8ae4cc7172c861d016fc5e22d3308242f11701acaf76bdb061b60bcdcc364` |

Final commit binding: independently verified that the three guarded source/test files immediately above match both working-file bytes and Git blob bytes at implementation commit `e8d7cc8e447c04bb9bcad3cadb32480a44d6be4a`, with the same listed SHA256 values. This binding does not relabel the original eight-arm execution as guarded-code execution. No tests, media, OCR or inference were rerun for this commit-only check; this appended binding is a report-only follow-up.
