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

## Proof boundaries

Proven:

- UE 5.8.1 installation and disposable project target.
- PC-to-phone Live Link source discovery and active green subject.
- MetaHuman Creator Core Data installation completed on D:.
- Optional MetaHuman content now exists on disk.

Not yet proven at the time of this record:

- The repaired optional content loads without warning in a fresh UE session.
- A MetaHuman Character can be created and assembled in the disposable project.
- Subject `me` drives visible facial deformation on that character.
- The same path is integrated into Mood Buddy production.

## Official references

- [Live Link in Unreal Engine](https://dev.epicgames.com/documentation/unreal-engine/live-link-in-unreal-engine?lang=en-US)
- [Using a Live Link Face Source](https://dev.epicgames.com/documentation/en-us/metahuman/using-a-live-link-face-source)
- [Realtime Animation Using Live Link](https://dev.epicgames.com/documentation/en-us/metahuman/realtime-animation-using-live-link)
- [Getting Started with MetaHuman Creator](https://dev.epicgames.com/documentation/metahuman/getting-started-with-metahuman-creator?lang=en-US)

