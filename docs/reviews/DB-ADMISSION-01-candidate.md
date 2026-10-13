# DB-ADMISSION-01 candidate (default OFF, not activated)

Base: `040e3a4`. Builder branch: `claude/db-admission-01`.

## Contract
- Execution: a workload is `local` (default) or `remote`. Remote needs `remote_gpu.host_id` and `device_id` in policy. The workload may name a `host`; if it does, it must equal the policy identity. URLs are never used to infer locality.
- Stages: `generation`, `judge`, `refine`, `fallback`. Each stage is evaluated separately, so a local judge after remote generation faces the local gate.
- Remote readings must be well-formed: `available` is a boolean `true`; `units` is `MiB`; `total/used/free` are non-negative integers; free and used do not exceed total; `used + free == total` within 16 MiB; `host_id` and `device_id` match the policy; `measured_unix` is numeric, no older than `max_measurement_age_seconds` (fallback `measurement_ttl_seconds`), and no more than 5 s in the future.
- Any refusal is an admission of `false` with `automatic_process_termination: false`. Unknown policy, stage or execution values raise.
- Local readings also get the schema checks. A string `"false"` for `available` is refused.

## Not in this candidate
- Not wired into `jobs.py` or `server.py`. No flag. No activation.
- No remote probe. The remote measurement source is not implemented; it needs separate owner approval.
- No durable per-host leases and no cancellation or deadline handling. These remain open.
- `beast/resource-policy.json`, `beast.config.json` and `model_registry.json` are unchanged.

## Verification
- `cd studio && python -m pytest tests -q`: 163 passed, 7 deselected (live_gpu).
- Codex DB probe copied to scratch and run against this tree: 9 of 9 expectations met (`probe-new.json`). The evidence directory was not touched.
