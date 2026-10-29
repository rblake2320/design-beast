# Video-to-verified-capability consolidation proposal (2026-10-28)

This is an integration plan, not a claim that generalized video execution works.
Follow BEAST.md and reuse Watch rather than introducing a second watcher.

## Current inventory (do not rebuild)

- Watch v3: adaptive sampling, source timestamps, ingestion hashes, source-linked transcript, seek/rewind.
- Watch perception: spatial pixel/OCR tracks, OmniParser UI detector, V-JEPA 2 temporal embedding and fuse lane, currently experimental and bounded.
- Video Procedure Learning: evidence-to-procedure skill contract and human gate.
- Beast Packs: capability evidence levels, versioning and resource/recovery controls.
- UE execution proof: live-engine validation in a specific tested environment.

## New integration seam

`scripts/watch_temporal_bridge.py` converts existing Watch v3 frames into an ordered, hash-grounded visual comparison request list. It is strictly **not** a semantic-event recognizer or click-inference model. Source frames without ingestion hashes are rejected; gaps >3 seconds demand reinspection. Any semantic observation remains unverified pending independent checks.

Usage:
```powershell
python scripts/watch_temporal_bridge.py watched/tutorial --output watched/tutorial/temporal-review.json
python -m unittest tests.test_watch_temporal_bridge -v
```
The output is create-only. Future integration should consume this contract in `watch-fuse` rather than another parallel ingestion pipeline.

## Next implementation gates

1. **Canonical evidence**: reconcile existing typed, spatial, audio, video and receipt schemas with one versioned event contract. Preserve observed/inferred/uncertain versus reproduced/measured/verified/generalized as orthogonal dimensions (assertion confidence is not execution evidence).
2. **Native-rate escalation**: compare temporal pair coverage against independently labeled real GUI screen recordings. Escalate from adaptive samples to short native-frame-rate clips only on ambiguous transitions; track real costs and missed events.
3. **Semantic adjudication**: require verified UI control identity, before/after state, timestamps and evidence citations. Run two independent observers when confusion risk is high; abstain on disagreement rather than forcing consensus.
4. **Task graph**: compile verified observations to typed preconditions, permitted action, postcondition, rollback, version and dependency requirements. Never infer physical keypresses from a changed text field alone.
5. **Execution adapters**: reuse existing MCP/CLI/PowerShell routes and resource guard; add isolated browser/code environments with precise permissions and checkpointed idempotent action semantics. All external, paid, destructive and credential actions need explicit authorization.
6. **Outcome comparator**: independent executors verify behavior and visual state; compile evidence bundle and immutable capability receipt. Repair targets the earliest disproven assumption.
7. **Unseen benchmark**: freeze rubric, task set, labels and source hashes before model selection. Include transcript-only, fixed-frame, active-reinspect and semantic-event variants at matched budgets. Include falsification tasks and negative results.
8. **Reusable skills**: package only passed tasks in versioned Beast Packs; compare transfer on different applications before elevating to generalized.
9. **Platform experience**: add a single job UI with observe/reinspect/compile/execute/prove status, budgets, resource admission, approvals, exceptions and direct links to evidence. Do not stack separate dashboards.

## Research directions to evaluate, not install blindly

- Google Watch & Learn and Video2GUI: inverse-dynamics action inference and large video-derived GUI trajectories. Compare against Beast on the same blind task rubric.
- CUA-Suite: 30-FPS demonstrations, spatial/cursor ground truth for temporal perception benchmarking (inspect license and dataset terms).
- Microsoft UFO3: cross-device task orchestration ideas, not necessarily a dependency.
- Gemini agentic video: dynamic time navigation as an optional authorized provider adapter; compare with local Watch on a controlled budget.
- OSWorld-style desktop evaluation with frozen environments.
- Causal intervention tests: show indistinguishable visual outcomes caused by different actions, require uncertainty rather than fabricated cause.
- Skill drift monitoring: automatically mark capabilities needing re-verification when applications, plugins or UI structures change.
- Self-improving active inspection: learn **where** to spend inspection budget from accepted evidence, without allowing model scoring to rewrite proof history.

## Product simplification rule

One evidence graph, one job/state machine, one execution broker, one capability registry, one recovery/evidence ledger. Existing specialist tools stay behind adapters. Every new model must prove incremental value on frozen benchmarks before promotion.

Do not mistake dependency installation or successful unit tests for working visual interpretation.
