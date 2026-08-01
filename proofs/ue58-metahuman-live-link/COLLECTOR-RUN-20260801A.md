# Trusted collector extension — Run20260801A

Run date: 2026-08-01 (America/Chicago)

## Current result

The native `BeastEvidenceCollector` source plugin compiled against UE 5.8.1, was installed into the disposable `MoodBuddyUE58Proof` project, and was loaded by the running editor. A fresh receipt chain reached `SPAWNED` through an explicitly labeled local-assembly adoption path. The collector then refused a pose request because the fresh run had no `BOUND_READY` receipt.

This proves the plugin's UE 5.8 runtime load, fresh-run local adoption, saved actor state, remote execution path, and fail-closed precondition. It does not prove a fresh cloud build, a connected phone subject for this run, deformation, or animation.

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
- Automated tests: 26 passed, including image-hash tampering and cross-run receipt rejection.
- Remaining human input: point Live Link Face at the current PC Wi-Fi endpoint and turn `LIVE` on so the fresh run can reach `BOUND_READY` and collect neutral/expression receipts.

## Claim boundary

Proven in this extension:

- source plugin compiles and loads inside UE 5.8.1;
- remote Python can run file-backed skill scripts with correct import semantics;
- fresh local Blueprint adoption is labeled separately from a fresh build;
- actor/map save is receipt-backed;
- missing live binding blocks native evidence capture with a recoverable reason.

Not yet proven in this extension:

- fresh-run `BOUND_READY`;
- three native pose receipts;
- `DEFORMATION_MEASURED`;
- visual-region review or `ANIMATION_CONFIRMED`.
