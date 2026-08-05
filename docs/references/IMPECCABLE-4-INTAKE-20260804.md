# Impeccable 4.0 intake — 2026-08-04

Upstream upgrade review of the impeccable design skill (already in our tool map,
CLAUDE.md rule 4 and the web-components row). Triggered by
https://www.youtube.com/watch?v=RVeCbPg0liw ("The #1 Claude Code Design Skill
Just Got a HUGE Upgrade").

Evidence: full beast watch — `watched/RVeCbPg0liw`, 130 frames / 964 caption
segments, fingerprint `e46551355eaf9bc00dcb2c89c7ed6f52e59320ccb317ed2d4859b69ebf400e01`.
Frame citations below are `f_<ms>` in that bundle. Release/npm facts were
fetched live 2026-08-04.

## What 4.0 adds (verified)

- **Worlds.** Human-reviewed complete graphic systems dealt as challengers
  against the model's own idea; the hand is "dealt live from the 177
  highest-rated worlds in the deck by the same roll API the skill uses," with
  on-page roll/pool hashes and a DEAL AGAIN control (impeccable.style/#worlds,
  f_000000095000). Release notes say 188 reviewed worlds in the deck as of
  skill 4.0.4; the deal pool is the 177 highest-rated. Direction selection uses
  randomized seeding rather than model preference (4.0.4, 2026-07-30).
- **Live decision page.** `impeccable init` opens a localhost picker: the roll
  assigns one world, alternates are shown with palette chips and an explicit
  risk line each (e.g. "Reads as crime-drama kitsch if the props outshine the
  analysis"), plus Build this / optional steer / re-roll (f_000000375000).
- **Live mode (matured).** Bottom overlay bar on the running site: Pick
  element, Insert, Detect (slop rules on an existing page), DESIGN.md panel
  (VISUAL/RAW, named tokens with hex + prose intent), page-level steer prompt,
  mic input. A picked element takes a freeform prompt or a command domain and
  1–4 variations; review UI has per-variation tuners (e.g. tilt, stamp border),
  then Accept returns the choice to the terminal session, which polls live-mode
  events (f_000000595000, f_000000665000). Demo live server ran on
  127.0.0.1:4750; the worlds picker on 127.0.0.1:51905 — ports are per-session.
- **Automatic job detection** (blank slate / redesign / addition / refinement)
  per the 4.0 release notes, 2026-07-22. Not demonstrated distinctly in the
  video; observed in release notes only.
- **Finish reviewer.** After a build, a separate fresh-context subagent
  ("impeccable finish reviewer") re-checks the result for slop patterns
  (narration ~08:20; terminal output observed on screen ~07:33).

## Baseline facts (verified against frames)

- Repo `github.com/pbakaus/impeccable`, Apache-2.0. README: "1 skill,
  23 commands, live browser iteration, and 59 deterministic detector rules,"
  and credits Anthropic's frontend-design as the starting point
  (f_000000169017). GitHub badge on impeccable.style showed 48k stars.
- Slop catalog: 64 patterns exposing AI defaults/production defects; the
  deterministic detector covers 59 rules across source and rendered pages; five
  broader judgments remain LLM-only in `/impeccable critique`
  (impeccable.style/slop/, f_000000235000).
- **Version split (gotcha).** npm package `impeccable` is the CLI — latest
  3.5.0 (2026-07-30, verified via `npm view`). The *skill* payload is versioned
  separately: 4.0.4. "Impeccable 4.0" refers to the skill line.

## Narration vs screen (kept honest)

- Narration "about 50,000 stars" — badge showed 48k.
- Narration "port 4610" — URL bar showed 127.0.0.1:4750.
- Narration "177 different design templates" — site text: deck of 188 reviewed
  worlds, hand dealt from the 177 highest-rated.

## Higgsfield wiring

The video routes worlds imagery through the Higgsfield MCP. The
higgsfield.ai/mcp Claude Code tab itself states: "If you are using Claude Code
or Codex, it's better to use the CLI," and its Claude Code setup is CLI-based
(`npm i -g @higgsfield/cli`, `higgsfield auth login`,
`npx skills add higgsfield-ai/skills`) (f_000000305000). This matches our
existing CLI-first Higgsfield lane; no MCP adoption needed to use worlds with
our stack.

## Local state and adoption gate

- Installed skill at `~/.claude/skills/impeccable` is dated 2026-04-28 and has
  no worlds references — pre-4.0 by roughly two skill generations.
- Pre-upgrade backup taken: `C:\Users\techai\claude-skills-backups\impeccable-pre4-20260804`.
- Upgrade executed 2026-08-04 after owner approval:
  `npx impeccable skills install -y --providers=claude --scope=global` from a
  non-repo directory reported "Updated 1 skill(s) to v4.0.4". Warning, observed
  2026-08-04: bare `npx impeccable install` run inside a repo defaults to a
  *project* `.github` install — it wrote `.github/{agents,hooks,skills}` into
  design-beast and was removed the same session.
- File-level verification (done 2026-08-04): SKILL.md carries `version: 4.0.4`
  and references worlds; `reference/` grew to 36 files including `live.md` and
  `live-setup.md`. The installer's "hooks" are scripts inside the skill
  directory (`scripts/hook*.mjs`), not edits to `~/.claude/settings.json` —
  no global harness behavior changed without project opt-in.
- Runtime verification (pending, attended): run `/impeccable init` on a
  throwaway project and confirm the worlds decision page opens locally and one
  accepted live-mode element variation round-trips to the terminal session.
  This needs a human in the browser; the ledger claim stays unproven until it
  passes.

## Routing

Adopted tool maintenance, not a consolidation move: impeccable stays the
website lane owner per CLAUDE.md rule 4; design-beast's quality loop and
Higgsfield lane are unchanged. The worlds mechanism is convergent with our
multi-candidate → judge philosophy and its roll/pool receipts echo our
provenance culture — worth citing as prior art next time we design a
direction-selection step. See ledger OPP-20260804-01.
