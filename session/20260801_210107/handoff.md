# Handoff

## Resume From Here

Open `C:\Users\techai\brain\design-beast`, checkout `agent/ue58-trusted-pose-collector`, and verify `git status --short`. Read this file, then `session_state.md` and the latest proof documents. The UE project was saved and closed cleanly. The restart target is `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\MoodBuddyUE58Proof.uproject`, map `/Game/MetaHumanLiveLinkProof`, run `Run20260801A`. Do not require the phone merely to inspect or package existing evidence.

## Next Actions

- Verify hashes under `proofs/ue58-metahuman-live-link/deformation/Run20260801A`.
- Update `PROOF.md` and `COLLECTOR-RUN-20260801A.md` with the final acknowledged capture and rejected automated gate.
- On the next Unreal launch, verify the rebuilt collector DLL loads; rebuild already succeeded and its SHA-256 is recorded in `session_state.md`.
- Consider enabling official UE 5.8 `ModelContextProtocol` plus `AllToolsets` in a disposable copy, then expose Beast evidence operations as a custom Toolset rather than replacing the collector.
- Commit and push only scoped files.

## Watch Outs

- Do not claim `DEFORMATION_MEASURED` or `ANIMATION_CONFIRMED`; the v1 neutral-stability gate failed.
- It is accurate to say live facial animation was reproduced and verified by two independent surfaces: changing Live Link curve/frame data and exact hashed rendered images.
- Do not change the v1 threshold retroactively. Design alignment/registration prospectively and test on a new run.
- A stale source may return values while frame ID and source time remain frozen; require at least three distinct frames and at least 0.10 seconds of source-time span.
- Ollama was being relaunched by a stale Bash command from another agent terminal. Verify both the child model processes and their parent launcher when shutting down.
- Preserve unrelated worktree changes listed in `files.md`.
