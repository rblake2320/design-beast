# Files

## Inspected

- `proofs/ue58-metahuman-live-link/PROOF.md` - current readiness claim boundary.
- `proofs/ue58-metahuman-live-link/COLLECTOR-RUN-20260801A.md` - collector extension status before live capture.
- `skills/ue58-metahuman-live-link-readiness/references/evidence-contract.md` - allowed evidence states.
- `skills/ue58-metahuman-live-link-readiness/references/deformation-gate.md` - fixed v1 thresholds.
- `D:\DEpic GamesUE_5.8\UE_5.8\Engine\Plugins\Experimental\ModelContextProtocol\ModelContextProtocol.uplugin` - official UE 5.8 MCP plugin.
- `D:\DEpic GamesUE_5.8\UE_5.8\Engine\Plugins\Experimental\Toolsets\AllToolsets\AllToolsets.uplugin` - official MCP tool provider.
- `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\Content\BeastMCPProof\BP_MCPGraphProbe.uasset` - MCP-created, compiled, and saved whole-graph proof asset.

## Changed

- `skills/ue58-metahuman-live-link-readiness/assets/BeastEvidenceCollector/Source/BeastEvidenceCollector/Private/BeastEvidenceCollectorLibrary.cpp` - reject stale Live Link bursts before writing evidence.
- `skills/ue58-metahuman-live-link-readiness/scripts/verify_pose_receipts.py` - independently reject stale frame bursts.
- `skills/ue58-metahuman-live-link-readiness/tests/test_verify_pose_receipts.py` - regression test for a frozen frame ID/source time.
- `skills/ue58-metahuman-live-link-readiness/scripts/frame_bound_actor.py` - deterministic front/back camera framing discovered during the run.
- `skills/ue58-metahuman-live-link-readiness/scripts/inspect_bound_actor_render.py` - read-only bound actor component/render inspection.
- `scripts/probe_ue58_mcp.py` - read-only, loopback-only official MCP handshake/discovery/viewport probe.
- `proofs/ue58-official-mcp/PROOF.md` - measured behavior, mutation proof, defects, and claim boundary.

## Generated

- `proofs/ue58-metahuman-live-link/deformation/Run20260801A/` - exact final PNG/JSON receipts plus rejected v1 measurement.
- `session/20260801_210107/` - durable resume state for this work.

## Unrelated Worktree Content To Preserve

- `docs/OPPORTUNITY-LEDGER.md`
- `docs/runbooks/UE58-MCP-BLUEPRINT-PATHBOOK.md`
- `proofs/watch-004-ue58-first-game/`
