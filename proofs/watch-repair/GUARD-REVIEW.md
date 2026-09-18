# Independent guard and diagnostic review

Reviewer `/root/inspection_review`, 2026-09-18. Read-only source/artifact review; only this independent review artifact written. No inference, OCR rerun, source edits or merge. Earlier semantic grades and frozen references remain unchanged.

## Disposition

**No remaining blocking finding in the narrowly claimed byte-binding, UTF-8 transport, and explicit clock repairs reviewed here.** This is not approval of semantic watching quality, hostile-process isolation, complete original-source lineage, or autonomous event recovery. The original semantic challenge remains failed and the held-out grade remains partial.

## Independently executed tests

- `python -m pytest watch/tests watch/evidence/tests -q`: **106 passed, 1 skipped**.
- `python -m pytest tests/test_watch_gate_injection.py tests/test_validate_watch_procedure.py -q`: **18 passed**.
- Combined scope: **124 passed, 1 skipped**. The skip is the previously declared Windows symlink-privilege case. No provider/GPU tests run.
- One preceding invocation named nonexistent `scripts/tests/test_watch_real_challenge.py`; pytest ran no tests for that invocation. It is not counted as a passing run.

## Guard findings

1. `observe_frame` reads image bytes once, hashes those bytes, and submits the same bytes. The new regression replaces the disk file during admission and checks the actual base64 request payload: it remains the original bytes. Timestamp/hash binding is code-owned, not model-generated.
2. A mismatched model digest is rejected before inference, with a regression asserting only the tag lookup occurred. Actual options are retained in intent. This is a preflight consistency check, not isolation against a malicious daemon or concurrent tag replacement inside the model service.
3. `observe_ocr` hashes input bytes and passes those exact bytes through Tesseract stdin. Output is decoded as strict UTF-8; empty, non-TSV and invalid-UTF-8 responses fail. Regression covers non-ASCII text and disk replacement after the verified read. TSV prefix checking establishes transport shape, not word accuracy or full semantic TSV validation.
4. `pixel_change` now hashes and decodes the same in-memory byte buffers when expected hashes are supplied. The dense runner supplies both hashes. This closes the prior hash-then-reopen mismatch at this call site.
5. New transition records explicitly label clip-relative milliseconds and separately carry original-source milliseconds/hash. Old reports are not retroactively rewritten.
6. The runner still emits unverified candidates and zero procedure promotions. No model probability or descriptive text was converted automatically into accepted evidence.

Remaining explicit limits: `source.json` original media identity/offset is trusted rather than independently pinned; generic pair-observer callers may omit expected pixel hashes; source lineage and resistance to malicious filesystem/model-service actors are not established. A 61-frame report is accounting, not proof of comprehension.

Reviewed working-file SHA256 values:

- `watch/ocr_observer.py`: `940a93ebfa8a7ccf41aaa1c3fc0d43c34ddf8ce40e35dd2439ff17c2af0f4c16`
- `watch/frame_observer.py`: `4ac95f76da82cbd98e9c72f92ad5cc90ba2fa67bf8c0a30d67619a17e3c568cc`
- `watch/temporal_observer.py`: `5d7bc30dca61cae1b8c4e09fce30d98c786ed11799729968535490af137de012`
- `scripts/watch_dense_repair.py`: `01040ab3d60df8ad54a14935b7ac965cbc406b9ed195fd8ac5ac36e24cff5ee3`

## Separate OCR recovery evidence

Inspected `dense-ocr-recovery-01/intent.json`, its report, and all **61 individual recovery receipts**. All contain a non-null UTF-8 TSV string with the expected header and the corresponding original frame hash. The original `dense-instruct-01` still contains **17 null TSV receipts**; its report SHA256 is still `2f49e8fbe17dd862bf8a20d84957f957b63ae043e98f92cf4748ebbbcd53b00e`.

This supports a separately retained UTF-8 OCR transport recovery, preserving failed evidence. It does not change the original inference run's grade, prove every OCR token correct, or repair model descriptions. The recovery explicitly records zero vision calls and zero semantic acceptances.

## Four-crop diagnostic: region-probe-01

Directly viewed all four crop PNGs and read their results. These are selected failed-case diagnostics, not a blind held-out evaluation.

| Crop | Observed result | Disposition |
|---|---|---|
| frame-000-top-left | Still says Sculpting mode while Object Mode is visibly in the crop. | Failed mode distinction. |
| frame-017-viewport | Calls blue mark a vertical line and identifies pencil cursor without inventing a sculpt stroke. | Useful bounded improvement; no annotation action or temporal recovery proven. |
| frame-023-viewport | Calls visible eraser a pencil and implies editing mode. | Failed cursor distinction. |
| frame-034-center | Describes three panels and their contents, but calls them split-screen/multiple windows rather than recognizing the task switcher. | Partial content description, not recovery of V9. |

Cropping does not resolve the whole error class. At least two clear false state claims remain (mode and eraser), plus incomplete switcher interpretation. No event automatically recovered or accepted.

## CPU 27B two-call diagnostic

Both `cpu-27b-probe-01/frame-000/result.json` and `frame-023/result.json` completed before this review was finalized. Read both results; no aggregate report was present. **Disposition: failed to resolve the selected mode/cursor errors.**

The completed frame-000 result lists both Sculpting and Object Mode without asserting Sculpting mode active, and correctly describes the pencil/profile view. It nevertheless says the software version is not visible although the lower-right source frame displays 5.0.1, and refers to sculpting-brush settings as underdetermined. Its retained elapsed time is approximately **185.09 seconds**. One selected-frame description is neither semantic closure nor evidence of practical throughput. No inference was rerun by this reviewer.

Frame-023 explicitly says `in Sculpt mode` despite the visible Object Mode label and calls the eraser a brush cursor. It does correctly list the version 5.0.1. Its retained elapsed time is approximately **193.66 seconds**. Combined inference elapsed time is approximately **378.74 seconds for two frames**. The larger CPU model did not close the known semantic failure; at least one false statement remains in each selected frame result. This diagnostic does not license a full-video, autonomous-event or generalized-capability claim.
