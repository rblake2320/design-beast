# Adopted-tools freshness pass — 2026-08-04

First run of the monthly installed-vs-upstream sweep proposed after the
Impeccable finding (an adopted tool two skill generations stale, caught only
because a YouTuber made a video). Scope: version-bearing tools in CLAUDE.md's
tool access map and docs/STACK.md. Installed versions measured on this machine
today; upstream versions fetched live today unless marked unchecked.

## Results

| Tool | Installed | Upstream latest | Verdict |
|---|---|---|---|
| impeccable skill | 4.0.4 (upgraded today, owner-approved) | 4.0.4 | current — was 2026-04-28-era pre-worlds this morning; see OPP-20260804-10 |
| impeccable CLI (npm) | 3.5.0 | 3.5.0 (2026-07-30) | current |
| **@higgsfield/cli** | **0.1.35 (built 2026-05-09)** | **1.1.20 (2026-07-27)** | **SEVERELY STALE — worst finding of the pass** |
| hyperframes (npm) | 0.7.86 | 0.7.92 | slightly behind |
| ollama | 0.31.2 | 0.32.5 (2026-07-27) | behind — 0.32.x includes an NVFP4 output-quality fix relevant to local models |
| gh | 2.96.0 | 2.97.0 (2026-07-31) | one minor behind |
| yt-dlp | 2026.07.04 | 2026.07.04 | current |
| Blender | 5.1.2 | 5.1.2 is the 5.1-line latest; **5.2 LTS exists (2026-07-14)** | current-in-line; LTS jump available but NOT recommended blind — the :9876 MCP bridge lives inside Blender and compatibility with 5.2 is unverified |
| ImageMagick | 7.1.2-26 (2026-06-21 build) | unchecked this pass | — |
| ffmpeg | 8.1.2 (bundled build) | unchecked this pass | works; note below |
| node | 24.17.0 | — | fine |

## Notes and explanations

- **ffmpeg is not on the shell PATH** (`which ffmpeg` fails in bash and
  PowerShell) yet the watch pipeline works: `scripts/watch_video.py` resolves a
  bundled `ffmpeg-8.1.2-full_build/bin` internally via `_tool()`. Not a defect;
  recorded so the next agent doesn't chase it. Anything invoking bare `ffmpeg`
  from a shell will fail — use the bundle path or `beast doctor` to locate it.
- **gh version drift in docs**: the user-level CLAUDE.md gh-cli note says
  v2.88.0; the machine runs 2.96.0. Doc reference, not a tool problem.

## Recommended actions (owner-gated; none executed in this PR)

1. **@higgsfield/cli 0.1.35 → 1.1.20** — highest priority. Three months of
   vendor releases behind on a paid, auth-bearing tool that four higgsfield-*
   skills depend on. Upgrade needs an adoption gate: `npm i -g @higgsfield/cli`,
   re-auth check (`higgsfield auth login` may be required), then smoke one
   generation through each dependent skill before calling it adopted.
2. **ollama 0.31.2 → 0.32.5** — low risk, quality fix for NVFP4 local models.
3. **hyperframes, gh** — routine minor bumps, no gate needed beyond a smoke run.
4. **Blender 5.2 LTS** — decide deliberately: stay on 5.1.2 (bridge-verified)
   or schedule a bridge-compatibility test against 5.2 LTS in a disposable
   install. Do not upgrade the production install first.

## Method note

Evidence: installed versions = measured (command output, this machine, today);
upstream versions = fetched (npm registry / GitHub releases / vendor pages,
today). No ledger entry: this is maintenance reporting, not a new capability
door. Next sweep due ~2026-09-04, or immediately after any vendor
announcement touching an adopted tool.
