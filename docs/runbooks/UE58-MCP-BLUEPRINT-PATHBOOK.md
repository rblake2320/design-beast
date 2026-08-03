# Pathbook: driving UE 5.8 Blueprint authoring headlessly over MCP

Written 2026-08-01 from the first full live run (Enhanced Input movement slice,
`proofs/watch-004-ue58-first-game/EXECUTION-PROOF.md`). Follow this and the same
class of task takes minutes, not hours. Everything below was live-verified.

## 1. Boot the headless editor + MCP

```
"D:\DEpic GamesUE_5.8\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" ^
  "D:\Epic Games\Projects\BeastLab\BeastLab.uproject" ^
  -nullrhi -nosplash -unattended -stdout ^
  -ExecCmds="ModelContextProtocol.StartServer"
```
- Ready in ~12 s (poll POST /mcp until HTTP 200; GET returns 405 — that's normal).
- Or toggle `unreal-mcp` in the Studio Backends panel.

## 2. MCP session handshake (raw HTTP, no MCP client needed)

1. POST `initialize` → response **header** `Mcp-Session-Id: <id>` — capture it.
2. POST `notifications/initialized` with that header.
3. All subsequent `tools/call` POSTs carry the `Mcp-Session-Id` header.
4. Responses are **SSE-framed** (`event: message` / `data: {...}`) — parse the
   `data:` line, then the `result.content[0].text` payload, which is itself JSON
   (triple-nested decode for `execute_python_code`: SSE → tool result → output).

Headers on every call: `Content-Type: application/json`,
`Accept: application/json, text/event-stream`.

## 3. The one tool that matters: `execute_python_code`

The gateway trio (`list_toolsets`/`describe_toolset`/`call_tool`) is for
discovery, but everything real goes through `execute_python_code` with
`import unreal`. VibeUE services are static classes: `unreal.BlueprintService`,
`unreal.InputService`, `unreal.WidgetService` (owns start_pie/stop_pie), etc.

**Windows/bash gotcha:** never inline Python in a curl `-d` string. Write the
snippet to a file, json-wrap it with a helper, POST with `-d @file`. A `run_py()`
bash helper with two `python -c` steps (encode payload / decode SSE) works well.

## 4. Blueprint graph authoring — the discovery-first loop

The deterministic workflow (per VibeUE docs and confirmed live):
`discover_nodes` → `create_node_by_key(spawner_key)` → `get_node_pins` →
`connect_nodes` / `set_node_pin_value` → `compile_blueprint` → `save_asset`.

**Search discovery with INTERNAL CamelCase names, not display names.**
"Event Tick" finds nothing; "ReceiveTick" finds it. "Branch" → nothing;
"IfThenElse" → Branch. Display-name search sometimes works ("Add Mapping
Context") but internal names are reliable.

### Verified spawner keys (BP context: Character-parent Blueprint)

| Node | Spawner key |
|---|---|
| Event BeginPlay | `EVENT Actor::ReceiveBeginPlay` |
| Event Tick | `EVENT Actor::ReceiveTick` |
| Get Player Controller | `FUNC GameplayStatics::GetPlayerController` |
| Get EnhancedInputLocalPlayerSubsystem (from PC) | `SPAWN K2Node_GetSubsystemFromPC\|Get EnhancedInputLocalPlayerSubsystem` |
| Add Mapping Context | `FUNC EnhancedInputSubsystemInterface::AddMappingContext` |
| Has Mapping Context | `FUNC EnhancedInputSubsystemInterface::HasMappingContext` |
| Inject Input Vector for Action | `FUNC EnhancedInputSubsystemInterface::InjectInputVectorForAction` |
| EnhancedInputAction event (asset must exist first) | `SPAWN K2Node_EnhancedInputAction\|IA_Move` |
| Add Movement Input | `FUNC Pawn::AddMovementInput` |
| Branch | `SPAWN K2Node_IfThenElse\|Branch` |
| Print String | `FUNC KismetSystemLibrary::PrintString` |
| Make Vector | `FUNC KismetMathLibrary::MakeVector` |
| Variable getter | `SPAWN K2Node_VariableGet\|Get <Display Name>` (e.g. `Get Inject X`) |

### Pin-name rules (bit you'll get wrong otherwise)

- Exec pins: `execute` (in) / `then` (out). Event outputs: `then`.
- Function self: `self`. Subsystem node: `PlayerController` in, `ReturnValue` out.
- **Variable getter output pin = the variable's INTERNAL name** (`InjectX`), even
  though the spawner key uses the display name (`Get Inject X`). When a connect
  fails, `get_node_pins` and retry — never guess twice.
- `split_pin(bp, graph, node, "ActionValue")` → `ActionValue_X` / `ActionValue_Y`.
- Object-typed pins take asset paths as strings via `set_node_pin_value`
  (e.g. MappingContext → `/Game/Input/IMC_Asteroids.IMC_Asteroids`).
- Struct literals as strings: WorldDirection → `"(X=1.0,Y=0.0,Z=0.0)"`.

### Compile + save

```python
bp = unreal.load_asset(path)
unreal.BlueprintEditorLibrary.compile_blueprint(bp)
bp.get_editor_property('status')   # want BS_UP_TO_DATE
unreal.EditorAssetLibrary.save_asset(path)
```

## 5. Enhanced Input assets (`unreal.InputService`)

```python
unreal.InputService.create_mapping_context("IMC_X", "/Game/Input")      # priority=0
unreal.InputService.create_action("IA_Move", "/Game/Input", "Axis2D")
unreal.InputService.add_key_mapping(ctx, act, "W")                       # per key
unreal.InputService.add_modifier(ctx, mapping_index, "Negate")           # by index
```
- Modifier type strings: `Negate`, `SwizzleAxis`, `DeadZone`, `Scalar`, … (from
  `get_available_modifier_types`). Swizzle default order YXZ = the tutorial's
  "Swizzle Input Axis Values".
- WASD→Axis2D recipe: W none, S `Negate`, A `SwizzleAxis`+`Negate`, D `SwizzleAxis`.
- ⚠ `get_mappings`/`get_modifiers` can return EMPTY after a PIE session has run
  (stale resolution). The asset is fine — verify via
  `imc.get_editor_property('default_key_mappings').get_editor_property('mappings')`.

## 6. Levels, actors, PIE

- New level with floor+light: `LevelEditorSubsystem.new_level_from_template(path,
  "/Engine/Maps/Templates/Template_Default")`. ⚠ Its floor is tiny (~10 m): a
  600 UU/s character walks off in <2 s. For movement tests spawn a huge floor
  (cube at z=−52, scale (2000,2000,1)).
- Spawn BP instance: `EditorActorSubsystem.spawn_actor_from_class(
  unreal.EditorAssetLibrary.load_blueprint_class(bp_path), loc, rot)`; set
  `auto_possess_player` → possession confirmed via `GameplayStatics.get_player_pawn`.
- PIE: `unreal.WidgetService.start_pie()` / `stop_pie()` / `is_pie_running()`.
  PIE world: `unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()`.
- **The editor ticks in real time BETWEEN MCP calls; it does NOT tick while your
  Python snippet runs.** So a behavioral test = many small calls with real sleeps
  between them, state carried via instance properties.

## 7. Behavioral input testing (no keyboard available)

- Python has NO key-level injection and NO subsystem access from outside
  (`SubsystemBlueprintLibrary` is not exposed; `pc.player` is protected;
  `get_typed_outer(LocalPlayer)` returns None).
- **Pattern that works — in-Blueprint test scaffold** (build it with the same
  node workflow, ~10 nodes):
  - Float vars `InjectX`/`InjectY` — must call
    `BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, True)`
    or Python `set_editor_property` on instances throws "cannot be edited on
    instances".
  - `Tick → InjectInputVectorForAction(IA_Move, MakeVector(InjectX, InjectY, 0))`
    — zero vector = no actuation = clean idle.
  - `CustomEvent CheckIMC → HasMappingContext → Branch → PrintString
    "BEASTTEST_IMC_ACTIVE"/"..._MISSING"` — fire with `pawn.call_method('CheckIMC')`,
    read `Saved/Logs/BeastLab.log`. This is the runtime proof that the BeginPlay
    chain worked.
  - Action-level injection bypasses per-key modifiers — verify the key→vector
    layer structurally from `default_key_mappings` and state the boundary honestly.
- Test-leg hygiene: before each leg `pawn.get_movement_component()
  .stop_movement_immediately()` + `set_actor_location(start)`, then arm inject,
  sleep, sample `get_actor_location()/get_velocity()/get_actor_rotation()`, disarm.

## 8. Gotchas index (each cost real time)

1. **CDO edits don't reach already-placed instances** after recompile
   (`bUseControllerRotationYaw` stayed true on the placed pawn). Diagnostic
   signature: yaw stuck at exactly RotationRate·dt (±3° @120 fps) = controller
   snap-back fighting orient-rotation. Fix class defaults BEFORE placing, or set
   the instance too.
2. Reflection struct field names differ from expectation — `BlueprintNodeTypeInfo`
   has `display_name`, NOT `node_title`. When unsure print `str(struct)`.
3. `unreal.SubsystemBlueprintLibrary` missing, `World.get_game_instance` missing,
   `PlayerController` exposes no LocalPlayer path — subsystem work goes in-BP.
4. `set_component_property` only reaches SCS components; inherited C++ components
   (CharacterMovement) need CDO access:
   `unreal.get_default_object(cls).get_editor_property('character_movement')`.
   (`cls.get_default_object()` does not exist — use `unreal.get_default_object`.)
5. `discover_nodes` empty results → wrong search term form (use CamelCase
   internals); it is NOT broken.
6. `save_asset` can return false right after `stop_pie` — retry next call.
7. `create_asset` for Blueprints: `BlueprintFactory` +
   `factory.set_editor_property("parent_class", unreal.Character)`.
8. `add_member_variable(bp, name, BlueprintEditorLibrary.get_basic_type_by_name("float"))`
   — new vars are NOT instance-editable by default (see §7).
9. MCP responses for big payloads: persist to file; the triple-nested JSON decode
   is mandatory everywhere.
10. Editor self-exits after ~90 min idle — re-toggle/relaunch, re-handshake
    (session ids die with the process).

## 9. Official sources & corroboration (added 2026-08-02)

Epic's docs independently confirm this pathbook's core facts (research digest,
user's Downloads `md (3).md`):

- Official guide: dev.epicgames.com → "Unreal MCP in Unreal Editor" + Plugin
  Index entry `ModelContextProtocol` (UE 5.8).
- Endpoint/transport as documented here: `127.0.0.1:8000/mcp`, loopback-only,
  NO auth, HTTP/SSE only (no stdio/WebSocket) — never expose it off-box.
- **Epic officially lists Enhanced Input as a first-party toolset GAP** — going
  through VibeUE's `InputService` (as this pathbook does) is the correct route,
  not a workaround.
- Fresh-project setup: the Editor/AI **Toolset registry must be enabled** or
  tools are advertised but inert (BeastLab already has it on).
- `ModelContextProtocol.GenerateClientConfig ClaudeCode` (or Cursor/Codex/All)
  auto-writes `.mcp.json` at the project root — prefer over hand-authoring.
- MCP is slated to be "an integral part of UE6" (2027 EA) — this knowledge
  compounds; 5.8 is the last UE5 major.

## 10. Cost calibration

First blind run (all discovery included): ~50 MCP calls / ~1.5 h.
With this pathbook: boot (1) + handshake (2) + input assets (1) + BP+nodes+wiring
(3–4) + compile (1) + level (1) + scaffold (2) + PIE test legs (~10 short calls).
Roughly 20 calls, ~15 minutes.
