# Trusted collector extension — Run20260801A

Run date: 2026-08-01 (America/Chicago)

## Current result

The native `BeastEvidenceCollector` source plugin compiled against UE 5.8.1, was installed into the disposable `MoodBuddyUE58Proof` project, and was loaded by the running editor. A fresh receipt chain reached `BOUND_READY`, then an acknowledged neutral/neutral/expression sequence produced three trusted receipts and exact hashed viewport images.

The run reproduced visible Live Link facial animation across two independent evidence surfaces: changing UE source frames/curve values and changed pixels on the intended MetaHuman mouth/jaw. It does not satisfy the stricter v1 `DEFORMATION_MEASURED` state because neutral image stability failed, and it does not prove a fresh cloud build or production integration.

## Runtime evidence

- Engine: `5.8.1-56057345`
- Project: `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\MoodBuddyUE58Proof.uproject`
- Run: `Run20260801A`
- Plugin DLL SHA-256: `0E6B24EA504F4F7A84E07AD0654617FB888390FD264C8DD997D3BBDAC961C58C`
- Saved map: `/Game/MetaHumanLiveLinkProof`
- Fresh Blueprint: `/Game/MoodBuddyProof/Run20260801A/MetaHumans/AdaProof/BP_AdaProof`
- Spawned label: `BEAST_Run20260801A`

The editor log contains both:

```text
LogPluginManager: Mounting Project plugin BeastEvidenceCollector
LogModuleManager: InternalLoadLibrary: 'BeastEvidenceCollector' (.../UnrealEditor-BeastEvidenceCollector.dll)
```

## Receipt chain

1. `preflight.json` reports `PREFLIGHT_READY`, high-resolution textures present, `can_build=false`, and no external work.
2. `assembly-candidate.json` reports `ADOPTED_LOCAL_UE58_BLUEPRINT`, identifies the Run001 source Blueprint, and states that prior local dependencies are reused.
3. `spawn.json` reports `ADOPTED_LOCAL_ASSEMBLY`, the exact new class/actor paths, `/Game/MetaHumanLiveLinkProof`, and `saved=true`.
4. `bind_livelink.py` read back `LiveLinkSubject=me` and `UseLiveLink=true`, but found no enabled subject and `INVALID_OR_DISABLED`; it correctly did not create `bound-ready.json`.
5. The native collector refused `neutral-a` with: `BOUND_READY receipt is missing for the active run`.

## Defects found and fixed

- `scripts/ue_remote_exec.py` previously lost `__file__`, breaking scripts with local imports. It now executes compiled source with the real filename and supports validated repeated `--env NAME=VALUE` injection.
- Native rejection reasons were returned through the C++ out parameter but not persisted for Python recovery. Every preflight rejection now populates `GetLastError()`.
- Screenshot timeout was measured from overall capture start. It now starts when the screenshot is requested, so longer valid sample bursts do not time out immediately.
- Pose receipts now include the run ID plus bound actor path and transform. The verifier requires exact run/actor/view identity and rejects a receipt stored under a different run directory.
- `spawn.py` now saves dirty map/content packages and records the world plus `saved=true` before issuing its receipt.

## Validation

- Plugin package: UE 5.8.1 `BuildPlugin` successful.
- Skill structure: valid.
- Final source frames: neutral A `9`, neutral B `9`, expression `10` distinct IDs.
- Jaw medians: combined neutral `0.1300153881`, expression `0.8075177372`; delta `0.6775023490`.
- Automated v1 result: `MEASUREMENT_REJECTED`; neutral RMSE `0.03789118` exceeded `0.01`.
- Exact evidence: `deformation/Run20260801A/` in this proof package.
- New stale-frame regression: all repeated frame IDs/source times are rejected; focused Python tests pass.
- Rebuilt project plugin after stale-frame hardening: `UnrealEditor-BeastEvidenceCollector.dll` SHA-256 `b7d781919963ce649f31a40e950e0956d5578b724162a0d1c86f3cb1f1e1a7c5`.

## Claim boundary

Proven in this extension:

- source plugin compiles and loads inside UE 5.8.1;
- remote Python can run file-backed skill scripts with correct import semantics;
- fresh local Blueprint adoption is labeled separately from a fresh build;
- actor/map save is receipt-backed;
- missing live binding blocks native evidence capture with a recoverable reason.

Not yet proven in this extension:

- `DEFORMATION_MEASURED`;
- `ANIMATION_CONFIRMED` under the evidence contract;
- production Mood Buddy integration.
