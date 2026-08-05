# Beast generalization experiment

This directory is the staging area for the first non-pilot Beast-loop benchmark.
The benchmark is deliberately two-phase so implementation cannot be repaired after
seeing the hidden tasks and still be called held out.

## Phase 1 — independent implementation freeze

1. Merge the reviewed harness.
2. Fill an envelope JSON with exact model/provider/version, reasoning effort,
   agent harness, tools, target applications, hardware, budgets, intervention
   rules, and initial-state recipe. Empty, `TBD`, and `unknown` values are rejected.
3. With a clean worktree, run `beast_loop_custody.py freeze`, including the
   protocol, scorer, compiler, packs, and executors that the experiment will use.
4. Commit the freeze in its own draft PR. An independent reviewer verifies and
   merges it before selecting tasks.

## Phase 2 — sequestered task selection and sealed schedule

The agents that built or reviewed this machinery are **burned as selectors**, as
are every candidate domain and task pool discussed in their repository or mesh
traffic. Those candidates remain useful for pilots only and cannot support a
held-out claim.

After the frozen commit, tasks enter through one of two recorded paths:

1. the user supplies previously undisclosed task/tutorial sources as the trust-root
   selector; or
2. a context-isolated external selector deterministically samples a predeclared
   external pool using entropy that did not exist until after the freeze.

A fresh agent selector records its birth ID and attests that it has never read the
frozen Beast packs, Watch evidence, candidate-task mesh discussion, or burned pool.
Because the fleet shares one OS and GitHub identity, this attestation is a residual
trust boundary rather than hard access control; every resulting claim must say so.
The current fleet audits only after the registry is sealed.

Each selected task
must have a real source, a private oracle, a selection receipt, at least one
predeclared transcript-absent visual fact, and at least one predeclared ambiguous
segment. The oracle remains outside executor workspaces; the public seal contains
only its hash.

`seal` rejects the former generic `independent_reviewer` role. Registry schema v2
requires the selection method, authority receipt, selector identity/attestation,
and (for deterministic sampling) the post-freeze entropy receipt. It also requires
at least three domains, three tasks per domain, and the protocol's
three repetitions for all three conditions. It creates a randomized 81-run schedule.

## Execution and custody

Each run produces a row plus at least one hashed artifact receipt. `append-result`
accepts only the next sealed schedule entry and links it to the previous result hash.
Failures are appended exactly like passes. `verify-results --require-complete`
rejects missing, reordered, edited, cherry-picked, or artifact-less runs before the
scorer sees them.

Non-pilot `run_beast_loop.py` scoring requires `--seal` and `--artifact-root`.
Calling the scorer on a plain JSON array can exercise pilot analysis but can never
produce a promotable full report.

The first 81 runs can support only bounded generalization across the sampled domains.
They cannot establish “reliable everywhere.” A target-population reliability claim
requires at least 29 independently selected unseen tasks with zero Beast task-level
failures, giving a one-sided 95% exact lower success bound above 0.90. Every material
model, tool, pack, or target-version change creates a new envelope.

Primary methodology anchors:

- [NIST AI 800-3](https://www.nist.gov/news-events/news/2026/02/new-report-expanding-ai-evaluation-toolbox-with-statistical-models)
  distinguishes fixed-benchmark performance from generalized performance and
  requires uncertainty to match the intended claim.
- [NIST AITE](https://pages.nist.gov/ai-technology-evaluation/) uses blind data
  and sequestered evaluation to reduce contamination.
- [METR's autonomy evaluation resources](https://metr.org/blog/2024-03-13-autonomy-evaluation-resources/)
  retain private task implementations to reduce benchmark contamination.

These sources motivate the design; they do not validate Beast's implementation.
