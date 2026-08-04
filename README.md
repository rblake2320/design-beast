# Design Beast 🦬

**Other agents answer. Beast watches how, proves it can, and keeps the capability.**

Design Beast is a verified capability engine for demonstrated work—especially
visual information in tutorial video that transcripts cannot contain. It connects
image, video, audio, 3D, game, and web tools to agents through skills, CLIs, MCP,
evidence gates, recovery checkpoints, and live resource admission.

The point is not "can generate an image." Every tool here can. The point is closing the
gap between *AI output* and *the showcase-quality work people actually post*. That gap is
workflow, not model — and this repo encodes the workflow.

## The rules that make output good

1. **Never one-shot.** Generate 4+ candidates, judge, pick, refine. See
   [`design-system/QUALITY-LOOP.md`](design-system/QUALITY-LOOP.md).
2. **Never freehand a prompt** for anything that matters. Use a recipe card from
   [`design-system/recipes/`](design-system/recipes/) — structured subject / composition /
   lighting / lens / mood anatomy.
3. **Use purpose-built modes over raw prompts.** Higgsfield product-photoshoot modes,
   Marketing Studio, Nano Banana reference edits, Soul ID — these are why posted images
   look posted.
4. **Refine is half the work.** Winner gets an edit/inpaint pass, upscale, and grade
   before anyone sees it.

## Map

| Path | What |
|---|---|
| `BEAST.md` | Canonical Beast loop, evidence contract, anatomy, and operational invariants |
| `beast/` | Machine-readable capability graph, resource policy, pack schema, and active packs |
| `design-system/` | QUALITY-LOOP.md + recipe cards (incl. motion-graphic-video, game-look-pass — the anti-Roblox loop) |
| `skills/game-content-pipeline/` | Full 2D/3D/game pipeline skill (Blender ⇄ UE ⇄ Higgsfield) |
| `docs/STACK.md` | Complete tool inventory: what's installed, verify dates |
| `docs/SETUP.md` | Rebuild the whole stack from zero, lane by lane |
| `docs/CAPABILITY-MATRIX.md` | Everything we can do vs the field, with receipts |
| `docs/WIN-PLAN.md` + `COMPETITIVE-LANDSCAPE.md` + `COSTS-BASELINE.md` | Strategy: scoped moves, rivals' pain, defensible cost claims |
| `docs/CONTENT-POLICY-ARCHITECTURE.md` | Neutral platform: registry-routed policy, BYOK, legal floor |
| `docs/PIPELINES.md` | End-to-end recipes: image → 3D → UE, sprites, sites, video |
| `docs/OPPORTUNITY-LEDGER.md` | Evidence-first discovery protocol + parked openings |
| `studio/` | The API: jobs, GPU leases, judge loop, provenance manifests, env snapshots, chained ledger, backend registry |
| `scripts/` | doctor · validation/operator status · resource admission · recovery · Watch and evidence gates |
| `bin/beast.ps1` | CLI: `beast doctor · validate · status · resource-check · checkpoint · recover · watch · watch-validate` |
| `requirements*.txt` | Reproducible Studio runtime and test dependencies |
| `repos.yml` | Linked project repos (incl. vigil, hyperframes, ai-content-engine) |
| `mcp/mcp.template.json` | MCP wiring template (Blender :9876, UE :8000/mcp, magic) |

## Beast Studio (the UI)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe studio\server.py     # → http://localhost:8787
```
Brief + variations in a form, candidates stream into a grid with judge scores, winner
gets badged and auto-graded. Runs land in `studio/runs/<id>/` (final.png = deliverable).

## Quickstart

```powershell
# 1. Verify the whole stack (Blender bridge, UE, Higgsfield auth, ffmpeg, rembg, disk)
.\bin\beast.ps1 doctor

# Validate capability claims/packs and inspect current VRAM admission
.\bin\beast.ps1 validate
.\bin\beast.ps1 status

# 2. Pull the sibling repos this hub orchestrates
powershell -File scripts/sync_repos.ps1

# 3. Pick a recipe and go
Get-ChildItem design-system/recipes
```

### Watch and learn from tutorials

```powershell
.\bin\beast.ps1 watch tutorial.mp4 --start 12:00 --end 18:00
.\bin\beast.ps1 watch tutorial.mp4 --dense-window 12:04-12:12@4
.\bin\beast.ps1 watch-seek watched\tutorial --at 12:08 --level 2
.\bin\beast.ps1 watch-index watched\tutorial
.\bin\beast.ps1 watch-index watched\tutorial "Unreal material editor"
```

Watch v2 combines scene changes, periodic safety samples, targeted dense
reinspection, source-aligned transcripts, perceptual deduplication, and optional
OpenCLIP/Faiss semantic search. Its evidence and validation contract is designed to
compile tutorials into practiced Unreal/Python/MCP skills rather than summaries.
See [`docs/WATCH-LEARN.md`](docs/WATCH-LEARN.md).

The Watch publication contract now requires frame-linked visual-only facts and
real reinspection references for ambiguous segments. Parsing captions alone cannot
pass the watching gate.

## Domains this covers

- **Images** — Higgsfield CLI (GPT Image 2, Nano Banana 2/Pro, Soul ID) + quality loop
- **Video** — Seedance 2.0, Kling 3.0, Marketing Studio, ffmpeg assembly
- **3D** — Blender 5.1 (50-tool MCP bridge), image-to-3D (Tripo / Hunyuan3D / TRELLIS.2)
- **Game** — Unreal Engine 5.8 (first-party MCP via BeastLab) + 5.6.1 (`/api/to_ue`
  → RouteRush imports), Paper2D/PaperZD, packaging
- **Web / sites** — frontend-design, impeccable, theme-factory, dataviz skills; magic MCP
  (21st.dev components); real design systems, not screenshots
- **Faces / avatars** — NVIDIA ACE (Audio2Face-3D), Soul ID identity training
