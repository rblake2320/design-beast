# Session State

- Session: `20260801_210107`
- Repo: `C:\Users\techai\brain\design-beast`
- Branch: `agent/ue58-trusted-pose-collector`
- Started: 2026-08-01 21:01:07 -05:00
- Updated: 2026-08-01 21:01:07 -05:00

## Goal

Build a proof-driven system that learns procedures from tutorials and can execute and verify them in real software. The current proof target is UE 5.8 MetaHuman facial animation driven by iPhone Live Link Face.

## Current Subtask

Preserve the completed Live Link run, harden stale-source detection, document the UE 5.8 official MCP opportunity, and make recovery deterministic after a crash or context compaction.

## Loaded Skills

- `ue58-metahuman-live-link-readiness` - evidence states, cloud/consent boundaries, and deformation gates.
- `computer-use:computer-use` - guarded control of the open Unreal editor.
- `nemo-rl-session-memory` - durable session state and handoff rules.

## Current Status

- UE 5.8.1 project and proof map were saved, then the editor was closed cleanly.
- Ollama, its `llama-server`, and the stale Bash launcher that restarted Ollama were stopped; no Unreal or local-model process remained at the final check.
- Run `Run20260801A` reached `BOUND_READY` with subject `me` and actor `BEAST_Run20260801A`.
- Final collector receipts contain 9, 9, and 10 distinct Live Link frames.
- `CTRL_expressions_jawOpen` median changed from `0.1300153881` to `0.8075177372` (delta `0.6775023490`).
- Exact hashed images visibly show neutral and wide-open-mouth MetaHuman poses.
- Automated `DEFORMATION_MEASURED` promotion remains rejected because neutral crop RMSE was `0.03789118`, above the predeclared `0.01` gate. Do not retroactively lower the threshold.
- A frozen-source attempt exposed missing stale-frame detection. Native collection and offline verification reject fewer than three distinct frames or less than 0.10 seconds of source-time span. Python tests pass, and the project plugin rebuilt successfully; DLL SHA-256 is `b7d781919963ce649f31a40e950e0956d5578b724162a0d1c86f3cb1f1e1a7c5`.
- UE 5.8 official Unreal MCP exists locally as `ModelContextProtocol`, with tools supplied by `AllToolsets`; neither was enabled in the proof project when checked.

## Plan

- [ ] Update proof documents and add a visual-review record tied to the three final image hashes.
- [x] Rebuild `BeastEvidenceCollector` with stale-frame rejection in the saved disposable project.
- [ ] Verify the rebuilt plugin loads on the next editor launch.
- [ ] Add official UE 5.8 MCP as a broad control plane while retaining the evidence collector as the proof plane.
- [ ] Commit and push only scoped Live Link/session files; preserve unrelated user/agent worktree changes.

## Assumptions

- The final three receipts are immutable source evidence. Verify their SHA-256 values before relying on them.
- `/Game/MetaHumanLiveLinkProof` is the restart map and `Run20260801A` is the evidence run.

## Blockers

- Automatic numerical promotion needs a prospectively designed, pose-aligned capture method; the present run must remain rejected by the v1 RMSE gate.
