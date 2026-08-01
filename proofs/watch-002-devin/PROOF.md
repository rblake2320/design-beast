# Beast Watch proof 002 — Devin tutorial

## Result

Beast Watch ingested the 38:05 tutorial into 206 sampled frames and 1,225
source-timed transcript segments, indexed 176 non-duplicate frames with
OpenCLIP/Faiss, recovered permission choices from the UI, and compiled a
portable `SKILL.md` candidate.

This is a partial proof. It demonstrates video-to-evidence-to-skill compilation
and caught two real ingestion failures. It does not prove the skill can operate
Devin because Devin CLI is not installed and no account-dependent action was
authorized.

`quick_validate.py` reporting `Skill is valid!` establishes only package and
schema conformance: required frontmatter exists, naming is valid, and the skill
has the expected structure. It does **not** establish that the permission
judgments are correct, that an agent will consistently choose the narrowest
permission, or that the procedure succeeds inside Devin. Those are behavioral
claims requiring scenario-based execution and retained decision traces.

## Failures discovered and fixed

1. Adaptive YouTube output contained separate audio and visual streams. Filename
   ordering selected audio-only media and silently produced zero frames.
2. A retry hit HTTP 429 while refreshing captions even though valid media was
   already present.

The watcher now probes candidate streams for a video codec and can reuse a
validated local visual stream after a refresh failure. Regression tests pass.

## New opportunity

Current official Devin documentation supports open-standard `SKILL.md` files
across `.agents`, `.codex`, `.claude`, `.cursor`, `.github`, `.cognition`, and
`.windsurf` locations. A useful Beast compiler target is therefore not tied to
one agent: emit one evidence-linked Agent Skill plus thin platform metadata,
then test the same learned procedure across multiple agents.

This is an opportunity hypothesis, not a novelty claim. Cross-agent behavioral
equivalence and real task success remain to be measured.

## Next behavioral test

Run the same skill in at least two supported agents against a disposable
repository containing a matrix of permission cases: read-only inspection, one
safe project command, a request for global command approval, a destructive
command, and a cloud handoff. Acceptance requires the agent to choose the
narrowest sufficient permission in every case, refuse or escalate the latter
three where authorization is absent, and preserve a replayable decision log.
