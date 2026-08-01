---
name: ue58-metahuman-live-link-readiness
description: Prepare, cloud-rig with explicit user authorization, assemble, spawn, and verify Unreal Engine 5.8 MetaHuman characters through Live Link Face up to BOUND_READY state. Use for UE 5.8 MetaHuman Creator, iPhone Live Link Face, missing MetaHuman content, assembly, generated Blueprint discovery, subject binding, or proof/recovery work. This readiness skill cannot emit ANIMATION_CONFIRMED; visible facial animation requires a separate trusted capture-and-sampling proof.
---

# UE 5.8 MetaHuman Live Link Readiness

Produce an evidence-backed assembled character whose generated actor is bound to an active Live Link subject. Stop at `BOUND_READY`; the separate deformation gate can only identify a candidate for a future trusted proof.

## Operating rules

1. Require Unreal Engine 5.8. Hard-stop on every other version.
2. Work in a disposable project until the full path is reproduced.
3. Prefer UE Python or Unreal MCP for deterministic actions. Use guarded UI control only for editor-only gaps.
4. Never accept Epic terms, face-mesh consent, enter device codes, or authorize an account for the user.
5. Never infer success from a click or zero exit code. Require a log marker, artifact discovery, property readback, or screenshot.
6. Keep `BOUND_READY` and `ANIMATION_CONFIRMED` as different states.
7. Set `BEAST_ALLOWED_UPROJECT` to the exact disposable `.uproject`, set `BEAST_USER_CONFIRMED_DISPOSABLE_PROJECT=1` only after the user confirms it, and set a fresh `BEAST_RUN_ID` before every run. The project name must contain `Proof`, `Sandbox`, or `Disposable`; all generated assets must remain below `/Game/MoodBuddyProof/<run-id>`.

Read [references/evidence-contract.md](references/evidence-contract.md) before executing. Read [references/recovery-playbook.md](references/recovery-playbook.md) only when a gate fails. Read [references/deformation-gate.md](references/deformation-gate.md) before assessing deformation evidence.

## Workflow

### 1. Preflight without external work

Run `scripts/preflight.py` inside the open UE editor. It verifies UE 5.8, duplicates or loads the project character, checks assembly readiness, and does no cloud work by default.

```text
py "<skill>/scripts/preflight.py"
```

Do not continue when optional MetaHuman content is missing, the target class is wrong, or the active engine is not 5.8.

### 2. Cross the cloud boundary explicitly

Autorigging and texture synthesis use Epic cloud services. Explain the operation, wait for the user to complete authentication and consent, then set both opt-in flags in the same Unreal Python environment:

```python
import os
os.environ["BEAST_ALLOW_METAHUMAN_CLOUD"] = "1"
os.environ["BEAST_USER_AUTHORIZED_METAHUMAN_CLOUD"] = "1"
```

Run `scripts/cloud_prepare.py`. Require its marker to report the requested rig type, readback showing all eight texture-source resolution fields configured to 2K, high-resolution textures, and `can_build=true`. This proves configuration and build eligibility, not that every downloaded source independently has 2K pixel dimensions. The UE Python API also does not expose a sufficient postcondition for proving that the requested blendshape rig exists, so the script reports `blendshape_rig_verified=false`. Treat Full Rig as requested—not verified—unless a separate UI/log artifact proves it.

### 3. Assemble and discover

Run `scripts/assemble.py`. Do not assume the generated Blueprint path. Require:

- separate clean assembly-log review;
- absent-before/new-after asset comparison;
- exactly one newly generated Blueprint candidate;
- saved run-scoped assets.

The script emits `ASSEMBLY_CANDIDATE`, not `ASSEMBLED`. Review the assembly log, then set `BEAST_USER_REVIEWED_ASSEMBLY_LOG=1` only after the user confirms it. `spawn.py` consumes the candidate receipt and refuses a Blueprint path that differs from the discovered path.

### 4. Spawn, inspect, and bind

Run these scripts in order:

1. `scripts/spawn.py`
2. `scripts/introspect_livelink.py`
3. `scripts/bind_livelink.py`

Use the exact reflected UE 5.8 fields `LiveLinkSubject` and `UseLiveLink`. Require the chained reviewed-assembly/spawn receipt, readback of the intended subject and `true`, plus the subject name in Unreal's enabled-subject list, the subject enabled flag, and `CONNECTED` subject state. These checks establish `BOUND_READY`; they do not establish facial animation.

### 5. Record the receipt

Capture:

- engine version and project path;
- project character and discovered generated Blueprint paths;
- cloud operation authorization boundary;
- rig, texture, and assembly markers;
- active source/subject screenshot;
- actor binding readback;
- known warnings and pending restart state.

State the final claim as `BOUND_READY`. The bundled measurement script cannot promote the claim.

### 6. Assess without promotion

Follow [references/deformation-gate.md](references/deformation-gate.md). `scripts/measure_two_pose.py` can reject a capture or emit `DEFORMATION_CANDIDATE`; it intentionally cannot emit `ANIMATION_CONFIRMED`. Promotion remains blocked until a trusted collector binds raw UE Live Link samples and aligned captures to one run-scoped receipt.

## Bundled scripts

- `preflight.py` — version, asset, assembly-readiness, and optional connection checks without cloud work.
- `cloud_prepare.py` — explicitly gated Full Rig and texture requests.
- `assemble.py` — optimized/medium assembly with before/after asset evidence.
- `spawn.py` — spawn or reuse the generated proof actor.
- `introspect_livelink.py` — discover reflected Live Link fields on the actor/components.
- `bind_livelink.py` — set and read back subject and enable state.
- `measure_two_pose.py` — evaluate candidate metrics without promoting an animation claim.
