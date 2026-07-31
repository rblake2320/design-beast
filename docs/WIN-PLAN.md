# Win plan — scoped moves, 2026-07-31

Every move from COMPETITIVE-LANDSCAPE.md scoped: what exists, what to build, effort,
and a measurable win condition. Effort in agent-days (one focused Claude Code session
≈ 0.5-1 day). Sequencing at the bottom. Companion: ROADMAP.md owns reliability items;
this file owns competitive differentiation.

---

## 1. Exact-replay manifests — kill ComfyUI's reproducibility pain
**Size: S (1-2 days) · finishes ROADMAP P0 provenance · do first**

- **Exists:** per-run `manifest.json` with artifact SHA-256, params, workflow id,
  model/source, local seeds (test_provenance.py). Gap named in ROADMAP: no env
  digests, no exact Comfy graph hash.
- **Build:**
  1. At job start, snapshot: `pip freeze` hash of the Comfy venv, ComfyUI commit,
     every custom node's commit SHA, model file SHA-256s (cache by mtime), full
     submitted graph JSON hash. Write into manifest.
  2. `beast replay <run-id>`: diff current env vs manifest, report drift precisely
     ("node X moved a1b2→c3d4; torch 2.7.1→2.8.0"), then re-run and compare artifact
     hashes.
  3. Env drift check wired into `doctor`.
- **Win condition:** same-machine replay reproduces bit-identical (or documented-
  nondeterminism-only) output; cross-machine replay names every drifted component.
  ComfyUI can't do this; we embed ComfyUI and can.

## 2. Local style-LoRA training — take Scenario's moat onshore
**Size: L (5-8 days) · the single most-paid-for feature in the game-asset market**

- **Exists:** 5090 (32GB — trains SDXL/Flux LoRAs comfortably), ComfyUI + Flux
  local, llm-trainer skill (LoRA/QLoRA patterns), judge loop, recipes discipline.
