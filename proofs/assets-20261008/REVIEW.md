# Static-asset workflow review — 2026-10-08

Built from remote main `1edb5c2` in an isolated worktree. Existing checkout edits,
open maintenance PR #47, user Blender process and other projects were preserved.
No Meshy generation credits were spent.

| Acceptance scenario | Observed outcome |
| --- | --- |
| Plain control: Blender prepare/render, GLB reopen, UE 5.8 import and fresh-process reopen | Worked: 37.063 s; Blender bounds difference 0 m; one mesh/material slot; source/export hash retained |
| Textured control with parent rotation and nonuniform scale | Worked: 26.047 s; embedded texture and bounds retained; UE extents 66.9615/55.9808/75 cm; saved mesh survived restart |
| Studio file picker → preparation → local 3D viewer → Unreal import | Worked in the real browser; receipts identify UE 5.8.1 and the dedicated destination |
| Mobile 390 px viewport | Worked: document width 375 px; visible buttons at least 45.1875 px high; no browser error logs |
| Native UE viewport | Worked after repairs: complete blue/gold control visible, no obscuring debug widgets or visible engine errors; independent image inspection agreed |
| Meshy authenticated balance and v1 image/v2 text task lists | Worked: 8,070 credits, both lists empty |
| Live paid Meshy batch / real hosted model download | Blocked: no existing task; required 120-credit batch approval is pending |
| Hosted/privacy authorization removed in a controlled test copy | Failed as expected: the strengthened consent regression rejects the altered code; zero actual provider calls |
| Malformed/no-geometry/external/rigged GLBs, out-of-bounds buffers, invalid transforms | Worked: rejection before engines open inputs; contained public errors |
| Cancellation and process ownership | Worked: owned tree/grandchild terminated within 0.797 s in independent measurement; unrelated control process completed |
| Receiving receipt for another job/asset, stale receipt, failed spawn | Worked: rejected or terminal failure; no stale-file success fallback |
| Schema generation during an active asset job | Worked: row/connection/lease preserved by disposable subprocess generation |
| Clean test environment without plugin preloading | Worked: 26 focused tests after fixture isolation repair |

Validation: 292 Python tests passed, seven pre-existing GPU generation tests
excluded by repository policy; 26 focused asset tests; 21 TypeScript tests and
typecheck; fatal lint; OpenAPI drift and capability-graph checks. Hosted CI is
recorded separately once available. Tests include deterministic provider stubs
and real SQLite/process/HTTP/browser/Blender/Unreal execution; paid provider
submission stubs are not counted as live Meshy generation.

Original failures remain in this bundle and the independent review:

- malformed GLB shapes were accepted or escaped as raw exceptions; strict
  geometry/container/buffer validation now rejects them;
- text task listing initially used API v1 (404), corrected to documented v2;
- JPEG bytes were mislabeled as PNG, now normalized before submission;
- taskkill took 2.812 s and allowed a late write; suspended-child job ownership
  restored the original sub-two-second cancellation gate;
- clean tests failed because a fixture replaced global `threading.Thread`,
  corrected to a module-scoped stub and enforced in CI without plugin autoload;
- early Blender rendering lacked a world; real render diagnosis added one;
- the first native capture used an unavailable AutomationScheduler; public
  Slate callbacks and console execution now drive capture;
- the first frame was overexposed and the next map creation reused a name;
  calibrated light and unique proof maps repaired both, with a wider camera
  preserving the whole silhouette;
- nested exports were omitted from manifests; recursive checksum records now
  include editable sources and receipts, and draft assets require review;
- import refresh discarded the selected viewer/downloads; receiving status now
  carries the prepared selection so it can be restored after reload;
- a Windows atomic-file read race affected an existing test helper; bounded
  manifest polling now retries read/parse failures without relaxing its deadline.

The design detector's remaining side-tab finding is the existing red striped
error tape in Studio; it is contextual failure-state treatment, not a repeated
card accent. Colored glow shadows were removed; no suppression was added.

Primary sources used:

- https://docs.meshy.ai/en/api/image-to-3d
- https://docs.meshy.ai/en/api/text-to-3d
- https://docs.meshy.ai/en/api/pricing
- https://docs.meshy.ai/en/api/balance
- https://modelviewer.dev/
- https://dev.epicgames.com/documentation/unreal-engine/the-gl-transmission-format-gltf-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/interchange-framework-in-unreal-engine
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects

Vendor: model-viewer 4.3.1, Apache-2.0 license retained beside the local runtime.
The accepted viewport and Blender preview are functional control-asset proof.
The workflow currently handles static assets; rigs/animation are rejected.
The remaining human handoff is independent/user review and merge, plus explicit
approval if the live paid Meshy acceptance test should proceed.
