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

## Prerequisites (this design is CONDITIONAL on all of these)

1. **PR #15 (Experience Forge lifecycle + signed evidence) merged to main.**
   As of this revision it is OPEN, not landed — every reference below to
   lifecycle probes, demotion, checkpoint-verify, or the signed chain means
   "the machinery PR #15 proposes, once merged." If PR #15 changes under
   review, this design re-reviews against what actually lands.
2. **OPP-20260804-09 present in the main ledger** (currently only on the
   PR #15 branch). This document must not merge with a dangling ledger
   reference — rebase/re-link after the prerequisite lands.
3. A user-controlled trust root exists (see Authorization) — created by the
   user interactively, before the first manifest can be approved.

## Design principle

**The runner executes approvals; it never makes them.** Every night's work
is a user-approved manifest. The runner adds four things schedulers don't
have: resource admission, OS-enforced budget envelopes, freshness receipts
scoped to what the host can actually prove, and crash-recoverable service
restoration with an explicit unresolved state.

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
    {"id": "verify-signed-chains", "kind": "evidence_chain_verify",
     "target": "proofs/**/signed-evidence.jsonl", "timeout_minutes": 10,
     "resource_profile": "cpu_light",
     "host_requirements": {"platform": "linux-arm64", "gpu": false,
                            "apps": [], "network": false}}
  ],
  "on_breach": "cgroup_kill_job, run_restoration, receipt, halt_night",
  "manifest_sha256": "<canonical-json sha256>",
  "signature": "<HUMAN TRUST ROOT signature over manifest_sha256>"
}
```

**Host/platform compatibility is an admission AND a promotion rule.** Every
job declares `host_requirements`; admission refuses jobs whose requirements
the host cannot meet. Freshness is scoped to what the host actually proved:
a Spark-2 CPU run can refresh *schema/chain/manifest* evidence for a pack,
but can NEVER refresh a UE 5.8 *capability* claim — UE runs only on the
Windows/5090 host (arm64 UE confirmed impossible 2026-07-26). A probe
receipt names exactly which evidence class it refreshes; the lifecycle
engine must reject a freshness promotion whose evidence class does not
match the claim. The earlier draft's example (UE pack probed from Spark-2)
was a false-freshness path — retracted.

### Authorization trust root (two distinct gates, neither implies the other)

Agents share the user's git and GitHub credentials, so `approved_by: "user"`
in a file an agent can write proves nothing. Therefore:

- **Human trust root:** the user generates a dedicated Ed25519 keypair
  interactively (private key stays user-controlled — passphrase-protected,
  never readable by agent sessions; NOT any agent session key, NOT the
  PR #15 proof keys).
- **The authoritative public key lives OUTSIDE the repo** at root-owned
  `/etc/beast-runner/trusted_user.pub` (installed by the user with sudo at
  Gate 1). The runner verifies file owner (root), mode (0644, root-writable
  only), and key fingerprint at every start, and refuses on any mismatch.
  A repo copy may exist for reference but is NEVER authoritative and can
  never override /etc — agents can push commits, so a repo-pinned key
  would let an agent swap the trust root and sign its own manifests
  (amendment from codex hardware review, 2026-08-05).
- **Manifest approval = a signature over the canonical-JSON SHA-256 of the
  exact manifest**, carrying scope (host, date window) and expiry. The
  runner verifies signature + scope + expiry against the pinned public key
  before every night — an unsigned, expired, out-of-scope, or modified
  manifest is a `no_manifest` night.
- **Gate 1 (standing): timer installation** — approves the runner existing
  on a host. **Gate 2 (per-manifest): the signature above** — approves one
  concrete night's work. Neither implies the other; both are required.

Hard rules:
- No valid signed manifest → the timer wakes, writes a `no_manifest`
  receipt, exits. Silence is never scheduled.
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
restore    -> CRASH-RECOVERABLE, not guaranteed: obligations are recorded
               before the pause, reconciled on every runner start (including
               after power loss / crash). Each obligation ends in exactly one
               state: restored_verified | unresolved_requires_human. The
               unresolved state is loud (digest top-line + alarm) and never
               auto-cleared — host power loss, disk corruption, or a missing
               dependency can defeat restoration, and the design says so
               rather than promising otherwise.
receipt    -> signed start/finish/fail/skip receipt appended to the
               evidence chain (Ed25519, hash-linked, PR #15 verifier).
```

### OS-enforced envelopes (the watchdog observes; the OS enforces)

Each job runs in a **dedicated systemd transient SERVICE unit**
(`systemd-run --unit=beast-job-<id> --property=...` — NOT `--scope`: scope
units cannot carry `Type=`, and the proven timeout contract requires
`Type=exec`), so limits are kernel-enforced and fail-closed rather than
watchdog-promised:

