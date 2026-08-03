# Beast Reflection approved-change execution — 2026-08-03

Base decision: `BR-APPROVALS-20260803.md`.

## Applied

- **BR-005:** execution started by fetching and fast-forwarding local `main` to
  approved commit `297a9d02560bec546c2690703d76319608dc3a36` before editing.
- **BR-001:** repository scope is now the collector default. It recognizes the
  repository and registered Git worktrees, excludes unrelated sessions, records
  exclusion counts, and reserves `--scope global` for explicit user-wide review.
  A named `--include-session` override supports manually reviewed parent-root
  threads; the override is recorded and forbidden for nightly automation.
- **BR-003:** the durable claim boundary in the approval file remains unchanged:
  practical MetaHuman facial reproduction is proven; the stricter predeclared
  `DEFORMATION_MEASURED` gate remains rejected.

## Validation

- Focused reflection tests: `7 passed`.
- Full suite: `199 passed, 7 deselected`.
- Skill package: valid.
- Real 24-hour manual run:
  - scope: `repo`
  - one explicitly named parent-root Design Beast session included
  - 70 messages retained
  - 11 messages across two unrelated sessions excluded
  - zero parse errors and zero truncations
  - repository HEAD: `297a9d02560bec546c2690703d76319608dc3a36`
  - receipt: `38ad92f92c4c8bfed83e`
  - bundle fingerprint:
    `779870e6430104dcbb207b5812a6196353badc9950875da273a62ff7b9c664ac`
  - newest retained event age at completion: 52.8 seconds

The first default scoped run retained zero messages because the active Codex
thread was rooted at the broad parent `C:\Users\techai\brain`. That run was not
accepted as the manual validation. The explicit session override was added and
tested so manual parent-root work is auditable without weakening default scope.

## Automation boundary

The BR-001 implementation and clean manual freshness run are complete. A nightly
Automation is now eligible for separate user-authorized setup, but has not been
created. Nightly execution must start in this repository, use no session override,
and produce a new completed receipt with `repo` scope, current HEAD, recent source
activity (or an explicit no-activity result), a new receipt ID, and a new bundle
fingerprint. Scheduler success without that receipt is failure.

BR-002 and BR-004 remain deferred and were not changed.
