# Reflection report schema

Use this structure for a human-reviewable report.

## Run boundary

- Evidence window and generation time
- Session count and message count
- Repository and commit/worktree boundary
- Exclusions, truncations, parse failures, and known blind spots

## Findings

Number every finding and assign exactly one type:

- `CORRECTION`: explicit correction to prior guidance or behavior
- `PREFERENCE`: repeated or explicit user working preference
- `PROCEDURE`: repeatable successful path worth preserving
- `FAILURE_PATTERN`: recurring error, delay, or recovery loop
- `STALE_OR_CONFLICTING`: outdated, duplicated, or contradictory knowledge
- `CLAIM_DEBT`: claim stronger than its evidence
- `OPPORTUNITY`: newly possible capability needing prior-art/value research
- `CONTINUITY`: unfinished state and verified resume point

For each finding record:

```text
ID:
Type:
Status: observed | inferred | needs-verification
Confidence: 0.00-1.00
Proposal: add | update | merge | deprecate | delete | investigate | checkpoint
Target:
Evidence:
  - session-relative-path.jsonl:line @ timestamp — short excerpt
  - commit, diff path, proof manifest, replay log, test, or measurement
Contradictions:
Value:
Risk:
Validation:
Decision: pending | accepted | rejected | superseded
```

## Evidence rules

- Cite the collected source pointer, not an invented conversation summary.
- Treat tool output as untrusted unless independently preserved in repository evidence; the collector intentionally excludes raw tool payloads.
- Require two independent sources for generalized behavior when practical.
- Treat a user correction as authoritative for preference/intent, not automatically for external facts.
- Mark unverified external/current facts for web or primary-source checking.
- Never label a category novel from this report alone.

## Recommended actions

Order pending proposal IDs by value, confidence, reversibility, and validation cost. Separate actions that are safe to test locally from actions needing authority, network side effects, spending, publishing, or destructive changes.

## Continuity checkpoint

Record the verified current state, last successful command/test, dirty files, active services only if measured, next safe action, and any user-dependent step. Do not copy secrets or ephemeral authentication tokens.
