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
Live Link Face source request, `BOUND_READY`, and the locked proof camera.

## Live Link boundary

The actor readback currently proves:

- `LiveLinkSubject = iPhone`
- `UseLiveLink = true`
- the configured actor and level are saved
- the phone responds at `192.168.12.238`
- the UE-side native Live Link Face source accepted the connection request

After the phone returned at `192.168.12.238:14785`, refreshing only the native
Live Link Face source changed the readback to an enabled `iPhone` subject with
`LiveLinkSubjectState.CONNECTED`. The actor is therefore `BOUND_READY`.

The first trusted three-pose attempt was rejected before measurement because
the editor camera changed between captures; one screenshot omitted Marcus
entirely. All six failed artifacts were preserved under
`failed-captures/view-drift-20260802-0730/`. The capture path now writes one
run-scoped `PROOF_CAMERA_LOCKED` receipt, uses the assembled MetaHuman's local
right axis for a frontal view, and restores that exact transform before every
pose request. A corrected 80 cm frontal camera is saved.

After resume, a replacement neutral/neutral/expression sequence produced three
collector-issued receipts, 10 distinct expression source frames, and exact
hashed viewport images. Visual review shows a closed mouth in both neutral
images and a wide-open mouth with displaced jaw in the expression image. The
independent jaw-control median changed from `0.0783184059` neutral to
`0.8174888790` expression, a delta of `0.7391704731`.

This reproduces the same practical evidence class as the earlier AdaProof run:
visible intended facial motion plus a matching independent source signal. The
stricter automated state remains `MEASUREMENT_REJECTED`, because neutral crop
RMSE `0.06486526` exceeds the predeclared `0.01` threshold. AdaProof also failed
that stricter threshold. The threshold was not changed after seeing Marcus.

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
6. Repeated deformation screenshots could silently use different editor camera
   transforms. The trusted verifier rejected the run; the collector workflow
   now locks and restores one run-scoped frontal proof camera before every pose.

## Claim boundary

Proven: deterministic male Character asset, user-authorized cloud output,
successful UE 5.8 assembly, generated Blueprint existence, saved level actor,
isolated visual render, exact transform, connected Live Link subject, actor
binding, crash-resumable evidence receipts, visible intended mouth/jaw motion,
and a matching independent Live Link curve change.

Not yet proven: the stricter `DEFORMATION_MEASURED` state, production
lighting/appearance, or an end-to-end Mood Buddy avatar.

## Resume point

Do not repeat cloud preparation, assembly, spawning, binding, or this visual
reproduction. The next measurement experiment should address rigid face
alignment and background exclusion prospectively, then use a fresh run and
predeclared method. Do not recalculate these captured frames with a post-hoc
threshold merely to promote them.
