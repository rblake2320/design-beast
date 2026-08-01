# UE 5.8 MetaHuman + Live Link Face green path

Last verified: 2026-08-01 (America/Chicago)

This runbook records only what was observed or verified on the local machine. It separates a working network/Live Link connection from the still-unproven final MetaHuman facial-animation response.

## Fixed target

- Engine: Unreal Engine 5.8.1 only.
- Engine root: `D:\DEpic GamesUE_5.8\UE_5.8`
- Disposable proof project: `C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\MoodBuddyUE58Proof.uproject`
- Do not use the Mood Buddy production renderer for this proof.
- Phone endpoint used in the successful connection: `192.168.12.238:14785`.
- Live Link Face source name observed in Unreal: `Live Link Face`.
- Machine and subject observed in Unreal: `iPhone` / `me`.

## Proven green path

1. Use a UE 5.8.1 disposable project with `MetaHumanCharacter` and `MetaHumanLiveLink` enabled.
2. Put the iPhone and PC on a reachable network path.
3. In Live Link Face, enable Live mode and target the PC running Unreal.
4. In Unreal, open the Live Link panel and add/use the Live Link Face source.
5. Select the phone source and confirm the subject appears.
6. Treat a green subject indicator as proof that Unreal is actively receiving Live Link data, not as proof that a MetaHuman is responding.

Observed result on 2026-08-01:

- Source: `Live Link Face`
- Machine: `iPhone`
- Subject: `me`
- Role: `Basic`
- Status: green

Local evidence captured during the run:

- `C:\Users\techai\AppData\Local\Temp\moodbuddy58-livelink-tall.png`
- `C:\Users\techai\AppData\Local\Temp\moodbuddy58-livelink-subject.png`

## MetaHuman content repair

Before repair, the UE log reported:

```text
MetaHuman Optional Content folder not found. MetaHuman Creator plugin initialized with limited features.
```

The editor was closed cleanly. Epic Games Launcher 20.1.7 was then used to modify only UE 5.8.1 and add `MetaHuman Creator Core Data` to the D-drive installation. The launcher request resolved the `metahuman_content` tag. After completion, the launcher returned to `Launch` and the following folder existed:

```text
D:\DEpic GamesUE_5.8\UE_5.8\Engine\Plugins\MetaHuman\MetaHumanCharacter\Content\Optional
```

Verified optional subfolders included `Animation`, `Body`, `BodyTextures`, `Clothing`, `DCC`, `Grooms`, `Migration`, `Presets`, and `TextureSynthesis`.

Install evidence:

- `C:\Users\techai\AppData\Local\Temp\epic-metahuman-only.png`
- `C:\Users\techai\AppData\Local\Temp\epic-metahuman-download-active.png`
- `C:\Users\techai\AppData\Local\Temp\epic-metahuman-progress-1.png`
- `C:\Users\techai\AppData\Local\Temp\epic-metahuman-progress-2.png`
- `C:\Users\techai\AppData\Local\Temp\epic-metahuman-progress-3.png`
- Launcher log: `C:\Users\techai\AppData\Local\EpicGamesLauncher\Saved\Logs\EpicGamesLauncher.log`

## Resume after interruption or context compaction

1. Verify the engine binary exists at `D:\DEpic GamesUE_5.8\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe`.
2. Verify `MetaHumanCharacter\Content\Optional` still exists.
3. Open only the disposable `MoodBuddyUE58Proof.uproject` under UE 5.8.1.
4. Inspect the fresh project log. The earlier optional-content warning must be absent before treating the repair as loaded successfully.
5. Create or open a MetaHuman Character and assemble it for UE Cine or an appropriate optimized quality level.
6. Bind the assembled character to the exact Live Link subject exposed by the phone.
7. Capture a neutral frame and a deliberately changed expression frame.
8. Require both a changing subject signal and visible character response before claiming end-to-end facial animation.

If the phone is offline, continue through character creation/assembly and binding readiness. Record the final response proof as blocked by source availability, not failed.

## Verified deterministic automation path

UE 5.8 ships first-party MetaHuman Python examples under:

```text
D:\DEpic GamesUE_5.8\UE_5.8\Engine\Plugins\MetaHuman\MetaHumanCharacter\Content\Python\examples
```

The installed examples cover asset creation, assembly, and actor spawning. Prefer these supported editor APIs over OCR for deterministic construction; retain SelfConnect screenshots for visual verification. The installed Live Link plugin also exposes a scriptable source connection:

```python
handle, created = unreal.LiveLinkFaceSourceBlueprint.create_live_link_face_source()
connected = unreal.LiveLinkFaceSourceBlueprint.connect(
    handle, "me", "192.168.12.238", 14785
)
```

Design Beast packages the non-cloud checks in `scripts/ue58_metahuman_preflight.py`. Run it from an open UE 5.8 editor console with:

```text
py "C:/Users/techai/brain/design-beast/scripts/ue58_metahuman_preflight.py"
```

The script hard-stops outside UE 5.8, verifies/duplicates the configured project asset, checks assembly readiness, emits one JSON evidence marker, and performs no external work by default. A validated run returned engine `5.8.1-56057345`, a saved `MetaHumanCharacter`, `can_build=false`, `high_resolution_textures=false`, and `live_link.attempted=false`.

