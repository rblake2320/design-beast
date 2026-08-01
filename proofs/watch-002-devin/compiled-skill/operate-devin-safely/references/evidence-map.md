# Evidence map

## Video observation

Source: `https://www.youtube.com/watch?v=GFlFABWeqDc`, Tech With Tim,
uploaded 2026-05-18. Bundle: `watched/proof-002-devin-full-tutorial`.

| Topic | Source time | Observed evidence | Confidence |
|---|---:|---|---|
| Permission modes | 00:08:33–00:09:50 | `/mode` exposes normal, accept-edits, and bypass; Shift+Tab cycles modes | video + captions |
| Command approval | 00:17:18 | UI offers approve once, global executable allow, project-scoped executable allow, or deny | visual frame at 00:17:18 |
| AGENTS.md | 00:17:23–00:20:16 | Root instructions are loaded into later sessions | demonstrated, but presenter says “trust me”; independently verify |
| Subagents | 00:21:30–00:26:43 | Parallel landing-page variants are delegated and later inspected | demonstrated result, not an isolated benchmark |
| Cloud handoff | 00:28:01–00:30:12 | Git repo and provider connection precede `/handoff`; cloud session creates a PR | account-dependent demonstration |

The tutorial displays Devin for Terminal `v2026.5.6-4`. Treat commands and UI as
version-sensitive.

## Current official verification (checked 2026-07-31)

- CLI index: `https://docs.devin.ai/cli/index`
- permissions: `https://docs.devin.ai/cli/reference/permissions`
- rules and AGENTS.md: `https://docs.devin.ai/cli/extensibility/rules`
- skills: `https://docs.devin.ai/product-guides/skills`
- subagents: `https://docs.devin.ai/cli/subagents`
- handoff: `https://docs.devin.ai/cli/handoff`

Official docs now describe repository `SKILL.md` files using the open Agent
Skills standard. This capability was not covered in the tutorial and is the
reason this compiled artifact is a skill rather than only an AGENTS.md file.

## Proof boundary

On the proof machine, `devin` was not installed. The video ingestion, visual
reinspection, skill compilation, and static validation were executed. Devin
authentication, paid usage, cloud sessions, repository connections, PRs,
integrations, schedules, and secrets were not executed.
