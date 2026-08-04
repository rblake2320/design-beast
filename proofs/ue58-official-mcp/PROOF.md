# UE 5.8 Official Unreal MCP — Live Proof

Date: 2026-08-02  
Engine: UE 5.8.1 (`D:\DEpic GamesUE_5.8\UE_5.8`)  
Disposable project: `MoodBuddyUE58Proof`  
Loaded level: `/Game/MetaHumanLiveLinkProof`

## Result

Epic's experimental first-party Unreal MCP plugin was enabled in the disposable
UE 5.8 project and exercised against the live editor process. This is not a
descriptor-only or documentation-only check: a real MCP client completed the
handshake, discovered tools, and dispatched calls on the loaded project.

The strongest immediately proven value is:

1. **Whole-graph Blueprint authoring.** `BlueprintTools.write_graph_dsl` accepted
   an S-expression program, created the graph, and compiled the Blueprint. This
   replaces the fragile node-by-node/pin-by-pin loop that previously made an
   Enhanced Input graph slow to construct.
2. **Unreal-native skills.** The live editor exposed 20 `AgentSkill` entries and
   tools to list/read/create/update project skills. The installed Blueprint skill
   explicitly instructs agents to read and write graphs through the DSL and to
   compile only after a logical unit is complete.
3. **One local control plane.** The live toolsets cover Blueprints, actors,
   assets, materials, PCG, Niagara, Sequencer, Control Rig, Slate UI automation,
   semantic search, automation tests, and programmatic/batch tool execution.
4. **Pixels plus editor state.** `CaptureViewport` returned a valid PNG together
   with the exact camera location, rotation, and FOV. This is a useful bridge
   between Beast Watch's visual evidence and Unreal's structured world state.

## Reproduction

With the project open and the official MCP server listening on loopback:

```powershell
python scripts/probe_ue58_mcp.py --capture
```

The probe is read-only. It refuses non-loopback URLs, does not save the captured
image, and reports only its byte count, PNG signature, and SHA-256 digest.

## Live observations

- Listener: `127.0.0.1:8000`, owned by the active `UnrealEditor.exe` process.
- MCP protocol negotiated: `2025-06-18`.
- Meta-tools: `list_toolsets`, `describe_toolset`, `call_tool`.
- A dispatched `SceneTools.get_current_level` call returned
  `/Game/MetaHumanLiveLinkProof`.
- The editor exposed 20 native Agent Skills.
- The reproducible probe decoded 8,665 characters of Blueprint DSL documentation
  and confirmed that it begins with `GRAMMAR OVERVIEW`.
- In-memory viewport capture returned a valid PNG. One observed capture was
  4,391,761 bytes with SHA-256
  `af62b37d8c51ae4752e6ef6047dabfcfec03ddf446bc650595127e81cabf41e0`.

### Blueprint mutation proof

The test created and saved this disposable project asset:

`/Game/BeastMCPProof/BP_MCPGraphProbe`

Before writing, MCP node search returned the exact live node type IDs
`AddEvent|EventBeginPlay` and `Development|PrintString`. One
`write_graph_dsl` call then submitted:

```lisp
(event EventBeginPlay
  (Development|PrintString "BEAST_UE58_MCP_GRAPH_PROBE"))
```

`read_graph_dsl` returned that same event and marker. A separate compile with
`warnings_as_errors=true` succeeded, and `AssetTools.save_assets` returned true.
The corresponding `BP_MCPGraphProbe.uasset` exists under the disposable
project's `Content/BeastMCPProof` directory.

## Experimental defects observed

These are findings from the installed UE 5.8.1 plugin and should be rechecked in
future engine builds:

- `initialize` returned empty `serverInfo.name`, `title`, and `version` fields.
- `CaptureViewport.captureTransform` and `annotations` are described as optional,
  but the dispatcher rejected calls that omitted them.
- `SceneTools.find_actors` describes `name`, `tag`, and `collision_channels` as
  optional filters, but its schema marks all three required.
- `FocusOnActors` returned normally for the loaded MetaHuman actor but did not
  move the camera in this World Partition level.
- `GetVisibleActors` returned a visible StaticMeshActor, while annotated viewport
  capture returned zero actor labels. Therefore actor-label grounding is **not
  proven** by this run.

## Claim boundary

Proven: the official UE 5.8 MCP server is installed, starts inside the editor,
accepts a local MCP client, exposes broad toolsets and native Agent Skills, reads
the real loaded project, captures valid viewport pixels with camera metadata,
and can create, whole-graph-write, compile, read back, and save a Blueprint.

Not yet proven: reliable annotated actor labels, unattended end-to-end task
execution, or better quality/speed than every community MCP implementation.
Those require separate, measured tests.

The report that UE 5.8 is the first release to ship this plugin and the broader
UE 5.8 feature inventory remain research claims unless separately supported by
Epic release material. This proof establishes the local plugin behavior only.
