# Design Beast product-value audit — 2026-09-28

## Verdict

Design Beast has a real local source-footage review and editorial export toolkit
in its research branch. It is not yet a demonstrated autonomous recording-to-
reproducible-tutorial product. The tested workflow can preserve actual footage,
measure visual changes, help an operator inspect it, and render their captions.
The automatic explanation path failed in today's environment, and retained
semantic challenges contain substantive errors. No actual customer or novice
participated: willingness to pay, learning improvement and labor savings remain
unmeasured, not zero and not assumed positive.

This is a bounded audit of the primary tutorial mission. It does not certify the
many image/3D/game generation backends, installers or the full repository.

## Decision gates

1. Select a first audience and recruit real creators/learners for a controlled
   value trial. Agents cannot stand in for human usability and demand evidence.
2. Review/integrate accepted Watch branches before presenting the research
   workflow as a feature on main. No integration or merge was performed here.
3. Resolve source-media, bundled font/model/dependency distribution decisions
   before publication. This audit retains raw media privately.

## Fresh end-to-end measurements

Source: existing retained 31-second Blender screen recording (fresh FFprobe
duration31.000000; prior semantic reference spans0–30s); known-case test,
not an unseen holdout. Source hash is recorded in proofs/product-value-audit.
Research checkout: 5f13b24. Main checkout: 1a7f7ab.

| Operation | Observed outcome | Receipt |
|---|---|---|
| Main `beast watch-training prepare` | Printed help, exited 0, created no tutorial workspace: requested command is absent | main-entrypoint.json |
| Research `watch-training prepare` | 62 frames, fresh CPU OCR/measurement, working review workspace; 49.265s | prepare.json; browser.json |
| Chrome review | Real playback, seek to 10.25s, operator caption entry and plan download; zero page errors, no overflow at 390px | browser.json |
| Research caption render | 2.000s H.264 MP4, 1280x848, no audio, 1.166s render | render.json; render-report.json |
| Export playback | Chrome advanced to .411799s, native dimensions/duration correct, media error null | playback.json |
| Complete output decode | FFmpeg returned 0 | decode.json |
| Source fidelity | At source9.5s/output.5s, RGB mean absolute differences .289/.272/.290 out of255; one sampled frame, caption band excluded | source-fidelity.json |
| Plain FFmpeg trim | Same two-second source interval, no captions/evidence workspace; .409s | direct-trim.json |
| Automatic explanation | Exit2, connection refused by local model endpoint; no automatic lesson | automatic.json |
| GPU admission | Admitted, 11,797MiB free; no unrelated process stopped | resource-admission.json |

The caption was supplied by the audit operator using the pre-existing V4 visual
reference: **“The model and annotation become smaller on screen.”** This is a
result observation, not an instruction for reproducing the operation. Its author
is recorded. The automated browser interaction took2.220s; that is NOT human
review time. The plain trim is a cost floor, not feature-equivalent editing or a
competitor benchmark. No ROI percentage follows from these numbers.

## What runs without an agent/model

| Component | Type / dependency | Verdict for tested scope |
|---|---|---|
| Video ingest/frame extraction | Python, FFmpeg/FFprobe | REAL: fresh source processed |
| Pixel/OCR measurements | OpenCV, NumPy, Tesseract | REAL: fresh 62-frame run |
| Source review player | Static HTML, installed Chrome | REAL: playback/seek/edit/download |
| Captioned source rendering | FFmpeg plus operator-authored plan | REAL: actual render/decode/playback |
| Source custody checks | Hashes and interval receipts | REAL: retained bytes and sampled fidelity; not caption truth |
| Resource admission | NVIDIA probe, policy | REAL: fresh admission receipt |
| Automatic visual explanations | Local qwen3-vl through Ollama | UNKNOWN in fresh run: endpoint refused connection |
| Narrated export | Kokoro weights/runtime + reviewed plan | UNKNOWN fresh; historical short result-only success retained |
| Automatic verified procedure recovery | Reasoning + evidence review + target execution | UNKNOWN as a product: historical challenge failures; not delivered by fresh run |
| Studio upload-to-tutorial flow | UI/server routes | Absent in inspected main/research surfaces; no working entrypoint |
| Other Studio/image/3D/game capabilities | Provider/engine dependencies | UNKNOWN in this bounded audit; not retested |

Six executable components passed their bounded T0 checks. This count is not a
product completion percentage: the missing core promise outweighs peripheral
passes. T1 could not complete because the required local model service was
unavailable. T2/operator assistance supplies the explanation and editorial
selection; it does not supply FFmpeg execution or browser playback. No external
model, generated replacement image, paid API call or GPU inference was used.

## Existing semantic evidence, independently inspected

The separate read-only reviewer inspected these source artifacts, not just this
report. Paths refer to the research checkout:

