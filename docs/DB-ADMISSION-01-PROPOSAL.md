# DB-ADMISSION-01: stage-aware GPU admission (proposal, not activated)

Base: `040e3a4` (PR #51 merge). Branch `claude/db-admission-01`, local only, not pushed.

## Problem
`resource_guard.admission()` measures only the local RTX 5090. Any job whose VRAM
is consumed on another host (spark-3173 via tunnel) still waits behind unrelated
local processes. Run `20261013_010724_f9fd` failed its 30-minute deadline this way.

## Stage split
| Stage | Where VRAM is used | Admission |
|---|---|---|
| remote generation (tunnel-backed backend) | remote host | `execution: "remote"`, judged on remote `nvidia-smi` only |
| local judge / refine (`judge`, `studio_light`, ...) | local GPU | `execution: "local"`, unchanged local gate |

## What this change does
- `evaluate_stage(local, remote, policy, workload)` in `studio/resource_guard.py`.
- Existing `evaluate()` and `admission()` are unchanged. Local workloads take the
  identical code path and record `execution: "local"`.
- Remote workloads never read the local snapshot. They require a fresh, available
  remote measurement judged against `policy["remote_gpu"]`. Missing, unreadable, or
  short remote state is refused, even when `unknown_state_policy` is `allow`.
- A remote workload without a `remote_gpu` policy section raises (fails closed).
- Unknown `execution` values raise. Every result keeps
  `automatic_process_termination: false`.

## Not done (needs separate written owner approval)
- No change to `beast/resource-policy.json`: no workload is marked remote, so runtime
  behavior is identical to `040e3a4`.
- `studio/jobs.py` still calls `admission(workload)`; the stage-aware path is not wired in.
- No remote `nvidia-smi` probe over SSH is implemented. Remote measurement is the next,
  separately approved step.
- `model_registry.json` is not edited.

## Tests
`studio/tests/test_resource_guard.py`: 7 new cases (remote ignores local state,
remote refuses without measurement, remote unknown state denied under `allow`,
remote short free VRAM rejected, remote without `remote_gpu` fails closed, local
gate unchanged and ignores remote, unknown execution target rejected).
Result: `python -m pytest tests -q` in `studio/` gives 154 passed, 7 deselected (live_gpu).
