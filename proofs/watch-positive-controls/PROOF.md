# Positive-control outcome — 2026-09-19

## Tested results

| Endpoint | Baseline | Rewind | Verdict |
|---|---:|---:|---|
| Visible input-indicator cases recovered | 3/3 | 3/3 | PASS for both |
| Negative cases with invented input | 0/1 | 0/1 | PASS for both |
| Wrong input kind/key cases | 0 | 0 | PASS on emitted observations |
| More positive cases recovered than baseline | — | tie | FAIL: rewind graduation |

`SCORE.json` is generated against the independently frozen `BLIND-LABELS.json`.
The labels were sealed before scheduling; recovery receives videos and reviewed
result anchors, not labels, DOM state or private telemetry. No source-control
answer is embedded in the scheduler. The OCR observer is explicitly designed to
read visible input indicators, not arbitrary UI clicks.

## Real recordings and audit

`capture/` contains the actual25FPS1280x720 browser videos, sparse source review
frames, source hashes and withheld-until-audit input logs. Cases cover mouse,
keyboard-only, delayed result and a trim excluding the initiating mouse input.
The test app renders pointer/down indicators from actual DOM events. It is a
controlled fixture, not a natural third-party recording or60FPSnativeWGC capture.

`comparison/` retains the two Watch schedules, extracted frames and actual OCR
outputs for all four cases. Same per-arm maxima16requests/decodes/OCRcalls,
0modeltokens,60seconds sampling plus60seconds OCR. Repeated frames are not counted
as distinct recovered actions. No causal chains are automatically accepted.

The original Blender source-evidence failure is preserved unchanged in
`proofs/watch-rewind-outcome/`; it was not used to tune the new positive clips.
Current independent audit is in `INDEPENDENT-REVIEW.md` when retained.

## Software verification

Doctor33OK,1optionalComfyUIoffline,0fails; corevalidateOK.
Full local suite414passed,1Windows symlink skip,7liveGPU deselected.
Nine new regressions cover explicit positive markers, result/motion/UP negatives
and source/report mutation after the checked byte snapshot. These unit tests are separate from the actual browser/FFmpeg/OCR
experiment. JavaScript Playwright Test was unavailable locally; recording used
the installed Python Playwright API with an isolated headless Chrome context.

After the full comparison, independent review identified an OCR parse/hash reread
gap. The observer now parses/hashes each report snapshot once and passes the exact
hashed image bytes to Tesseract stdin. The same snapshot rule was applied to the
scorer. `ocr-custody-check-01/` retains the affected real mouse-case verification:
four mouse-indicator frames, same as before. `SCORE-CUSTODY-CHECK.json` reproduces
the original3/3tie. The full comparison's original code hashes remain unchanged;
it is not relabeled as a run of later guard code.

PR41 recheck: head41adb047eb3cbe97aa229e26247e33733e9a5469, Python and TypeScript
CI successful, open/draft/unmerged. No token scopes were changed. No API charges,
GPU model calls, TTS, or external application actions occurred in this experiment.
