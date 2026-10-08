# Static assets in Studio

Open Studio's **3D assets** link, or visit `/assets`. The default route prepares
a local GLB. Meshy is optional; Blender prepares and renders the source, and
Unreal imports the chosen asset into a dedicated UE 5.8 workspace.

## Sources and costs

- **Local GLB:** static triangle geometry with embedded buffers/textures, up to
  50 MiB. Rigs, animation and external dependencies are rejected.
- **Meshy task:** retrieves a finished image-to-3D or text-to-3D task without
  generating, retexturing, remeshing, or deleting provider data.
- **Image → Meshy:** four textured Meshy 7.1 draft candidates, estimated at
  120 credits total. Both image-upload consent and the exact credit limit are
  required. A unique idempotency key binds the request; conflicting reuse is
  rejected. Unknown submissions are retained in `provider-state.json`, never
  automatically retried. Cancellation stops local work; already submitted
  Meshy tasks may finish remotely and can later be retrieved.

Review candidates in the local orbitable viewer. Downloads include GLB, FBX,
editable packed `.blend`, a rendered preview and an asset receipt. These are
drafts requiring visual and reuse-rights review. Importing a selection creates
a unique Unreal destination and verifies the actual engine/project/source
identity, loaded mesh bounds, material slots and saved assets.

## Node configuration

Existing `BEAST_BLENDER` and `BEAST_UE58_EXE` overrides select local binaries.
The Unreal engine must report 5.8 in its `Build.version`. The workspace is
`.beast/unreal-assets/BeastAssets.uproject`; the legacy RouteRush API remains
available for compatibility, while Studio's new handoff targets 5.8.

Set `MESHY_API_KEY` or `BEAST_MESHY_API_KEY` in the Studio process environment.
To reuse an existing local Meshy MCP credential, `BEAST_MESHY_KEY_FILE` can
point to its TOML configuration, or node-local `beast.config.json` can contain
the `meshy_key_file` path. Only `[mcp_servers.meshy.env].MESHY_API_KEY` is read.
Neither the key nor signed download URLs enter job records or shared evidence.

Start Studio normally:

```powershell
python studio/server.py
```

## Owner verification

Install `requirements-dev.txt`, then run against an owned static GLB and a fresh
output directory:

```powershell
python scripts/verify_asset_pipeline.py --source path/to/owned.glb --output .beast/check-001 --unreal --viewport
```

This executes Blender, reopens the GLB in a fresh Blender process, imports it
in Unreal 5.8, reopens saved meshes in a separate engine process, and attempts
an offscreen viewport capture after GPU admission. Inspect the retained image;
capture success is separate from visual acceptance. Omit `--viewport` for
CPU-only import/readback. No generation credits are consumed by this command.

Two original control assets and portable Blender builders are retained in
`proofs/assets-20261008/`, alongside measured outcomes and original failures.
The runtime stops only its own process tree, including launcher descendants.
Windows children are suspended until bound to a kill-on-close job; Linux
children use a dedicated process group. Active user editors are preserved.

The Python client exposes `asset_tools`, `meshy_tasks`, `upload_asset`,
`prepare_asset`, and `import_asset_unreal`; the TypeScript client exposes the
matching camelCase methods. Both follow the checked-in OpenAPI contract.

## Current observed acceptance

Local plain and textured controls passed actual Blender and UE 5.8.1 execution,
fresh-process readback, source/export checks, Studio upload/inspection/import,
and native viewport inspection. Meshy authentication and both task-list APIs
worked, with empty lists. Live paid generation and real hosted-model retrieval
remain blocked by the required batch approval or a finished task. The separate
maintenance PR #47 supplies runtime/packaging upgrades; this change includes
its minimal schema-isolation repair and httpx test dependency because active
asset jobs and clean test installs require them.
