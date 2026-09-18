# Real-video deep-end challenge: FAIL

The current Watch + local Qwen3-VL 8B path did **not** meet the requested visual
recovery standard. This is not a synthetic result and not an efficiency success.

## Frozen task

Source: https://www.youtube.com/watch?v=qy-wwP-b9HY, retained Blender character
course, source 30:00–30:30. The interval was chosen before any frame inspection;
it was not replaced after seeing the content. Audio stripped; transcript, title,
reference labels and reviewer notes were never sent to the model.

Source original SHA256: `af73daeaa165ed1fe05ef1d772a126cdb8c28d2595c44a43912fb484d4a5a0e4`.
Silent local excerpt SHA256: `5b9b1f739bcb0c6ab8d802a76e3e72ddb8210b424eba1d703f9c2a7e1e8c8917`.
The original and excerpt are retained locally, not republished. `run-01/export.json`
records excerpt location and hashes for exported receipts and review frames.

Model: `qwen3-vl:8b`, digest
`901cae73216286ea8c5aba8b46d307ff7188f737285ec500c795a12f05225d28`.
Runtime: Ollama 0.32.14, RTX5090, fresh Beast resource admission before inference.
Only the Qwen model loaded by this experiment was released; no user process killed.
Provider spend USD0. No Jev/SemIf model execution.

## Measured outcome

- Blind independent agent reference: 10 visible events, frozen in `596be81` before
  answer grading. This is an independent sampled visual reference, not infallible
  human ground truth; see `BLIND-REFERENCE.md`.
- Strict correctly grounded recovery: **0/10**. One coarse slide-transition mention
  corresponds to the subject of a real event but cites the wrong after-frame.
- Complete change records: **1**, incorrectly grounded records **1/1**. The model
  says frame index1 is a full-screen slide. Index1 is actually Blender at clip10s;
  the slide appears at indices2/3. Perception and transition confidence were1.0.
- Detail output: **rejected**. It repeated descriptions until the1800-token cap,
  returned `done_reason=length`, and contained incomplete JSON. No detail accepted.
- Overview input: 0,10,20,30s. Deterministic reinspection chose2–8s; Watch retained
  25 frames but the observer consumed only2,4,6,8s. This evidence-use/coverage gap
  missed short events. Total requested extraction charge29 frames; model saw8.
- Independent reviewer used61 separate reference frames; those were not model inputs.
- Zero procedure promotions. False model observation is **not** false acceptance
  by Watch: the complete response remained `unverified_visual_observations`.

## Failed transport and bounded repair

Initial schema-format request returnedHTTP400. A diagnostic admission was denied
while the experiment's newly loaded model occupiedVRAM. After releasing that own
model, diagnostic HTTP400 identified unsupported sampler grammar. Both failures
are retained. Switching to JSON mode permitted one completion, whose exact JSON
was in `thinking`, not `response`; parsing that already-returned JSON was a transport
repair, not a new inference. The detail inference then failed the fixed output cap.

Totals: four HTTP generation attempts, two rejected before a completion and two
completed generations; one additional admission denial produced no model request.
No output-budget increase, semantic-prompt retuning or source-window substitution
was used to turn the challenge into a pass. Post-run parser regressions explicitly
reject length-limited answers even when parseable. They do not alter this outcome.

## Escape reason and next concrete repair

The earlier control test validated extraction/custody, not the real model transport
or temporal grounding. The new observer initially bypassed the already-known
installed-adapter grammar/envelope constraints. More importantly, four-frame text
generation did not reliably bind claims to pixels, and most newly extracted detail
frames were never interpreted. A probability of1.0 did not correct either defect.

Next implementation target: reuse the existing hardened local-model adapter,
frame-addressed bounded observations, temporal coverage across extracted frames,
and independent before/after checks before accepting a transition. Evaluate repairs
as new versions against this retained FAIL and a new unseen case; do not rewrite it.

Validation: `tests.xml` contains106 passes and one Windows symlink-privilege skip.
Those tests prove code boundaries, not successful watching. `INDEPENDENT-GRADE.md`
contains the independent visual findings. PR33's original reviewed head is unchanged;
this experiment is on its own follow-up branch and does not claim that review.