- **Build (phased):**
  1. *Dataset prep* (1d): `beast style init <name>` — ingest 15-50 reference images
    (the art bible's images!), auto-caption via local VLM (qwen3-vl), crop/bucket.
  2. *Training* (2d): kohya-ss/sd-scripts or SimpleTuner behind a job type
     (`POST /api/style/train`), GPU-lease aware (heavy class), checkpoints +
     sample grid per epoch, judge scores samples vs reference set each epoch —
     auto-pick best checkpoint. Flux-LoRA first (matches installed base model).
  3. *Serving* (1d): trained LoRA registers as a backend variant
     (`flux-local+style:<name>`) in the model registry; recipes can pin a style.
  4. *Consistency gate* (1d): batch-generate 8 assets with the style, judge scores
     style-coherence pairwise; publish a consistency score per style pack.
  5. *Game bridge* (1-2d): style pack = the art bible made executable — game-look-pass
     recipe generates concept frames THROUGH the game's own style LoRA, so 2D concepts,
     textures, and UI all share one look. This chains into image→3D texturing.
- **Innovation on top:** *closed-loop art direction* — bible → LoRA → every generated
  asset judged against the bible → drift caught automatically. Scenario sells style
  consistency; nobody sells style *enforcement*. This is also the structural fix for
  "everything comes out looking Roblox."
- **Win condition:** train a "RouteRush look" pack from 20 concept frames; 10 assets
  generated through it score ≥8 style-coherence; a stranger sorts them into one game.

## 3. Native MCP server + capability discovery — own the agent-first lane
**Size: M (3-4 days) · ROADMAP P4 · ships before cloud players make agents default**

- **Exists:** 19-path REST API + OpenAPI (requests typed; responses not), Python/TS
  SDKs, SSE events, job DB, GPU leases. Agents today shell through HTTP.
- **Build:**
  1. MCP server (stdio + streamable-HTTP) wrapping the REST surface: tools =
     generate/refine/judge/style-train/to_ue/status; resources = runs, manifests,
     recipes, STACK; declare response models while at it (closes the OpenAPI gap).
  2. Capability discovery tool: returns the model registry (content classes, licenses,
     local/cloud, VRAM state, style packs) so any agent can plan without docs.
  3. Long-job pattern: MCP tool returns job id + SSE cursor; add `wait_for` tool.
  4. Register in mcp.template.json next to Blender/UE — one config gives an agent
     the whole creative machine.
- **Innovation on top:** the *judge as an MCP tool* means ANY agent (not just ours)
  can quality-gate its own outputs — "score this screenshot against this bible" as a
  primitive. Nobody offers vision-QA-as-a-tool.
- **Win condition:** a fresh Claude Code session with zero repo context completes
  brief → judged image → UE import using only MCP tool calls.

## 4. Local-first guarantees — weaponize their credit anxiety
**Size: S (1-2 days) · mostly product truth-telling, high leverage per hour**

- **Exists:** execution policy (cloud opt-in only), local Flux/LTX/Wan/TTS/music
  staged, honest-degradation habit in doctor.
- **Build:**
  1. `beast costs`: per-run ledger already knows backend — roll up "this month:
     N generations, $0 metered; equivalent on Krea/Runway/Higgsfield: $X" using a
     small price table. Provocative, factual, updates the pitch automatically.
  2. Verify the staged local video lane (LTX-2.3 + Wan 2.2 smoke renders) so the
     no-credit claim covers video — the category where credit anxiety is worst.
  3. README positioning block from COMPETITIVE-LANDSCAPE's closing sentence.
- **Win condition:** video generates locally end-to-end; `beast costs` prints a real
  dollars-avoided number after a week of use.

## 5. Policy tiers + crypto-first billing — be ready before the crisis
**Size: M (3-5 days now; processor integration deferred until SaaS is real)**

- **Exists:** CONTENT-POLICY-ARCHITECTURE.md (registry/routing/floor design),
  provenance attribution, allow_*_fallback flags as prior art for policy-as-config.
- **Build now (pre-SaaS):**
  1. Implement the model registry with content_classes + license fields (YAML next
     to repos.yml); router honors it; `E_BACKEND_POLICY` error with alternates.
  2. Tenant policy object in config (single-tenant today, N-tenant later) +
     per-request content-class tagging threaded through jobs.
  3. Judge-refusal detection: classify judge output as score vs refusal; on refusal,
     auto-reroute to next eligible judge and log — never emit a fake low score.
  4. BTCPay Server: deploy on the Hostinger VPS as a standing test instance wired to
     a sandbox store; invoice flow behind a feature flag. (Real processors: deferred.)
- **Win condition:** a mature-class request routes to an eligible backend while
  Higgsfield-class backends are skipped by policy, not by failure; a test invoice
  settles via BTCPay on testnet.

## 6. Self-serve operability — support as a non-issue
**Size: S (1 day, rolling)**

- **Exists:** doctor, degradation notes, AGENT_ACCESS.md, CLAUDE.md manual.
- **Build:** doctor --fix for the top 5 failures (ffmpeg PATH, Blender bridge down,
  Comfy venv drift → replay diff, stale skills, MemoryWeb down); every E_* error
  carries a runbook link; docs/RUNBOOK.md generated from real failures as they occur.
- **Win condition:** the three failures we hit TODAY (init silent-fail, ffmpeg PATH,
  torch pin conflicts) each resolve from the error message alone.

---

## The two genuinely new things (nobody in the landscape has either)

- **A. Vision-gated creative CI** — the game-look-pass loop generalized: every
  pipeline (game, site, video, image) ends with a screenshot/frame judged against a
  bible, wired as a *gate* (like tests), exposed as an MCP primitive (move 3) and
  fed by style packs (move 2). Competitors do generation; none do enforcement.
- **B. Beast packs** — a style LoRA + recipe + env lockfile + judge rubric bundled
  as one shareable, *exactly replayable* artifact (moves 1+2 combined). This is what
  ComfyUI workflow-sharing wants to be and can't: a look that reproduces anywhere,
  not a graph that breaks on import. Also the natural SaaS unit of sale later.

## Sequencing (dependency-honest)

```
Week 1: #1 exact-replay (S) → #4 local-first + LTX/Wan verify (S) → #6 doctor --fix (S)
Week 2: #3 MCP server (M) — unlocks agent story; response models close OpenAPI gap
Week 3-4: #2 style-LoRA (L) — the moat; judge + registry from #3/#5 feed it
Parallel drip: #5 registry now (small), BTCPay when SaaS talk gets real
Then: A + B fall out of combining 1+2+3 — packaging, not new invention
```

Total to differentiation: ~3-4 focused weeks of agent-days on hardware already owned.
