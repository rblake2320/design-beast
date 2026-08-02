# Timeline

## 2026-08-01 21:01 -05:00

- Reopened the saved UE 5.8 proof map and connected iPhone Live Link Face subject `me` through the native source bridge.
- Framed the bound MetaHuman from the front and collected several controlled and rejected attempts without deleting evidence.
- Final acknowledged sequence captured two neutral receipts and one expression receipt with changing source frame IDs.
- Observed jaw median delta `0.6775023490`; exact rendered images visibly changed on the mouth/jaw region.
- Ran the predeclared verifier. Source delta and continuity passed; neutral stability and rendered-deformation ratio failed because the screenshots were not pose-aligned tightly enough.
- Discovered a separate frozen-source attempt where all samples reused frame ID `42537`. Added native and offline stale-frame rejection and a regression test (`3 passed`).
- Reviewed Smart Poly video `OiFtnBj1P9o` and its linked setup video. Confirmed from Epic UE 5.8 documentation that official Unreal MCP is experimental, embedded in-editor, uses local HTTP, has plugin ID `ModelContextProtocol`, and relies on `AllToolsets`.
- Saved the project and proof assets through Unreal remote execution, then closed Unreal cleanly.
- Stopped Ollama and `llama-server`. Traced an automatic relaunch to Bash PID 77504 running an old Claude shell command and stopped that exact launcher.
- Synchronized the single patched collector C++ source file into the disposable project and rebuilt `MoodBuddyUE58ProofEditor` successfully. New collector DLL SHA-256: `b7d781919963ce649f31a40e950e0956d5578b724162a0d1c86f3cb1f1e1a7c5`.

## 2026-08-02 01:00 -05:00

- Enabled Epic's official `ModelContextProtocol` and `AllToolsets` plugins in the UE 5.8 disposable project and configured loopback auto-start at `127.0.0.1:8000/mcp`.
- Corrected a quoted-project-path launch failure, reopened `/Game/MetaHumanLiveLinkProof`, and verified the MCP listener belongs to the active Unreal Editor PID 51192.
- Completed a real MCP `initialize` handshake, tool discovery, and live `get_current_level` dispatch. Measured 55 toolsets and 20 native Agent Skills.
- Confirmed the Blueprint toolset includes a whole-graph S-expression DSL and the native Blueprint skill explicitly recommends it over repeated node edits.
- Created `/Game/BeastMCPProof/BP_MCPGraphProbe`, discovered exact node types, wrote its BeginPlay/PrintString graph in one DSL call, read the graph back, compiled with warnings as errors, and saved it. Asset SHA-256: `47ae2da3a972c906389fe405776a56494185fdb81ff25e0f3fc69d3361dc4868`.
- Captured valid viewport PNG bytes and camera metadata in memory. Actor annotations remained empty despite one visible actor, so label grounding remains unproven.
- Added a read-only reproducible probe and a proof report under `scripts/probe_ue58_mcp.py` and `proofs/ue58-official-mcp/PROOF.md`.
