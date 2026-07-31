# Recipe — Motion-graphic video (HyperFrames)

**Use for:** short punchy MP4s — kinetic type, stat hits, logo stings, image-hero
cinematics, explainer clips, social cuts. HTML/CSS/GSAP in, deterministic MP4 out.
**Tools:** `/hyperframes` router skill (installs the right workflow on demand) +
`hyperframes` CLI. Renders locally in 10–20s on the 5090. Free, Apache 2.0.

## The iron rule
Never write composition HTML freehand — enter through `/hyperframes` and let the route's
director/builder contract drive. The contract (paused seek-safe GSAP timeline on
`window.__timelines`, `class="clip"` + `data-start/duration/track-index`, deterministic
code only) is what makes renders frame-exact; freehand HTML fails `check` and wastes loops.

## Order of operations
1. `/hyperframes` → route the brief (kinetic type → `/motion-graphics`; site promo →
   `/product-launch-video`; topic explainer → `/faceless-explainer`; deck → `/slideshow`)
2. Director plans `shot-plan.json` (beats, palette, metaphor) → builder composes from
   catalog blocks (`hyperframes add <block>`) — reuse-first, hand-author only gaps
3. Gates, in order: `hyperframes lint` → `hyperframes check` (runtime/layout/motion/WCAG)
   → `hyperframes snapshot --at <beat times>` → inspect the contact sheet BEFORE rendering
4. `hyperframes preview` (Studio, hot-reloads) for human review; iterate by editing HTML
5. `hyperframes render . -q high -o renders/video.mp4` (or `--format webm` for
   transparent overlays)

## Using a hero image (cinematic Ken Burns)
Oversized plate `<img>` + one full-duration `fromTo` scale/pan with `transform-origin`
locked on the focal point; endpoint math keeps image edges off-canvas. Glow accents as
`mix-blend-mode: screen` layers anchored INSIDE the plate so they track the camera.
Text over image needs a scrim + text-shadow — `check` enforces WCAG AA and it will catch you.

## Hard-won gotchas (2026-07-31, hyperframes 0.7.86)
- Main composition lives at project ROOT `index.html`; `compositions/` is for
  sub-comps/blocks only. "No composition found" = wrong location.
- Run `hyperframes init <name>` from the parent dir with a bare name — a nested path
  can silently scaffold nothing while printing the success epilogue. Verify files exist.
- `radial-gradient(circle, ...)` defaults to farthest-corner → discs render as squares.
  Use `circle closest-side` for soft-edged suns/orbs.
- ffmpeg must be on PATH for render/snapshot (winget install puts it in
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg...\bin`).
- Studio previews: `npm run dev` is long-running — background it; ports auto-increment
  3002, 3003… one server per project.

## Quality gates
- [ ] `lint` 0 errors; `check` passed including contrast (WCAG AA)
- [ ] Contact-sheet frames inspected at opening, signature move, final hold
- [ ] One metaphor per piece, scenes partition the full duration on a beat grid
- [ ] Render verified: file exists, duration matches, no blank tail frame
