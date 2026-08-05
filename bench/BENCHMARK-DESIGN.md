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
**Isolation (A2, strengthened 2026-08-05):** the curator is a **new,
context-isolated seat** — not a fork of a current seat — given only the selected
tutorial and the sealed acceptance criteria. It must have no access to Beast
packs, typed evidence, watch bundles, the mesh transcript, this design file, or
any protocol candidate list, and it writes its skill before any C3 compile
exists for that tutorial. Attestation recorded in the selection commit states:
curator birth_id, spawn timestamp, the briefing it received verbatim, and an
explicit declaration of no prior access to each of those categories. A curator
with any such exposure is burned for that task.

**Enforcement mechanism and residual risk (stated in the result, not hidden):**
every fleet seat operates under one GitHub identity and one host, so
attestation is a *procedural* control, not a cryptographic one — an
attestation cannot prove non-exposure the way a signature proves authorship.
The published result must name the mechanism actually used (fresh spawn +
briefing capture + commit-order evidence) and state the residual risk plainly:
isolation rests on process discipline and commit ordering, and a reader who
distrusts that should treat C2 as a weak comparator rather than a clean
control. Mesh-relayed claims of isolation are not evidence of isolation.

## Task selection (sealed, unseen)

- 3 materially different domains × 3 tasks, all driven by instructional videos
  that contain **predeclared visual-only facts** absent from their transcripts.
- **Sealed acceptance (review amendment A3):** per-task acceptance criteria,
  hard-gate parameters, and the predeclared visual-only facts are written and
  committed at selection time, BEFORE any C3 compile begins. The selection
  commit records selector seat + birth_id and curator seat + birth_id. Criteria
  changed after sealing void the task.
- Pilot domains (Blender, Audacity, Inkscape — bench/concern-proof) and the
  MetaBalls held-out tutorial are **burned**: they are SEEN and excluded.
### Sequestration repair (2026-08-05, blocking — supersedes the original rules)

The original design listed a domain candidate pool in this file and the fleet
discussed candidates over the mesh. **That disclosure burns them.** A pool
named by the seats that built the compiler is not held-out, and "the selector
did not build the compiler" is too weak when every current seat has read the
design, the packs, or the mesh transcript.

- **BURNED — pilot/training only, never held-out evidence:** the pilot domains
  (Blender, Audacity, Inkscape — `bench/concern-proof`), the MetaBalls held-out
  tutorial, and **every domain named in the superseded candidate pool of this
  file** (UE 5.8, Blender, DaVinci/OBS-class AV, spreadsheet/office, GIMP/Krita).
  Results on them may be reported as pilot or training data and never as
  held-out generalization.
- **No current seat may select.** claude 1/2/3 and codex 1 are all presumed
  contaminated for selection and curation until an audit proves otherwise.
- **Trust-root selection — one of two mechanisms, declared before the freeze:**
  1. **User-supplied (preferred):** the user provides previously undisclosed
     tutorial/task URLs *after* the compiler+scorer freeze commit. The user is
     the only trust root not derivable from fleet state.
  2. **Deterministic external-pool:** a predeclared external corpus plus
     post-freeze public entropy (a named future public value, e.g. a
     scheduled index close or block hash) seeds a deterministic selector.
     The entropy source and derivation are declared before it exists.
- **Freeze order (enforced by commit history):** (1) compiler + scorer frozen
  at an exact named commit; (2) selection mechanism declared; (3) tasks
  selected by the trust root *after* that commit; (4) task IDs, source hashes,
  acceptance criteria, selection method + seed, and timestamp sealed
  immediately in one commit; (5) selected tutorials verified absent from
  `watched/`, `proofs/`, and prior bench artifacts; (6) only then may any C3
  compile begin. The current fleet may audit only *after* the seal.

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
  per tutorial).
- **Budget arithmetic (review amendment A1)** — stated, not assumed:

  | Component | Count | Expected (est.) | Worst case (caps) |
  |---|---|---|---|
  | Scored runs | 108 | ~20 min avg → 36 h | 45 min → 81 h |
  | C3 compiles | 9 | ~45 min → 6.8 h | 90 min → 13.5 h |
  | Negative controls | ~9 runs | ~2 h | 45 min → 6.8 h |
  | Practice variants | ≤18 runs | ~6 h | 45 min → 13.5 h |
  | **Total** | | **~51 h** | **~115 h** |

  One tranche = 5 idle nights ≈ 40 h, which does NOT cover even the expected
  case. The suite therefore runs in **tranches**: when a tranche's time is
  exhausted, the suite HALTS, partial results are published (labeled partial,
  every completed run reported), and resuming the next tranche requires a
  **fresh explicit user gate**. Expected tranche count: 2 (expected case) to 3
  (worst case). No tranche may silently extend itself.
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
