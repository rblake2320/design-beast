# Independent 3D workflow review — 2026-10-08

Final verdict: no remaining actionable code or test-harness findings after the repairs recorded below. Independent native Unreal visual check Worked for the bounded textured control. Original red history and outstanding external acceptance gates are retained. Reviewer lane is read-only code inspection and isolated tests. No paid provider call, real Blender/Unreal execution, or active user scene mutation was performed.

## Instructions and recall

Read CONSTITUTION.md, this worktree's AGENTS.md/CLAUDE.md, BEAST.md, QUALITY-LOOP.md, game-asset recipe, existing bridges, cancellation code/tests, and file-access boundary. New Unreal work must target5.8; the5.6 RouteRush path is explicitly legacy. MemoryWeb localhost8100 refused connections and its helper reported authentication unavailable. UltraRAG remote health was up; current-task search returned no results. Local memory registry contained no relevant3D pipeline prior decision used in this review.

## Controlled baseline findings

Reproducer: `3d-independent-baseline.py`; machine output: `3d-independent-baseline.jsonl`. The script initializes a disposable SQLite DB before importing Studio, substitutes temporary paths and fake tool outcomes, joins its workers and closes their thread-local DB connections. It never invokes real Blender/Unreal.

- Failed — legacy `/api/to_ue` accepts non-GLB bytes, then reports DONE when both fake tools return exit1 and a pre-existing `asset.uasset` exists. This demonstrates a stale receipt and missing input/return-code validation.
- Failed — cancellation requested immediately after Blender still allows the UE import call. The durable row correctly becomes CANCELLED, but the forbidden receiving-side stage is still invoked. Terminal state alone is insufficient cancellation evidence.
- Failed — FileNotFoundError at Blender spawn escapes the worker and leaves the row RUNNING. Each new worker must classify spawn/timeout/parser/download failures into terminal state.
- Inspected — every legacy run exports `asset.fbx`, imports to the same `/Game/BeastAssets/asset`, and uses replace_existing=True. This collides across jobs and can overwrite user assets.
- Inspected — legacy configuration binds `/api/to_ue` to UE5.6 RouteRush. A new workflow must explicitly bind a5.8 binary and target project, without silently selecting the legacy project.
- Inspected — the legacy Blender script sets every mesh object's scale to `(100,100,100)`, replacing original object scaling and disregarding hierarchy-dependent transforms. This requires measured unit/bounds verification, rather than applying that rule to arbitrary Meshy GLBs.

## Required acceptance for the new workflow

1. Existing Meshy task retrieval is a separate operation from generation. Prove it makes only task-status/asset retrieval requests and downloads, with zero generation, texturing, remesh or rigging submissions. Authentication/subscription/download failures must remain classified errors; retries never fall through to paid generation. Preserve provider task ID, source/type, timestamps, license/attribution data when actually supplied, and GLB checksum.
2. Paid/hosted generation gates must be server-enforced, explicit and default-denied. Source-image transmission and spending require their respective authorization, before network side effects. A UI checkbox without server validation is not the gate. Existing asset retrieval should not be mistaken for authorization to send a new prompt/image to a provider.
3. Validate GLB content before Blender/UE: GLB2 header, declared byte length, chunk bounds/alignment and JSON shape; reject truncated/oversized/empty-geometry artifacts and unsupported external dependencies with classified errors. Engine import/reimport must independently verify nonempty geometry, finite bounds, materials/textures and transform/unit behavior. File extension or header magic alone is not an asset validation result.
4. Treat model URLs as untrusted input. Restrict provider/API hosts and asset download origins, validate redirects, retain response/body size limits and timeouts, and never forward provider Authorization to an arbitrary asset host. Download to job-owned temporary files; cancel/error/truncation must not promote a partial GLB.
5. Cancellation must suppress subsequent side effects, not merely set the final row: before remote submissions, during polling/download, before Blender, before UE and before success publication. Cancel only subprocess trees created by this job, retain cleanup evidence, and leave the user's existing GUI scenes/processes intact. Run a cancellation-between-Blender-and-UE case and assert zero UE calls.
6. Headless Blender must operate on an isolated scene/process. Retain the imported source, Blender version, counts/bounds/unit conversion, exported `.blend`/FBX/GLB as applicable, artifact hashes, and a receiving reimport/render check. Preserve meaningful source transforms rather than replacing each object's scale. Conversion-only success must not claim repaired topology or game readiness.
7. Bind Unreal receipt to actual engine version5.8, canonical project identity/path, unique job destination and FBX/source hash. Verify the imported object is the expected nonempty StaticMesh and is saved/readable in that target. A pre-existing `.uasset`, HTTP success, process exit alone or unbound stdout string cannot satisfy the receipt.
8. Use unique asset destinations with an explicit overwrite/idempotency policy. Retry and recovery must distinguish safe read/download from generation/import side effects, retain task/import receipts and avoid overwriting unrelated project assets. A crash after import needs outcome classification/reconciliation, not blind resubmission.
9. Worker exception barriers must drive Failed/Cancelled terminal outcomes. Retain stderr and stage-specific diagnostic evidence without exposing API keys, signed asset URLs or other credentials. Final job data should expose receiving artifact paths and exact outcomes so the UI can show real progress and downloads.
10. Verify the shipped Studio/SDK/browser path in addition to component tests. Real free existing-asset import -> Blender artifact -> UE5.8 receiving import and screenshot evidence is the workflow acceptance target. If a required account task/project/tool is unavailable, attempt its concrete preflight and report the exact blocker; do not substitute a synthetic fixture for a live provider claim.

