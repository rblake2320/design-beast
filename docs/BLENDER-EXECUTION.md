# Standalone Blender execution (bounded v1)

`beast blender` runs a data-only procedure in two fresh local Blender processes:
build/save, then reopen/measure/render. It does not use the editor MCP, a model,
cloud credentials, or a running Studio server. Existing editor scenes are not
opened or altered. This is a source-distributed CLI, not an installed SDK feature.

## Run

From this checkout, with Python dependencies installed and Blender configured:

```powershell
python scripts/doctor.py
./bin/beast.ps1 blender examples/blender/blockout.json --output renders-proof --allow-execute
```

`renders-proof` must not exist; its parent must exist. Use a new path for a
deliberate new run. `BEAST_BLENDER`, local `beast.config.json`, or `--blender`
selects the trusted executable through Beast's existing configuration. The
procedure pins an exact Blender version; a mismatch fails rather than silently
adapting. No install or restart is automatic.

The example is **owner-authored test geometry**, not a watched tutorial or a
finished creative deliverable. Four fixed camera views support visual inspection;
native transforms/materials and image decoding do not prove aesthetic quality.

## Contract

See `examples/blender/blockout.json` and `beast/blender_contract.py`.

- `add_mesh`: named cube, UV sphere or subdivided grid.
- `transform`: absolute location, XYZ Euler degrees, positive scale.
- `material`: opaque RGBA, roughness and metallic values.
- `bend`: one Simple Deform bend per object, exact axis and angle in degrees.

Only earlier-created objects can be targeted. Unknown fields/actions, duplicate
IDs, non-finite numbers, forward references and oversized plans are rejected.
No Python text, arbitrary operator names, external asset paths or input `.blend`
files are accepted. Supported bounds are explicit in the contract.

## Bind Watch evidence

Replace a scalar in the procedure with `{"field":"typed_field_name"}` and run:

```powershell
./bin/beast.ps1 blender template.json --output new-proof --allow-execute --target target.json --observations observations.json --timeline timeline.json
```

Beast reruns its existing typed compiler against the retained frames. An
unresolved state, hash mismatch, wrong application or version stops execution.
The compiled state and consumed field names are retained. Unbound setup is
authored scaffolding, never silently labeled as visually learned. Frame hashes
bind pixels; they do not establish that a human/model interpreted them correctly.
This runner does not promote Watch procedures or bypass their visual-only and
reinspection publication gates.

## Evidence and recovery

`receipt.json` is written before each child starts. It records authorization,
exact command, executable/worker/contract/procedure hashes, exit codes, structural
gates and output hashes. `steps.json` records native state after each action.
`scene.blend` is reopened in a second process; `measurement.json` is compared
against the expected final contract. `view-0.png` through `view-3.png` are CPU
Cycles diagnostic renders, 512x384, 24 samples, two threads. GPU admission is not
needed for this deliberately CPU-only path; no GPU/model process is stopped.

Every trace step is checked against its plan prefix. Primitive-specific base
topology/shape, modifier state/count, render visibility and nonzero evaluated
vertex displacement for a nonzero bend are checked as well as final transforms.
Windows sharing/access-denied errors retry only the same atomic receipt replace,
at most five attempts; persistent denial retains the old receipt and `.tmp`.

Nonzero child exits, missing artifacts, wrong native values or invalid images
cannot report success. Timeout retains `outcome_unknown`, kills only the child
started by this runner, and never automatically replays. A crash may leave the
write-ahead receipt or its temporary file; quarantine that run for inspection.
This directory is an exclusive run reservation, not a resumable job queue.

The executable, worker, output parent and operating-system account are trusted.
This is **process isolation, not an OS sandbox**: a compromised local Blender,
hostile concurrent writer or native vulnerability is outside this v1 boundary.
Binary/file hashes are integrity receipts, not signatures or authentication.

## Tests and claim boundary

Owner acceptance command (two positive and three negative cases, CPU-only):

```powershell
python scripts/verify_blender_execution.py --output my-new-blender-proof --allow-execute
```

It verifies blockout + actual bend, no-authority denial, exact-version drift, and
a configured-but-ineffective bend. All runs and artifact hash checks are retained.

```powershell
python -m pytest -q tests/test_blender_execution.py
# Explicitly opt into the real CPU artifact test:
$env:BEAST_TEST_BLENDER = 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
python -m pytest -q tests/test_blender_execution.py -k live
```

Default tests cover validation, no-permission/no-mutation, malformed evidence,
missing outputs, child failures, timeout receipts and native-state mismatches.
The live test is opt-in, not a silently mocked engine success. No broad tutorial
learning, generalized modeling, game readiness, paid Higgsfield integration or
Unreal execution is claimed by this slice. The next gate is a fresh real tutorial
with independently reviewed frame observations and a named visual acceptance test.
