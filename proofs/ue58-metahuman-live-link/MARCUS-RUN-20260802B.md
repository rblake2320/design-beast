# MarcusProof Run20260802MaleB

Date: 2026-08-02  
Engine: Unreal Engine 5.8.1  
Project: `MoodBuddyUE58Proof` (disposable proof project)  
Map: `/Game/MetaHumanLiveLinkProof`

## Result

The fresh masculine MetaHuman Character was cloud-rigged and its texture
sources were downloaded by the user in Epic's UI. Unreal's assembly log then
reported `MetaHuman Character assembly succeeded`. The generated Blueprint was
adopted into the fresh run root, spawned through Epic's official Unreal MCP,
saved, selected, and visually inspected in the level.

The first assembly ran for approximately 47 seconds. The later shader summary
reported 519 completed jobs, 100% complete, with 36.31% job-cache hits and
26.52% DDC hits. This is an observed run on an RTX 5090 system, not a generalized
hardware benchmark; cloud latency, CPU texture compression, disk, and shader
workers also affect elapsed time.

Visual inspection found two older proof actors overlapping Marcus at the world
origin. Marcus was moved to `(300, 0, 0)` without deleting the older evidence.
The isolated readback showed one rendered male actor with skin, body, clothing,
hair components, and no overlapping second face/body.

## Durable evidence

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Character asset | 7,046,866 | `050DED1485541C67DC8C20D73416E884702A81FBB5B20AF8A25EC81D3A67E7C4` |
| Adopted assembled Blueprint | 199,022 | `A08A979D33E4FB3EA44E3DD1CA3A4F4F02CBC28776EB5F2F2FE97E3276088CED` |
| Saved World Partition external actor | 121,216 | `ADFCF02F3E91AECF79DB1742D2387E48ABF0C583717CA347CEB8B452589178A5` |

Run receipts are under:

`Saved/BeastProof/Run20260802MaleB/`

They preserve preflight, reconciled cloud output, assembly adoption, spawn,
Live Link Face source request, and the partial binding checkpoint.

## Live Link boundary

The actor readback currently proves:

- `LiveLinkSubject = iPhone`
- `UseLiveLink = true`
- the configured actor and level are saved
- the phone responds at `192.168.12.238`
- the UE-side native Live Link Face source accepted the connection request

Unreal currently reports no enabled subject and
`LiveLinkSubjectState.INVALID_OR_DISABLED`. Therefore the honest current state
is `BINDING_CONFIGURED`, not `BOUND_READY`, and facial animation is not claimed.
The checkpoint is saved so restoring the phone stream does not require repeating
character creation, cloud preparation, assembly, or spawning.

## Defects converted into fixes

1. Epic's Python remote-execution node temporarily disappeared while official
   Unreal MCP remained healthy. The actor was spawned through official MCP.
2. Epic's MCP `save_actor` failed on the new World Partition external-actor path.
   Normal editor save succeeded and the external actor file was verified.
3. The original spawn script attempted to save every dirty package and failed
   on an unrelated shared ARKit mapping dependency. It now saves only the proof
   level through `LevelEditorSubsystem`.
4. Post-assembly MetaHuman Character data is unloaded, so repeating a
   pre-assembly `can_build` test creates a false-looking failure. Reconciliation
   now verifies the generated Blueprint in the post-assembly state.
5. Failed connected-state readback formerly lost useful partial state. Binding
   now saves the actor and writes `binding-configured.json` before stopping at
   the connected gate.

## Claim boundary

Proven: deterministic male Character asset, user-authorized cloud output,
successful UE 5.8 assembly, generated Blueprint existence, saved level actor,
isolated visual render, exact transform, Live Link property configuration, and
crash-resumable evidence receipts.

Not yet proven: a connected Live Link subject for this run, measured facial
deformation, production lighting/appearance, or an end-to-end Mood Buddy avatar.
