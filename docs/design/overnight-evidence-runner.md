# Design: Budgeted Overnight Evidence Runner

Status: **PROPOSAL-ONLY** (per OPP-20260804-09's decision line — nothing here
installs a timer, schedules a job, or touches a GPU; nightly automation
requires separate, explicit user approval of a concrete manifest).
Author: claude 2 (seat), 2026-08-05, lane assigned via mesh by claude 1.
Reviewers: any agent ≠ author, then the user (rule 8).

## Problem

Matched benchmarks, lifecycle probes, and practice variants remain unrun
while the 5090 and two DGX Sparks sit idle overnight. Manual daytime runs
compete with interactive work for GPU and attention. But unattended
execution amplifies mistakes: a hung job burns hardware for hours, a
crashed run leaves services paused, a silent failure reads as "ran clean."

## Design principle

**The runner executes approvals; it never makes them.** Every night's work
is a user-approved manifest. The runner adds four things schedulers don't
have: resource admission, hard budget envelopes, freshness receipts, and
guaranteed service restoration. It inherits — not reimplements — the
machinery PR #15 landed: lifecycle probes, checkpoint-verify-resume, signed
evidence chains, and the VRAM governor.

## 1. Authorization: the Run Manifest

A manifest is a single JSON file the user approves *per night* (or per
recurring window, explicitly scoped, e.g. "Mon–Fri until 2026-09-01"):

```json
{
  "schema": "beast.runner.manifest/v1",
  "approved_by": "user",
  "approval_scope": "2026-08-06T01:00 local, single night",
  "host": "spark-2",
  "budgets": {
    "wall_clock_minutes": 240,
    "gpu_minutes": 0,
    "disk_gb": 5,
    "downloads": "none",
    "max_concurrent": 1
  },
  "jobs": [
    {"id": "probe-ue58-movement", "kind": "lifecycle_probe",
     "pack": "ue58-enhanced-input-movement", "timeout_minutes": 10,
     "resource_profile": "cpu_light"}
  ],
  "on_breach": "kill_job, restore_services, receipt, halt_night",
  "manifest_sha256": "<computed>", "signature": "<user-session Ed25519>"
}
```

Hard rules:
- No manifest → the timer wakes, finds nothing approved, writes a
  `no_manifest` receipt, exits. Silence is never scheduled.
- Jobs not enumerated in the manifest cannot run. The runner has no
  "while I'm here" authority — curriculum stays proposal-only.
- `downloads: "none"` is the default and requires explicit allowlisting to
  change. Model pulls are never overnight work.
- GPU minutes default 0. A GPU job exists only if the user approved a
  nonzero GPU budget *and* the named job.

## 2. Execution loop (per job)

```
admission  -> beast resource-check <profile>; refuse-and-receipt if denied.
               NEVER kill a user process; if the GPU/host is busy, the job
               is SKIPPED (receipt: skipped_busy), not queued into conflict.
snapshot   -> env fingerprint (same fields lifecycle drift-checks use).
pause      -> services paused ONLY if the job's profile requires it; each
               pause recorded as a restoration obligation in the receipt DB
               BEFORE the pause happens (crash-safe restore list).
checkpoint -> beast checkpoint before first mutation; verified.
run        -> job under its own timeout; heartbeat file every 60s.
verify     -> job's own acceptance check (probe result, test exit, etc.).
restore    -> every recorded obligation restored + verified; failure to
               restore = loud receipt + morning alarm, never silent.
receipt    -> signed start/finish/fail/skip receipt appended to the
               evidence chain (Ed25519, hash-linked, PR #15 verifier).
```

Watchdog (separate process, CPU-only): if a job's heartbeat goes stale
past `timeout + grace`, kill the job's process tree (never anything else),
run the restore list, write a `stale_killed` receipt, halt the night.

## 3. Budgets are envelopes, not suggestions

- Wall-clock, GPU-minutes, disk, and download budgets are enforced by the
  watchdog, not by job goodwill. Breach = kill + restore + receipt + halt.
- Electricity/wear is acknowledged as a real cost: the receipt records
  wall-clock and (where available) energy counters, so the morning digest
  shows what the night cost, not just what it produced.

## 4. Morning digest (the dream-report pattern)

One file per night: `proofs/overnight/<date>/DIGEST.md` +
`receipts.jsonl` (signed chain). The digest lists: jobs run/skipped/
failed/killed, budget consumption, restoration status, evidence deltas
(claims refreshed vs demoted by lifecycle), and anything requiring human
review. Delivery is **pull, not push**: agents/the user read it in the
morning — the runner never injects into idle sessions at 3 AM. Freshness
receipts feed the lifecycle engine directly: a probe pass refreshes a
pack's verify date; a probe failure demotes per the existing rules.

## 5. Failure design (what the smallest experiment must prove)

Per the ledger entry's falsifiable claim, the acceptance test is about
*visible* failure, not success:

1. Install a systemd timer on Spark-2 (CPU-only, `gpu_minutes: 0`) — THIS
   STEP IS THE USER GATE; nothing before it is scheduled anywhere.
2. Night A: one real CPU lifecycle probe → morning digest shows completion
   receipt + refreshed verify date.
3. Night B: a deliberately broken job (bad probe target) → digest shows
   fail receipt, restoration verified, night halted per policy.
4. Night C: kill the runner mid-job (simulated crash) → watchdog/next-wake
   restores obligations from the receipt DB; stale-job alarm fires.
5. Acceptance: 100% of starts have finish/fail/skip receipts; zero silent
   staleness; services restored in all three nights; zero unapproved
   downloads or GPU seconds (verified from receipts + system logs).

## 6. Explicit non-goals

- No autonomous experiment selection (curriculum remains proposal-only).
- No spend, no downloads, no model pulls, no repo pushes. The runner
  produces evidence and receipts; humans and daytime agents produce
  decisions and merges.
- No cross-host orchestration in v1 — one host, one manifest. Fleet-wide
  nights are a later revision after single-host acceptance passes.
- Not a CI replacement: CI proves code; the runner proves *capabilities
  stay true over time*.

## Open questions for review

1. Manifest signature: user-session Ed25519 (matches PR #15 chain) vs
   simple approved-by field in a user-committed file — is committed-to-main
   approval sufficient, given commits are already the user's authority?
2. Should `skipped_busy` jobs retry within the night's window or only
   reappear in the next manifest? (Proposed: one retry at night's end.)
3. Windows host variant: Task Scheduler + the same receipt DB, or keep the
   runner Spark-only until the 5090's interactive-use conflict story is
   designed? (Proposed: Spark-only v1.)

## Relationship to existing machinery

Uses as-is: `beast resource-check`, lifecycle probes + demotion
(beast/lifecycle.py), checkpoint verify, signed evidence chain +
`verify_signed_evidence.py`. New surface: manifest schema, watchdog,
restoration-obligation DB, digest writer. Estimated build: 2–3 agent-days
after design approval — but the *decision* this document requests is only:
approve the design direction and the smallest experiment's user gate.