The builder owns implementing and exercising these acceptance cases; the reviewer will verify final deltas and run safe independent checks after notification.

## Final-delta review findings and independent checks

The initial implementation passed the builder's control-asset Blender/UE proof, but independent fault probes found additional boundaries:

- P1 malformed GLB containers escaped as HTTP500 (`asset:[]`, `buffers:null`) and invalid mesh shapes/empty primitives were accepted. Original observations retained in `3d-independent-glb-probe.jsonl`. Repair retest `3d-independent-glb-green.jsonl`: all four now classified AssetError/HTTP400, and the parser now checks embedded geometry/accessors/indices/finite transforms. Normal test fixture was corrected to a genuine embedded triangle.
- P2 valid JPEG paid input was labelled PNG while retaining JPEG bytes. Original observation retained in `3d-independent-gates-probe.jsonl`. Repair retest `3d-independent-gates-green.jsonl`: outgoing bytes are actually PNG and media declaration matches; all provider calls were stubbed and no credits were spent.
- P2 a fresh receiving receipt with correct hash/job/project/engine but foreign destination and asset paths was accepted. Repair retest rejects it with AssetError. The validator now checks exact job destination, each mesh path, finite positive geometry, LOD and material metadata.
- P2 import-refresh lost selection, preview and downloads. Actual inline assets.html JavaScript executed in an isolated DOM fixture reproduced a completed import showing its success text while the viewer remained hidden, empty panel visible and downloads absent. This is a controlled UI logic test, not a browser run. Original observation: `3d-independent-ui-reload.jsonl`. Builder is adding persisted selected_asset and hydration; final retest pending.
- P1 the current branch retained the known unsafe schema generator from main. A disposable active asset job changed RUNNING -> FAILED and its lease1 ->0 after generate_openapi.generate(). No live database was touched. Evidence: `3d-independent-schema-red.jsonl`. This workflow's OpenAPI dependency requires the previously reviewed subprocess-isolation repair, even while broader PR47 work remains separate.

Worked: focused asset suite23 passed in5.82s after the GLB/MIME/identity repairs. Worked: actual Windows owned-process cancellation in0.797s killed a grandchild before its delayed write while an unrelated owned control process completed. Machine receipt: `3d-independent-owned-proof.jsonl`, with its retained fixture directory.

An interim full-suite run during builder edits observed3 failed/287 passed/7 deselected: two legacy provenance contracts received a new review_required:false field, and the legacy-history listing fixture encountered the recent30 cap after earlier tests. These are queued for repair/isolation and retest; they are not reported as green.

Retained real control-asset proof inspected: Blender5.1.2 imported/rendered/exported a beige rectangular12-triangle prop; fresh Blender reimport bounds difference0; UE5.8.1 imported it to a dedicated job destination with centimeter extents50/100/50 and separate-process saved-mesh readback. This establishes that control case. No paid Meshy submission was performed by this reviewer; account task lists are empty and paid-batch acceptance requires the owner's explicit credit approval.

## Code review closeout before final viewport inspection

All reported implementation findings are repaired and independently retested. Final full Python run:292 passed,7 GPU suites deselected, one Starlette/httpx deprecation warning,14.08s; transcript `3d-independent-final-tests.txt`. `git diff --check` passed. Focused asset suite26 passed in2.04s.

Additional closing controls:

- Worked — known missing Blender now rejects the fully approved generation request withHTTP400 and zero provider submissions/constructions. Original/repair evidence: `3d-independent-paid-preflight-red.jsonl` and `3d-independent-paid-preflight-green.jsonl`. A version/start preflight runs before the paid boundary.
- Worked — isolated schema generation preserves the active asset row and its existing lease; green receipt `3d-independent-schema-green.jsonl` preservesRUNNING and lease1.
- Worked — import-refresh UI logic now hydrates the persisted selected_asset, shows the viewer, hides the empty state and restores5 download links. Controlled JavaScript/DOM green receipt: `3d-independent-ui-reload-green.jsonl`. Builder's fresh live browser check remains separate.
- Worked — in-memory consent-guard mutation: fully otherwise-valid source/key requests with cloudfalse or maxcredits0/30 are rejected400 with zero provider constructions by current code. Disabling the guard only in an isolated in-memory copy makes those calls construct the stub provider; the strengthened repository authorization test rejects that mutant. Evidence: `3d-independent-consent-mutant.jsonl`. No runtime source changed, provider key was synthetic, and real provider calls/credits werezero.
- Worked — the clean-install test dependency is now explicit (`httpx==0.28.1` in requirements-dev.txt). New asset CI covers Windows/Linux andPython3.12/3.13. Hosted CI outcomes remain the builder's later gate.
- Worked — old nonasset manifest outcome shape is preserved; asset drafts alone carry review_required:true and trusted:false. Nested asset exports and receipts are now hashed in the manifest. Earlier full-suite failures were repaired; new fixture-created jobs are deleted to avoid polluting the capped legacy-history test.

