---
name: beast-reflection
description: Consolidate recent Codex sessions and repository evidence into a reviewable, evidence-linked improvement report. Use after long or multi-session work, before updating AGENTS.md/CLAUDE.md or skills, when repeated errors or stale guidance may exist, when preparing a recovery checkpoint, or when scheduling a nightly/weekly Codex reflection automation.
---

# Beast Reflection

Turn recent work into proposed durable knowledge without pretending to train model weights or silently rewriting authority files.

## Collect evidence

Run the deterministic collector before reasoning over sessions:

Resolve the collector relative to this `SKILL.md`, then run:

```powershell
python <this-skill>/scripts/collect_reflection_evidence.py --repo <repo> --since-hours 24
```

The command prints only the output path and counts. Its JSON output is private working evidence: keep `.beast/reflection/` ignored and never commit it. The collector:

- streams Codex JSONL instead of loading it into memory;
- keeps user and final-agent messages, not reasoning or tool payloads;
- redacts common secret forms and truncates oversized messages;
- deduplicates repeated events;
- records source file, line, timestamp, and content hash;
- inventories recent commits, worktree changes, and proof/document artifacts.

Use `--sessions-root` when `CODEX_HOME` is nonstandard. Increase `--since-hours` only when the evidence window is genuinely needed.

## Reflect

Read the generated evidence JSON. Produce a report using [references/report-schema.md](references/report-schema.md). Look across sessions and repository signals for:

1. explicit user corrections and repeated preferences;
2. recurring failures, slow paths, and successful recovery paths;
3. stale, duplicated, or conflicting instructions and skills;
4. claims whose evidence level is overstated;
5. reusable procedures worth compiling into or improving a skill;
6. newly opened opportunities that warrant research;
7. incomplete work and the smallest verified recovery checkpoint.

Distinguish observed evidence from inference. A repeated statement is not automatically true; it is stronger evidence of a preference than of an external fact.

## Gate changes

Write proposals first. Do not directly edit memory, `AGENTS.md`, `CLAUDE.md`, skills, opportunity ledgers, or proof claims during an unattended reflection run.

Each proposed change must include:

- target file or knowledge record;
- exact proposed addition, update, merge, deprecation, or deletion;
- source pointers and short evidence excerpts;
- confidence and contradiction status;
- expected value and regression risk;
- a validation step.

Only apply proposal IDs explicitly approved by the user. After approval, make minimal edits, run relevant validation, and record accepted/rejected outcomes so rejected suggestions are not repeatedly resurfaced without new evidence.

Creating a new timestamped evidence bundle or report is safe. Formatting/index repair may be proposed as low risk, but must not be auto-applied merely because the video workflow allowed it.

## Schedule safely

Prefer a Codex Automation that invokes this skill and deposits the report in a review queue. Local automation is also possible with `codex exec`, but the computer must be awake and authenticated.

Use a fresh reflection context, read-only access where practical, and no external messages or pushes. Never pass `--dangerously-bypass-approvals-and-sandbox` to an unattended reflection.

Start with a manual run. Schedule it only after the report is useful and false-positive rates are measured.

## Measure improvement

Do not claim the system became smarter from report generation alone. Compare before/after performance on repeated tasks using correctness, retries, tool calls, elapsed time, and regressions. Upgrade the claim only when the accepted memory/skill change improves those measurements.
