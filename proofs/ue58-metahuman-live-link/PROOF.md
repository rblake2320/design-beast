# UE 5.8 MetaHuman + Live Link Face proof

Run date: 2026-08-01 (America/Chicago)

## Result

The disposable UE 5.8.1 project produced and saved a full-rig MetaHuman, assembled an optimized/medium runtime character, spawned its generated Blueprint, received the iPhone Live Link Face subject `me`, and bound that exact subject to the actor with `UseLiveLink=true`.

This proves assembly and bound Live Link readiness. A later acknowledged three-pose run also reproduced visible facial animation with independent source and render evidence. The strict v1 automated measurement did **not** promote the run because the two neutral images exceeded its stability threshold; `DEFORMATION_MEASURED` and `ANIMATION_CONFIRMED` therefore remain unclaimed.

## Fixed environment

- Engine: `5.8.1-56057345`
- Engine root: `D:\DEpic GamesUE_5.8\UE_5.8`
- Project: `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\MoodBuddyUE58Proof.uproject`
- Project asset: `/Game/Characters/MetaHumans/AdaProof`
- Generated Blueprint: `/Game/MoodBuddyProof/Run001/MetaHumans/AdaProof/BP_AdaProof`
- Spawned actor label: `BEAST_AdaProof`
- Phone: `192.168.12.238:14785`
- Live Link source / subject: `Live Link Face` / `me`

## Reproduced evidence chain

1. A fresh authorization attempt completed after the earlier device code expired. Unreal logged `EOS_Success` and the authenticated Epic display name.
2. UE 5.8 Full Rig autorig completed in 47.899 seconds.
3. The first build correctly remained gated because texture sources were missing.
4. All eight 2K source maps downloaded. Readback returned `HIGH_RES=True` and `CAN_BUILD=True`.
5. Optimized/medium assembly succeeded and created 282 run-scoped assets, including `BP_AdaProof`, face/body meshes, ARKit mapping, and `ABP_MH_LiveLink`.
6. The generated assets were saved; Unreal showed `All Saved` before the later temporary-level actor change.
7. `BP_AdaProof` spawned as `BEAST_AdaProof` in the disposable level.
8. UE 5.8 reflection identified the generated actor properties as `LiveLinkSubject` (`LiveLinkSubjectName`) and `UseLiveLink` (`bool`).
9. The phone established a TCP connection to port 14785. The Live Link panel showed source `Live Link Face`, machine `iPhone`, subject `me`, role `Basic`, and a green status indicator.
10. Direct actor readback emitted:

```text
BEAST_LIVELINK_BOUND={"actor": "/Temp/Untitled_1.Untitled_1:PersistentLevel.BP_AdaProof_C_UAID_10FFE0B701E3CDF302_1076989183", "subject": "me", "use_live_link": true}
```

## Reusable automation

- `scripts/ue58_spawn_metahuman_probe.py` loads the discovered generated Blueprint, spawns or reuses the proof actor, selects it, and emits its actual class/path.
- `scripts/ue58_introspect_metahuman_livelink.py` searches the live generated actor and its components for UE 5.8 Live Link fields instead of guessing names from another engine version.
- `scripts/ue58_bind_metahuman_livelink.py` assigns the exact subject and requires reflected readback before reporting success.
- `scripts/ue_remote_exec.py` is a remote-Python helper. Remote execution was disabled during this original Run001 proof. It was enabled and runtime-proven during the later `Run20260801A` collector extension; see `COLLECTOR-RUN-20260801A.md`.

UE 5.8's Python `Actor` wrapper did not expose `rerun_construction_scripts`, and `LevelEditorSubsystem` did not expose the attempted viewport focus helper. Neither absence invalidated spawning or binding; the proof uses direct property readback and screenshots instead.

## Visual artifacts

- `metahuman-full-rig-all-saved.png` — photoreal AdaProof editor preview, eight 2K texture-source statuses, and full-rig state.
- `assembly-window.png` — assembly result window.
- `live-link-subject-me.png` — active `me` subject in Unreal Live Link.
- `spawned-bound-metahuman.png` — selected spawned actor with Live Link enabled in its details panel.

## Known confound

The project requested a restart after enabling Shader Model 6, which is required for correct Nanite rendering. The MetaHuman editor preview rendered correctly, but the temporary level was not restarted during this evidence run to avoid discarding the active phone/session state. A future visual-deformation proof must start with SM6 active and no pending restart.

## Claim boundary

Proven:

- UE 5.8 Full Rig and 2K texture-source completion.
- UE 5.8 optimized/medium assembly and saved generated assets.
- Spawned project Blueprint actor.
- Active iPhone Live Link subject.
- Exact actor subject binding with enabled-property readback.

Not proven:

- `DEFORMATION_MEASURED` or `ANIMATION_CONFIRMED` under the v1 numerical contract.
- A saved production level or packaged build.
- Integration into Mood Buddy's production renderer.

## Run20260801A collector extension

The saved proof map was reopened and a fresh receipt chain reached `BOUND_READY`. Unreal reported subject `me` as enabled and `CONNECTED`, and read back `UseLiveLink=true` on actor label `BEAST_Run20260801A`. The original runtime `bound-ready.json` has SHA-256 `12e7c180d59a9e297acc256958032da83bc74752f947543ba98bf994692a12bb`; normalized repository snapshots are under `receipts/`.

This extension reproduced and repaired four integration defects:

1. UE's generated Python wrapper copied the opaque `LiveLinkSourceHandle`, making a Python-only create/connect sequence fail. A C++ bridge now creates and connects the source without crossing that wrapper boundary.
2. UE's Python wrapper exposes an output error string for the collector request rather than the native boolean. Empty error now means accepted.
3. The UE 5.8 MetaHuman Animator stream exposes `CTRL_expressions_jawOpen`, not legacy `jawOpen`. The skill default and documentation now use the emitted UE 5.8 control.
4. `FPlatformMisc::GetSHA256Signature` crashed the editor with `No SHA256 Platform implementation` after writing the first PNG. The native collector now uses `PlatformCryptoContext::CalcSHA256`; the partial PNG was archived under the runtime run's `failed-captures` directory and is not counted as evidence.

The repaired native plugin built successfully. A later capture was performed only after explicit user acknowledgements for neutral and expression poses. The final receipts contain 9, 9, and 10 distinct source frames. The combined neutral jaw median is `0.1300153881`; the expression median is `0.8075177372`; the source delta is `0.6775023490`, and all 10 expression samples clear the continuity condition. The exact hashed expression render visibly shows the intended mouth/jaw deformation.

The verifier still emitted `MEASUREMENT_REJECTED`: fixed mouth-region neutral RMSE was `0.03789118` versus the predeclared maximum `0.01`, so the rendered-deformation threshold became `0.18945590` while observed expression RMSE was `0.11791251`. This is ordinary head/eyelid/lighting motion in unregistered crops, but the threshold is not changed after seeing the data. The run supports the narrower statement that UE 5.8 Live Link facial animation was reproduced and verified across source data and hashed pixels. It does not support the formal promotion states.

Exact artifacts are under `deformation/Run20260801A/`. `visual-review.json` binds the human visual review to the three image hashes and explicitly blocks promotion because `measurement.json` failed.

A frozen-source attempt also exposed a collector weakness: an evaluable Live Link subject can return the same stale frame repeatedly. Native collection and offline verification now require at least three distinct frame IDs and at least `0.10` seconds of source-time span. The Python regression test passes; the native plugin must be rebuilt before the next run for the C++ guard to take effect.