The builder is exercising the repository-required UE viewport gate in its dedicated5.8 workspace. GPU admission was reported successful without stopping another process; first overexposed frame was retained as Failed and lighting is being repaired. Independent visual review follows receipt of the final frame. Current account lists contain no existing Meshy task, and a real paid batch still requires explicit owner120-credit approval; neither was substituted by a mock claim in this review.

## Clean-harness gate found during final verification

Failed: `python -m pytest --disable-plugin-autoload studio/tests/test_asset_pipeline.py -q --tb=short` observed7 failed/19 passed in3.96s. Raw log: `3d-independent-clean-test-red.txt`. The API fixture patched asset_api.threading.Thread, which is the shared global threading module; AnyIO loaded its backend afterward and subclassed the substitute Immediate class, causing `Immediate.__init__ missing target`. Local plugin preloading had masked this in normal pytest runs.

This is a test-harness/CI reliability defect, not a production API defect. Requested repair is to substitute only asset_api's module reference with SimpleNamespace(Thread=Immediate) and keep the plugin-disabled invocation in asset CI. The same isolated reference is already used by reviewer probes. Closing green retest and final native viewport visual inspection remain queued.

Clean-harness repair retest Worked: plugin autoload disabled,26 asset tests passed in2.12s (`3d-independent-clean-test-green.txt`). The fixture now substitutes only asset_api.threading with an owned namespace; global threading stays intact. TypeScript21 tests and typecheck also passed. No remaining actionable implementation or harness finding from the reviewed code. The original clean-harness failure remains retained; final native UE screenshot inspection is the outstanding review gate.


## Final bounded visual verdict

Worked — independently inspected `proofs/assets-20261008/unreal-viewport.png` at1280x720 and compared it with the Blender textured preview and retained `viewport-overexposed.png`. The repaired Unreal frame shows the complete cuboid within the image, recognizable blue/gold texture on visible faces and no visible engine error or obscuring actor/debug gizmo. The initial frame is overexposed and its texture is unreadable; it remains correctly retained as a Failed visual attempt. This verdict establishes the imported textured control's render/appearance handoff, not production game-art quality.

The receiving viewport receipt names UE5.8.1, the dedicated visual-check level and the expected imported mesh. Textured source/export GLB hashes match; measured UE half-extents66.9615/55.9808/75cm match the transformed source bounds, and separate-process saved-mesh readback is retained. The builder admitted the viewport through the live GPU profile and stopped only the editor it owned. Shader/material appearance is visibly present in the final native frame.

Review closeout: no remaining actionable implementation/harness findings. Independent results include292 full Python tests,26 focused tests with plugin autoload disabled,21 TypeScript tests/typecheck, ownership/cancellation, malformed GLB, MIME, consent-guard mutation, unknown-submission replay, receipt identity, schema preservation and import-refresh logic. Updated asset CI explicitly keeps plugin autoload disabled. Builder's final live browser refresh and hosted CI are separate execution gates; this reviewer did not claim to perform them.

External acceptance remains explicit: the existing Meshy-task lists were empty in the builder's real account check, so there was no completed provider task to retrieve. A real four-candidate paid batch requires the owner's explicit120-credit authorization. All reviewer provider calls were stubbed; no generation credits were spent by this review. The source/Blender/UE/viewport checks above use retained owned control assets and do not masquerade as a completed Meshy generation run.

## Final header-only follow-up

Reviewed only the closing local_request/header delta: explicit raw Host authority parsing, numeric-port validation, rejection of userinfo/path/query/fragment in Host, loopback URL/authority checks, Origin authority comparison and a ValueError/TypeError -> AssetError fault barrier.

Worked — independently reran the three new valid-GLB malformed-header controls (unmatchedIPv6 Origin, invalidIPv6 Origin, invalidIPv6 Host), plus the existing cross-origin control, with pytest plugin autoload disabled. All4 passed in0.48s; retained transcript `3d-independent-header-controls.txt`. Malformed headers are contained as HTTP400 JSON errors. `git diff --check` passed. No additional actionable finding in this final delta.

Builder reports the completed live browser reload/keyboard orbit,5 restored exports and UE receipt. The earlier PR48 head had all6 hosted jobs green; the final header head requires its own CI rerun. Those reported execution gates remain distinguished from this reviewer's direct controls. No Meshy credits were used by the reviewer; the paid-budget authorization request remains separate.
