# Execution proof — ue-enhanced-input-movement skill run against live UE 5.8

Date: 2026-08-01 (overnight 07-31→08-01 session)
Executor: Claude Code driving the UE 5.8 first-party MCP (headless BeastLab editor,
`http://127.0.0.1:8000/mcp`) + VibeUE BlueprintService/InputService.
Project: `D:\Epic Games\Projects\BeastLab` (lab project; test assets retained as evidence).

## Verdict

**PASS — the compiled skill's procedure was executed end-to-end against a real
UE 5.8 project and met its validation gate.** Compile clean, mapping context
verified active at runtime, signed axis movement in all four directions, and
orient-rotation-to-movement behavior confirmed after the step-7 settings.

## What was executed (mapped to SKILL.md steps)

| Skill step | Action | Result |
|---|---|---|
| 1 | `IMC_Asteroids` + `IA_Move` created in `/Game/Input` via `unreal.InputService` | both created, saved |
| 2 | `IA_Move` value type `Axis2D` | set at creation |
| 3 | W/S/A/D mappings; S=Negate, A=SwizzleAxis(YXZ)+Negate, D=SwizzleAxis(YXZ) | verified in asset struct `DefaultKeyMappings` |
| 4 | BeginPlay → GetPlayerController → GetEnhancedInputLocalPlayerSubsystem → AddMappingContext(IMC_Asteroids) wired in `BP_Player` EventGraph | all connections true; **runtime proof:** `BEASTTEST_IMC_ACTIVE` at `BeastLab.log:2699` (HasMappingContext true during PIE) |
| 5 | EnhancedInputAction IA_Move event; ActionValue split X/Y; routed to two AddMovementInput nodes, WorldDirection (1,0,0)/(0,1,0) | all connections true |
| 6 | Compile + PIE movement test | `BS_UP_TO_DATE`; movement data below |
| 7 | `bUseControllerRotationYaw=false`, `OrientRotationToMovement=true`, retest | orientation data below |

`BP_Player` parent class = **Character** (established from source frame
`f_000001040000.jpg`, "Parent class: Character"), placed in disposable level
`/Game/Maps/MoveTest` with AutoPossess Player0.

## Behavioral evidence (PIE, positions in UU, velocity UU/s)

Movement legs (pre-rotation-settings), pawn reset to (0,0,92) + StopMovementImmediately
between legs; injection = per-tick `InjectInputVectorForAction(IA_Move, v)`:

| Leg | Injected value | Velocity | Displacement sign | Yaw |
|---|---|---|---|---|
| W | (+1, 0) | (+600, 0) | +X ✔ | 0 |
| S | (−1, 0) | (−600, 0) | −X ✔ | 0 |
| A | (0, −1) | (0, −600) | −Y ✔ | 0 |
| D | (0, +1) | (0, +600) | +Y ✔ | 0 |

Orientation legs (post step-7, grounded on `BigTestFloor`, z≈88 throughout):

| Leg | Injected | Yaw result | Expected |
|---|---|---|---|
| W | (+1, 0) | 0.0 | 0 ✔ |
| S | (−1, 0) | 180.0 | 180 ✔ |
| A | (0, −1) | −90.0 | −90 ✔ |
| D | (0, +1) | +90.0 | +90 ✔ |

## Honest boundary

- **Injection point is the action layer, not the keyboard.** Python exposes no
  key-level injection, so the behavioral test injects post-mapping vectors via
  `InjectInputVectorForAction`. The key→vector layer is verified separately and
  structurally: the asset's `DefaultKeyMappings` holds exactly
  W=none, S=Negate(x,y,z), A=Swizzle YXZ→Negate, D=Swizzle YXZ, whose Enhanced
  Input semantics produce precisely the four vectors injected. The composition
  covers the chain; a literal keyboard press was not simulated.
- **Test scaffold added to BP_Player** (marked, not part of the skill's product):
  `InjectX`/`InjectY` float vars + Tick→MakeVector→InjectInputVectorForAction
  chain, and CheckIMC→HasMappingContext→PrintString. The skill-specified graph
  is separate and unmodified.
- Rendering was nullrhi (headless) — no screenshots; evidence is JSON position/
  velocity/yaw samples + the UE log line.

## Defects found in the skill run (and fixes — feed back into SKILL.md)

1. **Blueprint-reinstancing gotcha (real UE behavior, worth a skill note):**
   CDO changes to `bUseControllerRotationYaw` after an actor is already placed do
   NOT propagate to the placed instance (it kept `true` and clamped orient-rotation
   to exactly RotationRate·dt = 3°/frame — diagnostic signature worth remembering).
   Fix: apply class defaults before placing the pawn, or set the same properties on
   placed instances too.
2. Skill step 7 says "disable Use Controller Rotation Yaw" — correct and
   REQUIRED; the ±3° equilibrium is what it looks like when missed.
3. Skill precondition "BP_Player and playable level exist" was NOT satisfiable in a
   fresh lab project — executor must create them (Character parent, AutoPossess,
   floor large enough that movement legs stay grounded; template floor is ~10m and
   the pawn walks off in <2s at 600 UU/s).

## Reproduction

Full node-by-node recipe with exact spawner keys, pin names, and gotchas:
`docs/runbooks/UE58-MCP-BLUEPRINT-PATHBOOK.md` (written from this run).
