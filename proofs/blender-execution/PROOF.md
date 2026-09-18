# Blender execution proof — 2026-09-18

Status: measured on local Blender 5.1.2 through the actual source-distributed
Beast CLI. This is a bounded infrastructure proof, not tutorial learning or a
finished creative asset. See `docs/BLENDER-EXECUTION.md`.

Preflight: Blender CLI 5.1.2 available. Editor MCP read at 127.0.0.1:9876 failed
to connect. Beast doctor: 31 OK, optional ComfyUI offline, FFmpeg/FFprobe missing.
No GPU work or external provider submissions are used by this CPU proof.

Initial suite: 41 passed, one explicit live-test opt-in skipped. An initial
test assertion was corrected by tightening missing-field gates; reviewer
triangle-as-cube and disabled-modifier false positives received regressions.

First CLI invocation rejected a missing output parent before any Blender run;
the proof directory is now explicitly created. No run was overwritten.

## Final real acceptance

`acceptance-02/acceptance.json` is the canonical final matrix. It records explicit
`status: complete`, all five expected case IDs and their subprocess outcomes.

| Case | Observed result |
| --- | --- |
| no-authority | exit 2, rejected, no execution output directory |
| blockout | 56 gates passed; three meshes, nine recorded steps, four PNGs; 5.344 s |
| bent-grid | 28 gates passed; 136 base vertices, 99 faces, effective Z bend; 3.797 s |
| version-drift | exit 1, Blender Python exit 23, no saved scene; 1.218 s |
| noop-bend | exit 1; configured Y bend rejected for zero evaluated deformation; 4.297 s |

Each executed case retains command, intent, exit code, native state, scene and
artifact hashes. Successful cases reopen the saved file in a second Blender
process. Rendering is CPU-only Cycles, two threads, 24 samples, 512x384; no
interactive editor project, GPU workload or paid provider job is touched.

Visual inspection: the blockout's four diagnostic camera views show the expected
coral cube, teal sphere and dark platform without cropping. The effective grid
case shows changed geometry; it is not a finished asset or an artistic quality
claim. The noisy low-sample renders are diagnostic evidence only. No upscaled or
generatively enhanced evidence substitutes for the native outputs.

## Tests and independent review

- Full source suite: 313 passed, 1 opt-in Blender test skipped, 7 live-GPU tests
  deselected. Machine test report: `tests.xml`.
- Blender-specific suite: 47 passed, 1 explicit live test skipped. The engine
  was separately executed by the five-case acceptance command above.
- Fatal Ruff checks and Beast graph validation pass (9 capabilities, 1 pack).
- Most default tests are pure validators; five subprocess-fault tests mock the
  child, and one Watch integration test runs the real typed compiler on synthetic
  pixels with execution replaced. These do not substitute for native proof.
- An independent agent found and rechecked primitive false positives, incomplete
  modifier state, malformed-output failure handling, intermediate-step omission,
  Windows replace denial, and partial aggregate success. No remaining scoped
  blocker was reported after corrections. Reviewer independently checked artifact
  hashes and native measurements; it did not launch Blender itself.

## Failures and repairs retained

- `run-01/`: first primitive proof before modifier-count/visibility tightening.
- `grid-01/`: configured bend without a meaningful geometry-effect gate; flat
  output is NOT promoted as a successful bend outcome.
- `grid-02/`: effective Z bend after adding evaluated displacement. Later code
  bounds the measurement size by retaining evaluated AABB corners.
- `acceptance-01/`: full five-case matrix passed, but its earlier harness could
  write false-green intermediate summaries. Superseded by `acceptance-02/`.
- Windows independently observed `os.replace` WinError 5 during a fault test.
  The lock owner is unproven. Old unknown receipt and pending final `.tmp` were
  retained in the reviewer's pytest temp directory. Bounded retries now repeat
  only the replace operation; persistent denial remains a loud failure. Forced
  transient and persistent denial regressions are in the suite.

Regression gates include triangle-as-cube rejection, disabled/ineffective bend,
malformed native measurements, each plan-prefix outcome, duplicate JSON keys,
no permission, unknown actions, missing outputs, timeout without replay, typed
frame tampering, and explicit complete-only acceptance aggregation.

## Boundary and next gate

Verified here: bounded authored scene execution and retained structural evidence
on one Windows machine and Blender version. Not proven: a fresh tutorial-to-scene
run, semantic accuracy of model observations, arbitrary modeling, finished art,
Higgsfield/Unreal integration, OS sandboxing or any user-count/production tier.
Existing Watch binding has synthetic-pixel regression coverage only. A fresh
tutorial with independently inspected frame observations and predeclared visual
acceptance is the next milestone; this proof does not claim it happened.

Owner reproduction (new directory, explicit permission):

```powershell
python scripts/verify_blender_execution.py --output my-new-blender-proof --allow-execute
```
