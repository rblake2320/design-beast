# Competitive landscape — 2026-07-31

Who's near design-beast's territory, what hurts them, and what we do about it.
Companion to SCOUT-2026-07.md (tools) — this file is about *products and their pain*.

## The map

| Player | What they are | Their pain (documented) |
|---|---|---|
| **Krea** | Cloud multi-model suite (64+ models, $9+/mo) | Restrictive free tier, Discord-only support, billing complaints (charges after deletion, refused refunds), enhancer quality regressions, ~3x fewer outputs/$ than rivals |
| **Higgsfield** | Multi-model studio (we're a customer) | Expensive credits + day passes, email-only support even at $119/mo |
| **Runway** | Video production suite | Killed Unlimited (June 2026) → 9,500-credit Max; credit anxiety is the defining UX |
| **ImagineArt Workflow, Pika Agents, Iris** | Agent-driven pipeline automation (brief → assets → video), agents living in Slack/Discord/Figma | Closest to our agent-first thesis; all cloud-only, credit-metered, no 3D/engine delivery |
| **ComfyUI** | THE local-first engine (we embed it) | Dependency hell (custom nodes pin conflicting torch versions), weekend-breaking updates, workflows don't reproduce on other machines, abandoned nodes |
| **InvokeAI** | Local canvas-centric suite | Slower than Comfy/Forge, weeks-late model support, VRAM hoarding, workflow ceiling for power users |
| **Scenario** | Game-asset SaaS, style-locked models trained on your art ($15+/mo) | Style consistency is their whole moat — cloud-only, per-tier compute |
| **Layer.ai** | Game-asset SaaS at studio scale (300+ models, consumption pricing) | Cloud-only; UA-creative focus, no engine-side delivery |
| **Meshy / Tripo** | Image/text → 3D SaaS | Per-seat + credit caps; topology/consistency still the complaint driver |
| **Civitai** | Adult-permissive model hub + gen | **Lost its card processor May 2025 over AI NSFW**; forced into crypto (NowPayments — USDC/LTC/ETH/SOL etc., no BTC on fees); split into civitai.com (crypto Buzz) vs civitai.green (card-safe) |

## What nobody else has (the combined moat)
Local-first **+** agent-native API **+** enforced multi-candidate judge **+** direct
Unreal delivery **+** operator-owned content policy. Each competitor has at most two.

## Their pain → our moves

1. **Credit anxiety (Krea/Runway/Higgsfield)** → local-first is the answer we already
   have; keep cloud strictly opt-in fallback (execution policy ✓). Marketing line
   writes itself: "your 5090 doesn't sell day passes."
2. **ComfyUI dependency hell** → reproducibility as a *feature*: we already pin
   per-tool venvs + provenance manifests. Add: snapshot ComfyUI's package set +
   custom-node commit SHAs into each run manifest (ROADMAP P0 provenance gap —
   raises it from partial to exact-replay).
3. **Scenario's style-lock moat** → replicate locally: train style LoRAs on the
   operator's own art (5090 handles it; llm-trainer skill exists). Candidate for
   ROADMAP P2/P3 — "consistent style" is the single most-paid-for feature in the
   game-asset market.
4. **Civitai's payment crisis** → *the* real-world proof of CONTENT-POLICY-ARCHITECTURE:
   policy tiers + crypto-first billing (BTCPay; note Civitai skipped BTC over fees —
   Lightning or stables matter) designed in from day one, not bolted on mid-crisis.
   Second lesson: they got hurt as a *hosted UGC marketplace* — selling the pipeline
   (self-hosted / BYO-compute) carries far less platform liability.
5. **Agent-first is being validated by others** (Pika Agents in Slack/Discord, ImagineArt
   MCP) → our ROADMAP P4 "native MCP server + capability discovery" is the
   differentiator to ship before cloud players make agents-on-cloud the default; ours
   is the only one an agent can drive end-to-end into a game engine.
6. **Support hostage-taking (Discord-only, email-only)** → self-hosted + `beast doctor`
   + honest degradation notes means the operator is never waiting on a support queue.

## Amendments (2026-07-31, post-verification external comparison)
- Local video lane verified (Wan 48s, LTX-2.3 85s WITH synced audio). External read:
  unit economics beat every Runway tier at volume; single-pass audio+video has no
  Runway equivalent at any tier. Full pricing baseline + methodology: COSTS-BASELINE.md.
- Honest gaps vs Runway to log, not hide: camera control (Motion Brush), face
  performance transfer (Act-One), video-to-video editing (Aleph), and validation
  breadth (our smoke tests ≠ their months of production traffic). Candidates for a
  future scout: local camera-control LoRAs / ATI-style trajectory control for Wan.

## Positioning sentence
Design-beast is what Krea/Higgsfield would be if they ran on your own GPU with no
credit meter, what ComfyUI would be if environments reproduced exactly, what Scenario
would be if style-lock were local, and what none of them are: agent-operable end to end
— brief to judged asset to Unreal — under a content policy the operator owns.

## Amendments (2026-08-05, truth-maintenance)

The combined-moat claim above compares commercial creative products and stands.
Adjacent fields are converging on individual pieces — skill signing (NVIDIA
Verified Agent Skills), tutorial→skill compilation with real-app execution
(Google Watch and Learn; Microsoft Resource2Skill/CUA-Skill) — none with Beast's
per-run evidence custody or lifecycle. Prior-art detail and verification dates:
RESEARCH-LANDSCAPE.md. Categorical "nobody" claims in the capability matrix were
scoped the same day; superseded wordings preserved in its amendment block.