- `DeviceAllow=` default-deny for GPU device nodes (`/dev/nvidia*`) —
  zero GPU use is *enforced*, not asserted; a nonzero GPU budget whitelists
  devices for that job's scope only.
- `IPAddressDeny=any` (plus `RestrictNetworkInterfaces=` where available)
  when `network: false` — downloads are impossible, not just forbidden.
- Isolated write directory per job; the unit gets no write path outside
  it (`ReadWritePaths=` allowlist + `ProtectSystem=strict`).
  **Disk-size ceiling: primitive NOT yet pinned or tested** — candidates
  are a per-job loopback image mount (`size` fixed at creation), tmpfs
  `size=` for small jobs, or xfs/ext4 project quotas; whichever is chosen
  must pass a hardware test (same standard as the unit contract) before
  the ceiling may be described as enforced. Until then the ceiling is
  WATCHDOG-MONITORED with threshold kill — observed, not enforced — and
  receipts must label it that way. Pinning this primitive is added to the
  smallest experiment's Night A checklist.
- `RuntimeMaxSec=` for wall-clock timeout — **with the proven unit
  contract, which is load-bearing**: hardware tests on both Sparks
  (codex-beast-primary-1, 2026-08-05) showed `Type=oneshot` silently
  defeats `RuntimeMaxSec` (a 2s cap ran 30s); the enforced-and-verified
  combination is:
  `Type=exec` + `KillMode=control-group` + `TimeoutStopSec=3` +
  `RuntimeMaxSec=<cap>` + `DevicePolicy=closed` (with `DeviceAllow=`
  whitelist only when a GPU budget is approved). This exact contract is
  pinned; deviations are a design change requiring re-review.
- **Startup property probe:** before launching the job payload, the runner
  reads the live unit's effective properties (`systemctl show`) and
  verifies they match the pinned contract — a unit that lost its limits
  (wrong Type, missing DevicePolicy, unset RuntimeMaxSec) refuses to run.
  Enforcement is verified per job, not assumed from the unit file.
- `MemoryMax=`, `TasksMax=` per profile.
- Termination is **cgroup-scoped** (`systemctl kill --kill-whom=all` on the
  unit) — never raw process-tree walking, which is vulnerable to PID reuse
  and breaks the "never anything else" promise.

Watchdog (separate CPU-only unit): on stale heartbeat past
`timeout + grace`, cgroup-kill the job's unit, run restoration, write a
`stale_killed` receipt, halt the night.

## 3. Budgets are envelopes, not suggestions

- Wall-clock, GPU, network, memory, and disk budgets are enforced by the
  job's cgroup/scope properties above; the watchdog is a second layer, not
  the enforcement. Breach = cgroup kill + restoration + receipt + halt.
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
   STEP IS USER GATE 1; the night's manifest signature is GATE 2; nothing
   runs without both.
2. Night A: one **Spark-compatible** CPU job (signed-evidence chain
   verification across `proofs/`, `host_requirements: linux-arm64, no GPU,
   no network`) → morning digest shows completion receipt refreshing
   *chain-integrity evidence only* — explicitly NOT any UE capability
   claim (those can only be probed from the Windows/5090 host, later
   phase, separately gated).
3. Night B: a deliberately broken job (bad probe target) → digest shows
   fail receipt, restoration verified, night halted per policy.
4. Night C: kill the runner mid-job (simulated crash) → watchdog/next-wake
   restores obligations from the receipt DB; stale-job alarm fires.
5. Acceptance: 100% of starts have finish/fail/skip receipts; zero silent
   staleness; every restoration obligation ends in restored_verified or a
   loud unresolved_requires_human (no third state, no silence); zero GPU
   device opens and zero egress (verified from cgroup accounting + system
   logs, not just receipts).

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

1. RESOLVED per review (codex-beast-primary-1): dedicated human trust
   root, distinct from all agent keys, signing the canonical manifest hash
   with scope + expiry. See Authorization section.
2. Should `skipped_busy` jobs retry within the night's window or only
   reappear in the next manifest? (Proposed: one retry at night's end.)
3. Windows host variant: Task Scheduler + the same receipt DB, or keep the
   runner Spark-only until the 5090's interactive-use conflict story is
   designed? (Proposed: Spark-only v1.)

## Relationship to existing machinery

Uses (CONDITIONAL on PR #15 merging — see Prerequisites): `beast
resource-check`, lifecycle probes + demotion (beast/lifecycle.py),
checkpoint verify, signed evidence chain + `verify_signed_evidence.py`. New surface: manifest schema, watchdog,
restoration-obligation DB, digest writer. Estimated build: 2–3 agent-days
after design approval — but the *decision* this document requests is only:
approve the design direction and the smallest experiment's user gate.
