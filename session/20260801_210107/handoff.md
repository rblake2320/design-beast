# Handoff

## Resume From Here

Open `C:\Users\techai\brain\design-beast`, checkout `agent/ue58-trusted-pose-collector`, and verify `git status --short`. Read this file, then `session_state.md` and the latest proof documents. The UE project is open in PID 51192 and the official MCP endpoint is `http://127.0.0.1:8000/mcp`. The restart target is `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\MoodBuddyUE58Proof.uproject`, map `/Game/MetaHumanLiveLinkProof`, run `Run20260801A`. Do not require the phone merely to inspect or package existing evidence.

## Next Actions

- Verify hashes under `proofs/ue58-metahuman-live-link/deformation/Run20260801A`.
- Update `PROOF.md` and `COLLECTOR-RUN-20260801A.md` with the final acknowledged capture and rejected automated gate.
- On the next Unreal launch, verify the rebuilt collector DLL loads; rebuild already succeeded and its SHA-256 is recorded in `session_state.md`.
- Run `python scripts/probe_ue58_mcp.py --capture` to re-verify the official MCP after a restart.
- Preserve `/Game/BeastMCPProof/BP_MCPGraphProbe` as the first successful whole-graph MCP proof asset; its current `.uasset` SHA-256 is `47ae2da3a972c906389fe405776a56494185fdb81ff25e0f3fc69d3361dc4868`.
- Expose Beast evidence operations as a custom Toolset or safe wrapper rather than replacing the collector. Official MCP is the control plane; `BeastEvidenceCollector` remains the proof plane.
- Commit and push only scoped files.

## Watch Outs

- Do not claim `DEFORMATION_MEASURED` or `ANIMATION_CONFIRMED`; the v1 neutral-stability gate failed.
- It is accurate to say live facial animation was reproduced and verified by two independent surfaces: changing Live Link curve/frame data and exact hashed rendered images.
- Do not change the v1 threshold retroactively. Design alignment/registration prospectively and test on a new run.
- A stale source may return values while frame ID and source time remain frozen; require at least three distinct frames and at least 0.10 seconds of source-time span.
- Ollama was being relaunched by a stale Bash command from another agent terminal. Verify both the child model processes and their parent launcher when shutting down.
- Preserve unrelated worktree changes listed in `files.md`.
- UE 5.8.1 MCP currently has schema/default defects: fields described as optional can be required, `serverInfo` is blank, `FocusOnActors` did not move the camera for the loaded MetaHuman actor, and annotated capture produced zero labels. Do not claim those paths are reliable yet.