- `proofs/watch-real-video/PROOF.md`: prior sparse challenge0/10 strict grounded
  event recovery, with retained malformed/detail output.
- `proofs/watch-repair/REPAIR-GRADE.md`: dense repair4 supported,4 partial,2 missed;
  false assertions in at least15/61 descriptions. This is reviewed description
  quality, not a newly executed automatic procedure benchmark.
- `proofs/watch-teachability/automatic-review-queue.json`:0 eligible automatic
  units. Pacing/approval gates contain errors; they do not recover missing actions.
- `proofs/watch-teachability/result-narration.json`:2.276s result-only narration,
  “Front orthographic view appears.” It does not tell a novice what to operate.

## Failure-class assessment

| Class | Finding |
|---|---|
| Instructions versus software | Executed intake/review/render are software. General skill compilation still needs explicit reasoning/review, not just running a recipe. |
| Harness dependence | Operator writes the explanation in tested flow; no autonomous authoring credit. |
| Stubs / wiring | Watch training CLI absent on main; no Studio training route found. This is missing integration, not evidence of a broken renderer. |
| Tests versus outcome | Fresh real media/browser/FFmpeg tests used no mocked renderer. Unit pass totals are not customer-value evidence. |
| Silent success | Main CLI returns0 and help for unsupported watch-training. Output existence must be checked. |
| Fault barriers | Automatic path returns2 and retains failure; fresh network failure is not semantic-model failure. |
| Doc/code divergence | WATCH-LEARN declares timeline/v2 while core emitsv3; research capabilities must not be marketed as main features. |
| Environment | FFmpeg discovery required child-local PATH; OCR path Windows-specific; Ollama unavailable; optional ComfyUI offline. |
| Multiple lineages | Main and unmerged research branches differ materially. Report both, do not silently merge. |
| Installed artifact | Source checkout workflow tested, not a clean installer or customer deployment. |
| Secrets/privacy | No keys loaded or raw media uploaded. This is not a complete secret/privacy scan. |
| Confabulation | Historical semantic errors remain; source hashes validate custody, not explanation truth. |
| Source/distribution | Existing audit identifies font, codec/model notices and rights decisions; legal clearance not inferred. |

Harness diagnostic history: initial direct-MP4 navigation waited for
networkidle and timed out. Continuing in the already-loaded video element proved
playback. Continuation initially failed to locate FFmpeg via a child-only PATH;
an explicit executable path resolved this. Neither failure was counted as a
product-quality result. Successful intake/render were not repeated to hide them.
The timeout is described in the continuation intent and session tool output;
byte-exact failed harness revisions and standalone traceback files were not
retained. Current harness scripts include the navigation/executable corrections.
Raw recordings, screenshots, fonts and full private working outputs remain in
`watched/value-audit-01`; only allowlisted JSON receipts accompany this report.

## Is there differentiated value?

Evidence-linked inspection/review is a plausible specialist benefit: original
footage, source clocks, frame references and uncertainty remain inspectable.
Today's execution demonstrates that mechanism, not reduced customer effort.
Ordinary clip extraction alone does not justify the49-second preprocessing cost.

Basic workflow documentation is already served by competitors:
[Tango documents automatic workflow capture](https://help.tango.ai/en/articles/5971654-how-do-i-start-capturing-a-workflow),
and [Guidde documents MP4/WebM upload into video/document workflows](https://help.guidde.com/en/articles/11193962-upload-mp4-videos-to-guidde).
These official pages were checked2026-09-28; neither product was run or scored
here. Do not claim Beast is unique merely because it ingests existing footage.

Recommendation: pursue a creator-assisted, evidence-linked workflow first, but
do not sell automatic tutorial recovery on these results. The central commercial
question is whether evidence assistance saves enough correction/review time while
helping learners complete the task. More encoder or unit-test scores cannot
answer that.

## Predeclared next customer-value gate (proposal, not a result)

Use three consenting creators and six authorized unfamiliar recordings, matched
across manual and Beast-assisted workflows with counterbalanced order. Include
silent actions, brief/occluded controls, delayed results and missing-input cases.
Freeze independent action/result labels before use. Give exported lessons to
separate novices on clean application states; do not coach them through gaps.

Measure complete creation/review/correction/export minutes, false instructions,
critical-step omissions, learner task success, interventions and time. A useful
graduation target is >=30% median creator-time reduction, no critical false
instructions, no lower learner completion, and explicit recapture requests when
input evidence is absent. Small-sample results remain a pilot, not market-wide ROI.
Record willingness to use/pay separately from technical quality.

This requires people, their consent and a target audience; no synthetic agent
rating will be relabeled as customer demand. No invitations or publication were
sent. The audit does not start product repairs automatically.
