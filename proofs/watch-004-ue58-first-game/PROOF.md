# Beast Watch proof 004 — Unreal Engine 5.8 movement slice

## Result

Beast Watch ingested the 75:29 Unreal University Asteroids course into 340
adaptive frames and 3,858 timestamped caption segments. OpenCLIP/Faiss indexed
246 unique frames. A confidence-triggered dense rewatch added five 31-frame
windows around the movement procedure (12:40, 13:35, 15:05, 17:20, 20:35).

The bounded skill below compiles the Enhanced Input movement slice: create
`IMC_Asteroids` and `IA_Move`, set `Axis2D`, apply Swizzle/Negate modifiers,
install the mapping context in `BeginPlay`, split X/Y, and route them through
`Add Movement Input`. The frame evidence confirms the UI state while captions
provide the ordered operations.

This is evidence-to-procedure compilation, not proof that a new UE project was
created and played by the compiled skill. UE execution, asset import, and
behavioral movement checks remain not executed in this proof.

## Evidence boundary

- structural: timeline, captions, frame files, dense seeks, and compiled skill
  are present;
- behavioral: Beast Watch tests and skill package validation can pass locally;
- Unreal behavioral/visual: not executed against a disposable UE5.8 project.

The course also exposes a reusable compiler opportunity: convert chapters into
a dependency graph of named Unreal assets, prerequisites, ordered actions, and
compile/play assertions. This is an experiment hypothesis, not a novelty claim.

## Next proof

Generate a disposable UE5.8 project, create the named input assets and player
logic, then run an automated movement smoke test with retained logs and before /
after screenshots. Do not mark the skill executed until those artifacts exist.

**UPDATE 2026-08-01: executed — see `EXECUTION-PROOF.md` in this directory.**
The skill's procedure was run end-to-end against live UE 5.8 (headless BeastLab
via MCP): compile clean, mapping context verified active at runtime (UE log),
signed-axis movement in all four directions, and orient-rotation ±90/180/0
confirmed after the step-7 settings. Boundary: input injected at the action
layer (no key-level injection exists in Python); key→vector modifier layer
verified structurally. Reproduction recipe:
`docs/runbooks/UE58-MCP-BLUEPRINT-PATHBOOK.md`.
