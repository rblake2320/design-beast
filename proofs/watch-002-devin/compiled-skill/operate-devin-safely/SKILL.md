---
name: operate-devin-safely
description: Prepare, operate, and validate Devin CLI or cloud coding workflows with explicit permission boundaries and replayable evidence. Use for Devin terminal setup, permission modes, AGENTS.md, skills, subagents, cloud handoff, PR review, schedules, or GitHub, Slack, and Linear integrations.
---

# Operate Devin safely

Treat tutorial observations as candidates, not current truth. Read
`references/evidence-map.md` when exact commands, source times, or version drift
matter.

## Establish the boundary

1. Inspect the repository, git state, available tests, and `AGENTS.md` files.
2. Check whether `devin` exists and record `devin --version`; do not install or
   authenticate unless the user asks.
3. Classify the requested work:
   - local read-only discovery;
   - local file or command mutation;
   - cloud session, PR, integration, schedule, secret, or paid usage.
4. Require explicit authorization before the third category. Never infer it from
   a request to learn, explain, prepare, or test a tutorial.

## Prepare durable instructions

1. Prefer a focused `SKILL.md` for a repeatable procedure and `AGENTS.md` for
   always-on repository context.
2. Discover existing instructions before adding new ones; preserve their scope.
3. Record exact setup, test, build, and validation commands from the repository,
   not guesses from the tutorial.
4. Put safety-critical workflows in a user-triggered skill when the target agent
   supports trigger controls.

## Run locally

1. Begin with the most restrictive permission mode that can complete the task.
2. Approve a command once until its behavior and scope are known.
3. Grant persistent command permission only for a narrow executable and project;
   avoid global allow rules when a project rule is sufficient.
4. Do not use bypass/YOLO mode for unreviewed repositories, install scripts,
   destructive operations, credentials, releases, or external systems.
5. Use subagents only for independent tasks with non-overlapping ownership.
   Validate every result in the parent session; parallel completion is not proof.

## Hand off to cloud

1. Verify a clean or intentionally dirty git state and identify the exact branch.
2. State which repository content, conversation context, and task will leave the
   local machine.
3. Confirm account, repository access, expected cost, and desired PR behavior.
4. Ask for explicit approval, then use the installed CLI's current help or
   official documentation to determine the handoff command.
5. Record the returned session URL or ID, branch, commit, commands, tests, and PR.

## Validate

Require evidence proportional to the work:

- structural: expected files, diffs, settings, branch, and artifacts exist;
- behavioral: relevant commands and tests exit successfully;
- visual: inspect rendered UI when appearance is part of the task;
- external: confirm the intended session, PR, issue, or schedule exists without
  broadening its scope.

Report observed facts separately from official verification and executed proof.
Call unsupported or account-dependent steps `not executed`, never `validated`.
