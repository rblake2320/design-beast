# Evidence contract

## States

| State | Required evidence | Forbidden inference |
|---|---|---|
| `PREFLIGHT_READY` | UE 5.8, valid MetaHuman Character asset, required local content | Rigged or assembled |
| `ASSEMBLY_ELIGIBLE` | Full rig requested, all eight texture-source fields configured/read back as 2K, high-resolution textures present, `can_build_meta_human=true`; blendshape rig and downloaded pixel dimensions remain unverified unless separately observed | Full blendshape rig or eight downloaded 2K files proven; assembly succeeded |
| `ASSEMBLY_CANDIDATE` | Fresh run-scoped assets, one newly discovered generated Blueprint, saved assets, clean-log review still required | Assembly accepted or Live Link drives it |
| `ADOPTED_LOCAL_ASSEMBLY` | A reviewed local UE 5.8 Blueprint duplicated under the fresh run, with its source Blueprint and reused prior dependencies recorded | Rebuilt in this run or dependency-isolated |
| `ASSEMBLED` | `ASSEMBLY_CANDIDATE` receipt plus explicit user confirmation of a clean assembly-log review | Live Link drives it |
| `BOUND_READY` | Chained reviewed-assembly/spawn receipt, actor property readback, and subject present, enabled, and `CONNECTED` through the UE Live Link API | Visible deformation |
| `DEFORMATION_CANDIDATE` | Every numerical gate in `deformation-gate.md` passes using user-supplied values and images | Animation confirmed |
| `DEFORMATION_MEASURED` | Three collector-issued receipts from one run/actor/view, image hashes, raw curve bursts, and all numerical thresholds pass | Intended facial motion or production readiness |
| `ANIMATION_CONFIRMED` | `DEFORMATION_MEASURED` plus visual-region review tied to the exact three image hashes | Production integration or generalization to other characters |

## Required language

- Use **observed** for a UI/log state seen once.
- Use **reproduced** only after a fresh rerun reaches the same state.
- Use **measured** only with a named metric and threshold.
- Use **verified** only when independent evidence surfaces agree.
- Do not use **novel** without a recorded prior-art search.

## Version and path discipline

- Record the complete engine version from `SystemLibrary.get_engine_version()`.
- Reject non-5.8 engines.
- Discover generated assets through Asset Registry/listing results.
- Keep disposable build output under a run-scoped `/Game/...` root.
- Require `BEAST_ALLOWED_UPROJECT` to match the active project exactly, explicit user confirmation that it is disposable, a project name containing `Proof`, `Sandbox`, or `Disposable`, and a fresh `BEAST_RUN_ID` whose content root and preflight receipt do not already exist.
- Persist run-scoped receipts under `Saved/BeastProof/<run-id>` and require downstream steps to consume the expected prior state.
- Do not modify Mood Buddy production content during a readiness proof.

## Human and external boundaries

Epic authentication, terms, face-mesh consent, and account authorization remain human actions. Cloud autorigging and texture synthesis require two explicit opt-in environment flags. A script must stop rather than create implied consent.
