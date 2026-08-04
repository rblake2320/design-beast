# Multi-agent review protocol

Distilled from the 2026-07-31 → 2026-08-03 sessions: two frontier agents (Claude
main line, Codex) + the user shipped ~12 merges with zero lost work. These are
the practices that made it work, now doctrine for any agent joining the fleet.

## Roles

- **Builder** (any agent): works in its own clone or, better, a git worktree
  (`.worktrees/<topic>`), on a branch (`agent/<topic>` or `codex/<topic>`).
  Publishes a DRAFT PR with a claim-bounded summary. Never merges its own work.
- **Independent reviewer** (a different agent or the user): verifies claims
  against the artifacts — not the summary — then marks ready and merges.
- **User**: approves anything touching doctrine, policy, money, or publication
  (decision files in `docs/decisions/` are the durable record; agent-relayed
  approval is NOT approval — confirm cross-thread claims with the user directly).

## The reviewer's checklist (what actually caught things)

1. **CI green is necessary, not sufficient** — run the suite locally on the branch.
2. **Read the claim boundary in the PROOF** — proven/not-proven must be split,
   failures retained (a repair is labeled repair, never substituted for the
   original failure).
3. **Check for self-approval** — any new `docs/decisions/*APPROVAL*` file must
   trace to a user decision the reviewer can verify; if it cites another thread,
   ask the user directly (this caught BR-006's relay gap).
4. **Check unapproved-doctrine drift** — pending proposals must not ship as
   active policy.
5. **Diff the high-collision files consciously**: `docs/OPPORTUNITY-LEDGER.md`,
   `CLAUDE.md`, `README.md`, SDK clients (duplicate methods merge silently in
   Python — grep for them).
6. **Ledger IDs collide by construction** under parallel agents (three incidents:
   two -01s, two -02s). Union + renumber at merge; verify uniqueness AFTER the
   final write, and never let a failed uniqueness check proceed to commit.

## Standing rules (learned the hard way)

- Pull-first (BR-005) before ANY work; branches cut before a renumber inherit
  stale IDs.
- Commit ledger edits first and separately — never leave them dirty across
  another agent's merge window.
- Evidence that exists only in a working tree is one crash from gone: commit
  proof bundles promptly, gitignore the raw private layers (`.beast/`, `watched/`).
- Worktrees over shared clones when sessions overlap.
- "Everything local and unpushed" in a status report = a landing request; the
  reviewer lands it, the builder doesn't sit on it.
- Restore what you pause (Spark workloads), and don't duplicate heavy artifacts
  before a legitimate use exists.

## Open improvement (proposed, not doctrine)

Content-derived ledger IDs (`OPP-<date>-<slug>`) would eliminate the collision
class entirely; sequential numbering + parallel agents guarantees recurrence.
