# Matched Beast-loop benchmark — frozen design (v2 draft, 2026-08-05)

Status: **DESIGN ONLY — no run has occurred, no result exists, no claim is made.**
This document freezes the experimental design before any execution, per the mesh
charter (queue item 1) and the coordination directive of 2026-08-05. It extends
`beast-loop-protocol.json` (v1, three conditions) to the four-condition design the
charter's definition-of-done requires. v1 is left untouched; the machine-readable
delta is `beast-loop-protocol.v2-draft.json`. Adopting v2 requires independent
review of this design plus user approval to spend the GPU/agent time.

## Hypothesis under test (unchanged from v1)

A compiled Beast capability improves matched task correctness or efficiency
without increasing unsupported claims. The external dividing line is SkillsBench
(arXiv 2602.12670): curated skills helped (+16.2pp average); self-generated
skills did not (+0.0pp average). Beast's packs are machine-compiled from watched
demonstrations — the benchmark must show which side of that line they land on,
against a *curated-skill* comparator, not only against no-skill baselines.

## Conditions (four, matched envelope)

| id | receives | isolates |
|---|---|---|
| C0 `baseline` | task + transcript + normal tools | no-watching floor |
| C1 `adaptive_frames` | C0 + initial sparse frames, no reinspection, no pack | value of initial visual sampling |
| C2 `curated_skill` | C0 + a human/agent-curated skill for the task, written from the same tutorial WITHOUT Beast machinery (no evidence map, no typed contract, no lifecycle) | the SkillsBench comparator |
| C3 `beast` | C0 + validated Beast Pack + recovery/resource controls | the full loop |

C2 authorship rule: the curator may watch the tutorial as a human viewer would
and write the best skill they can in ≤ the median wall-clock of the C3 compile,
but may not use Watch tooling, typed evidence, or pack validation. The curator
must not be the agent that built the Beast compiler (builder ≠ comparator).

## Task selection (sealed, unseen)

- 3 materially different domains × 3 tasks, all driven by instructional videos
  that contain **predeclared visual-only facts** absent from their transcripts.
- Pilot domains (Blender, Audacity, Inkscape — bench/concern-proof) and the
  MetaBalls held-out tutorial are **burned**: they are SEEN and excluded.
- Freeze order (enforced by commit history): (1) compiler + packs frozen at a
  named commit; (2) selection performed by an agent who did not build the
  compiler; (3) selected tutorials verified absent from `watched/`, `proofs/`,
  and prior bench artifacts; (4) selection committed before any C3 compile.
- Domain candidate pool (final pick sealed at selection time, not here):
  UE 5.8 (disposable GUI project, per the 2026-08-01 engine-version rule),
  Blender 5.1 with an unseen workflow class, DaVinci/OBS-class desktop AV,
  spreadsheet/office automation, GIMP/Krita. At most one UE domain, so the
  suite is not engine-weighted.

## Repetitions and scale

3 repetitions × 4 conditions × 9 tasks = **108 scored runs**, plus negative
controls below. All runs reported; no best-run selection; failures published
with the same detail as passes (charter rule).

## Negative controls (each must FAIL closed to pass)

1. **Drift demotion**: after C3 passes a task, introduce deliberate target
   version drift; the pack must demote to `stale_unproven` and the run must
   refuse, not improvise. (Machinery exists — PR #15 proved it on a labeled
   fixture; this is its first non-fixture exercise.)
2. **Ambiguity reinspection**: one task per domain contains a predeclared
   ambiguous segment; C3 must show retained reinspection (v1 hard gate).
3. **Wrong-pack refusal**: present C3 with a validated pack that does not match
   the task; the run must scope/refuse rather than force-apply (claim-boundary
   gate exercised adversarially).

## Practice variants (generalization stage)

Each C3 task that passes gets 2 parameter-varied assertions (different values/
targets, same procedure class) — replaying the original is not generalization.
Variant results are reported separately; base-task success is never promoted to
`generalized` on variant failure.

## Frozen envelope (v1 list, plus)

Everything in v1 `frozen_envelope`, plus: judge model pinned by digest; Ollama
model versions recorded; ComfyUI/env snapshot per run via `env_snapshot`; the
same physical machine for all scored runs (Windows/5090). The clean-machine
reproduction pass (below) is the only cross-machine step.

## Budgets, costs, abort rules (frozen numbers — change requires re-review)

- Per-run wall-clock cap: 45 min (C3 compile amortized separately, capped 90 min
  per tutorial). Suite cap: 5 nights of otherwise-idle time.
- Cloud spend: $0 — local models only; any cloud/paid call trips the
  `authorized_actions` gate and halts the suite.
- VRAM: every run behind `beast resource-check`; a denial reschedules, never
  forces; never terminate a user process.
- Abort the suite (not just the run) on: 2 consecutive infrastructure failures,
  any envelope drift detected mid-suite (env_snapshot diff), any unauthorized-
  action trip, or user interrupt. Aborts are published like results.

## Reproduction and reporting

- Independent clean-machine reproduction of at least one passing C3 task per
  domain (fresh worktree + fresh env; Spark-1 where the target app permits,
  otherwise a fresh Windows environment) by an agent who did not run the suite.
- Report: every run, all metrics from v1 `metrics`, per-condition medians and
  ranges, hard-gate pass rates, unsupported-claim counts, and a single primary
  comparison table C3 vs C2 vs C0 — the SkillsBench question first.
- Promotion rule: v1 rule, extended — C3 must additionally not lose to C2 on
  the predeclared primary correctness metric, or the result is reported as
  "curated skills suffice; Beast machinery unjustified at current maturity."
  That sentence appears verbatim in the report if it is the outcome.

## What this document is not

Not evidence. Not a result. Not a promotion. The claim boundary of v1 stands:
this defines the experiment; only retained run evidence can decide it.
