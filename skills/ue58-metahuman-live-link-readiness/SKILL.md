---
name: ue58-metahuman-live-link-readiness
description: Prepare, optionally cloud-rig with explicit user authorization, assemble or honestly adopt a reviewed local build, spawn, and verify Unreal Engine 5.8 MetaHuman characters through Live Link Face up to BOUND_READY; collect run-scoped deformation evidence up to DEFORMATION_MEASURED. Use for UE 5.8 MetaHuman Creator, iPhone Live Link Face, missing content, assembly/adoption, subject binding, or proof/recovery work. This skill cannot emit ANIMATION_CONFIRMED without a separate visual-region review tied to the captured hashes.
---

# UE 5.8 MetaHuman Live Link Readiness

Produce an evidence-backed assembled or explicitly adopted character whose actor is bound to an active Live Link subject. Readiness stops at `BOUND_READY`; trusted collector receipts and numerical checks can reach `DEFORMATION_MEASURED`, while `ANIMATION_CONFIRMED` remains blocked on visual-region review.

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

If the user already completed rigging and texture download in the UI, do not repeat
the cloud requests. Record authorization and run
`scripts/reconcile_cloud_prepared.py`; it requires the same eight 2K readbacks,
then writes a receipt labeled as adopted existing cloud output rather than fresh
cloud work. Before assembly it also requires high-resolution textures and
`can_build=true`. After a successful assembly has unloaded the editable Character
data, it instead requires the receipt's generated Blueprint to exist and reports
`can_build=null`; do not mistake that expected post-assembly state for a failure.

### 3. Assemble and discover

Run `scripts/assemble.py`. Do not assume the generated Blueprint path. Require:

- separate clean assembly-log review;
- absent-before/new-after asset comparison;
- exactly one newly generated Blueprint candidate;
- saved run-scoped assets.

The script emits `ASSEMBLY_CANDIDATE`, not `ASSEMBLED`. Review the assembly log, then set `BEAST_USER_REVIEWED_ASSEMBLY_LOG=1` only after the user confirms it. `spawn.py` consumes the candidate receipt and refuses a Blueprint path that differs from the discovered path.

If preflight finds a high-resolution local UE 5.8 character but `can_build=false`, do not imply a fresh assembly and do not force a cloud request. With an explicitly reviewed existing Blueprint, set `BEAST_MH_EXISTING_BLUEPRINT` and run `scripts/adopt_assembled.py`. It duplicates only that Blueprint under the fresh run and labels the receipt `ADOPTED_LOCAL_UE58_BLUEPRINT`, including that prior local dependencies remain reused.

### 4. Spawn, inspect, and bind

Run these scripts in order:

1. `scripts/load_proof_map.py` when reopening a saved disposable proof level.
2. `scripts/spawn.py`
3. `scripts/introspect_livelink.py`
4. `scripts/bind_livelink.py`

For the current Live Link Face app in MetaHuman Animator mode, create the UE-side source with `scripts/connect_livelink_face_source.py` using the phone address and required port `14785` before binding. This is a PC-pulls-from-phone source; do not substitute the legacy ARKit phone-push workflow.

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

State the readiness claim as `BOUND_READY`. The legacy measurement script cannot promote it.

### 6. Assess without promotion

Follow [references/deformation-gate.md](references/deformation-gate.md). `scripts/measure_two_pose.py` can reject a capture or emit `DEFORMATION_CANDIDATE`; it intentionally cannot emit `ANIMATION_CONFIRMED`. The trusted collector plus `verify_pose_receipts.py` can emit `DEFORMATION_MEASURED`, but promotion remains blocked until the exact hashed images receive visual-region review.

For trusted collection, source-build the plugin in `assets/BeastEvidenceCollector` against UE 5.8, install it into the disposable project's `Plugins` directory, enable it, and restart the editor. Follow [references/collector.md](references/collector.md). The plugin refuses captures without the matching `BOUND_READY` receipt and loaded bound actor, then writes curve bursts, actor/view identity, hashed PNGs, and JSON pose receipts under `Saved/BeastProof/<run-id>/deformation`.

## Bundled scripts

- `preflight.py` — version, asset, assembly-readiness, and optional connection checks without cloud work.
- `cloud_prepare.py` — explicitly gated Full Rig and texture requests.
- `reconcile_cloud_prepared.py` — verify and adopt user-completed cloud output without requesting it again.
- `assemble.py` — optimized/medium assembly with before/after asset evidence.
- `adopt_assembled.py` — explicitly adopt one reviewed local UE 5.8 Blueprint into a fresh run without claiming a fresh build.
- `load_proof_map.py` — reopen an explicit saved disposable proof map.
- `spawn.py` — spawn or reuse the generated proof actor.
- `introspect_livelink.py` — discover reflected Live Link fields on the actor/components.
- `bind_livelink.py` — set and read back subject and enable state.
- `connect_livelink_face_source.py` — create and connect the UE 5.8 Live Link Face source through the native bridge without copying the opaque source handle through Python.
- `load_proof_map.py`, `save_proof_assets.py`, and `quit_editor.py` — preserve and safely reopen the disposable proof state around native plugin rebuilds.
- `request_pose_capture.py` / `capture_status.py` — request and poll native trusted pose receipts.
- `measure_two_pose.py` — evaluate candidate metrics without promoting an animation claim.
- `verify_pose_receipts.py` — verify collector-issued neutral/expression receipts, hashes, identity, timestamps, curve delta, continuity, and rendered change without accepting typed-in curve values.
- `assets/BeastEvidenceCollector` — UE 5.8 editor plugin for engine-tick curve sampling and synchronized viewport capture.