Measured on this machine, the first asset-editor load took about 38 seconds while Unreal built and cached optional assets. A subsequent warm preflight emitted its evidence marker in about 2.6 seconds. Prefer one explicit warm-up followed by API checks instead of repeatedly rediscovering state through UI actions.

Observed on 2026-08-01 after the phone left the network: source-handle creation returned `True`, while connection returned `False`. That is expected offline behavior and is not evidence of a plugin failure.

### Local preset experiment

The bundled preset `/MetaHumanCharacter/Optional/Presets/Ada` was duplicated through `unreal.EditorAssetLibrary` to:

```text
/Game/Characters/MetaHumans/AdaProof
C:\Users\techai\Unreal Projects\MoodBuddyUE58Proof\Content\Characters\MetaHumans\AdaProof.uasset
```

The duplicate saved successfully as class `MetaHumanCharacter`. The first readiness query failed because character data had not loaded. Opening it through `AssetEditorSubsystem` loaded the character data and local optional assets. A second `can_build_meta_human` query then failed for the narrower reason `Character is not rigged`.

This is a useful hard gate: do not run assembly until `can_build_meta_human` returns true. Do not silently invoke cloud autorig or texture services when it returns false.

### Cloud Full Rig gate

Epic documents `request_auto_rigging` and `request_texture_sources` as supported UE 5.8 Python operations. No checkout or per-call price is documented, but do not state that the service is guaranteed to remain free. The two documented service hosts are:

```text
mh-uemhc-autorig-service.eeeb.live.use1a.on.epicgames.com:443
mh-texture-synthesis-service.eeeb.live.use1a.on.epicgames.com:443
```

Both hosts passed a TCP 443 preflight on 2026-08-01. The reflected UE 5.8 Full Rig enum is `MetaHumanRigType.JOINTS_AND_BLEND_SHAPES` (with an underscore between `BLEND` and `SHAPES`). Introspect the live enum rather than copying a display label or guessing its Python name.

A single Full Rig request on the generic Ada preset reached Epic authentication and opened a device-authorization page. The browser then displayed an explicit `MetaHuman Face Mesh Consent` page with `Accept` and `Decline` choices. The log reported no persistent auth credentials and `authorization_pending`. No credentials, verification code, access approval, consent choice, or terms acceptance were supplied by the agent. This is a required human boundary: pause for the user.

For privacy language, Epic says an uploaded Face Mesh is not retained after processing; do not broaden that into “Epic retains nothing,” because ordinary account, usage, and technical telemetry may still be retained.

## UE 5.8 preflight and known confounds

- Live Link Face on iOS must use `MetaHuman Animator` capture mode. Epic documents that realtime connection fails in ARKit mode in UE 5.8.
- Use port `14785`; VPNs, different subnets, and an offline phone can prevent connection.
- A green source confirms incoming data only. It does not prove character deformation.
- Full Rig is required for blendshape facial animation. An unrigged character cannot be assembled for this proof.
- UE 5.8 documents visible seam and some groom/quality issues on assembled characters. Do not automatically classify those known rendering issues as failed assembly or failed Live Link.
- MetaHuman Creator rigging and texture synthesis use Epic cloud services. Keep those external operations explicit in proof logs.

## Proof boundaries

Proven:

- UE 5.8.1 installation and disposable project target.
- PC-to-phone Live Link source discovery and active green subject.
- MetaHuman Creator Core Data installation completed on D:.
- Optional MetaHuman content now exists on disk.
- A fresh UE 5.8.1 session loaded MetaHuman Character and Live Link modules without the former limited-features warning.
- A bundled preset duplicated and saved as a project-scoped MetaHuman Character asset.
- The supported readiness API distinguished unloaded data from the current unrigged state.
- The supported Live Link Python API created a source handle; an offline phone correctly produced `connected=False`.

Not yet proven at the time of this record:

- The project-scoped MetaHuman Character has a Full Rig.
- A MetaHuman Character can be assembled in the disposable project.
- Subject `me` drives visible facial deformation on that character.
- The same path is integrated into Mood Buddy production.

## Official references

- [Live Link in Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/live-link-in-unreal-engine?lang=en-US)
- [Using a Live Link Face Source](https://dev.epicgames.com/documentation/en-us/metahuman/using-a-live-link-face-source)
- [Realtime Animation Using Live Link](https://dev.epicgames.com/documentation/en-us/metahuman/realtime-animation-using-live-link)
- [Getting Started with MetaHuman Creator](https://dev.epicgames.com/documentation/metahuman/getting-started-with-metahuman-creator?lang=en-US)
- [Creating a Character](https://dev.epicgames.com/documentation/en-us/metahuman/creating-a-character)
- [MetaHuman Assembly](https://dev.epicgames.com/documentation/metahuman/assembly?lang=en-US)
- [MetaHuman Creator Python Scripting](https://dev.epicgames.com/documentation/metahuman/metahuman-creator-python-scripting-in-unreal-engine?lang=en-US)
- [MetaHuman Known Issues 5.8](https://dev.epicgames.com/documentation/unreal-engine/metahuman-known-issues-5-8-in-unreal-engine)
- [MetaHuman 5.8 Release Notes](https://dev.epicgames.com/documentation/metahuman/metahuman-5-8-release-notes-in-unreal-engine)
- [MetaHuman Data Use](https://dev.epicgames.com/documentation/en-us/metahuman/metahuman-data-use)
