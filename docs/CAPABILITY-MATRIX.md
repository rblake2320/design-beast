# Capability matrix — everything Beast can do vs the field (2026-07-31)

Exhaustive, per-capability. **Bold** = verified with a dated receipt. Cost column is OUR
cost. "Who else" names the closest commercial offering and its cost model.
Companions: STACK.md (paths + verify dates), COMPETITIVE-LANDSCAPE.md (their pain),
COSTS-BASELINE.md (pricing sources), WIN-PLAN.md (what we build next).

## Image

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Text→image, SOTA quality | Higgsfield (GPT Image 2, Nano Banana 2/Pro) | subscription | Krea/Freepik/OpenArt — credits |
| Text→image local, unfiltered | **ComfyUI + Flux.1-schnell (benchmarked)** | free | ComfyUI (same, DIY setup); cloud suites can't offer unfiltered |
| Multi-candidate + judge + auto-improve loop | **Beast Studio (enforced, judged, re-rolled)** | free | Nobody enforces it — Krea/Midjourney give grids, human picks |
| Product photography, 10 purpose-built modes | higgsfield-product-photoshoot skill | subscription | Flair.ai, Pebblely — credits |
| Marketplace listing cards (compliance-shaped) | higgsfield-marketplace-cards skill | subscription | niche SaaS — subscriptions |
| Identity-consistent character (face lock) | Soul ID | subscription | Scenario (style not face), Civitai LoRAs |
| Style-locked generation (train on own art) | GAP — WIN-PLAN #2 (local LoRA training scoped) | — | **Scenario's whole moat** — $15+/mo |
| Background removal, ship-safe | **rembg GPU (birefnet)** | free | remove.bg — per-image credits |
| Image upscale | Real-ESRGAN (staged) | free | Topaz ($), Krea enhancer (credits, quality-regressed per reviews) |
| Inpaint/canvas editing | GAP (ROADMAP P3 vs InvokeAI) | — | InvokeAI (free local), Photoshop ($) |
| Precision masks by concept | SAM 2.1 **(verified)**; SAM 3 gated at Meta | free | cloud APIs — metered |

## Video

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Image→video local | **Wan 2.2 — 48s/clip smoke-verified** | free | Runway Gen-4 ~$0.05–0.30/sec; Kling/Luma credits |
| **Video + synced AI audio, single pass** | **LTX-2.3 22B — 85s/clip smoke-verified** | free | **No Runway tier bundles this**; Veo-3 class only, metered |
| Cinematic i2v/t2v, frontier models | Higgsfield (Seedance 2.0, Kling 3.0) | subscription | Runway/Krea/Higgsfield — credits |
| HTML→deterministic MP4 (motion graphics) | **HyperFrames — 3 videos shipped 2026-07-31** | free | Remotion (free but React-dev-only), After Effects ($) |
| Explainers/launch/captions/recuts/slideshows/music-sync | HyperFrames 10 workflows | free | Descript/Opus/CapCut — subscriptions |
| Faceless content pipeline (topic→YT+shorts+thread+blog) | ai-content-engine (needs keys) | API costs | Iris, faceless-channel SaaS — $50+/mo |
| Video upscale w/ temporal consistency | GAP — SeedVR2 scouted, not installed | — | Topaz Video ($299), SeedVR2 (free, DIY) |
| Camera control / motion brush | GAP — logged; trajectory-LoRA scout candidate | — | **Runway Motion Brush** — credits |
| Face performance transfer | GAP | — | **Runway Act-One** — credits |
| Video-to-video editing | GAP | — | **Runway Aleph** — credits |
| Virality prediction | Higgsfield brain_activity | subscription | none mainstream |
| Assembly/grade/cut | **ffmpeg 8.1.2 + ImageMagick** | free | CapCut/Premiere |

## Audio

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Voice cloning from 10s | **Chatterbox v3 (GPU-verified 2026-07-31)** | free | ElevenLabs $5–330/mo — [65.3% blind-test prefer Chatterbox](https://findskill.ai/blog/best-open-source-tts-2026/) |
| Fast fixed-voice TTS (54 voices, CPU-capable) | Kokoro (staged, studio-wired) | free | Amazon Polly, OpenAI TTS — metered |
| Premium cloud TTS parity | ElevenLabs via BYOK registry slot | user's key | same product, their key, their terms |
| **Full songs, commercial rights, local** | **ACE-Step 1.5 (CUDA-verified; Apache 2.0)** | free | Suno/Udio $10–30/mo, commercial rights restricted + litigation |
| Lip-sync | NVIDIA ACE Audio2Face-3D (staged) | free | HeyGen/Synthesia — subscriptions |
| Transcription | faster-whisper (in ai-content-engine) | free | Rev/Descript — metered |

## 3D & Game

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Image→3D textured mesh | Tripo API / Hunyuan3D-2.1 / TRELLIS.2 (fit 5090) | free local / API | **Meshy/Tripo SaaS** — per-seat credits |
| Full Blender control by agents | **Blender 5.1 MCP, ~50 tools** | free | nobody commercial |
| **Full Unreal control by agents** | **UE 5.8 first-party MCP (BeastLab, verified)** | free | nobody — Epic's MCP is new; we're already on it |
| Asset delivery INTO engine | /api/to_ue → RouteRush (UE 5.6) | free | **nobody** — Meshy/Scenario stop at file export |
| Sprites→flipbooks (Paper2D/PaperZD) | game-content-pipeline skill | free | Scenario 2D — credits |
| Game packaging | RunUAT via skill | free | manual everywhere |
| Screenshot→judge→fix-list look enforcement | **game-look-pass recipe (new 2026-07-31)** | free | **nobody has this** |
| Rigging/mocap | Rigify, mocap-wrapper, IK Retargeter | free | Mixamo (free, limited), Cascadeur ($) |

## Web & Frontend

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Anti-generic design system | frontend-design + impeccable + theme-factory + dataviz | free | v0/Lovable/Bolt — subscriptions |
| 240+ named styles, 127 font pairings | ui-ux-pro-max (installed 2026-07-31) | free | same skill sold into other agents |
| Component library on tap | magic MCP (21st.dev) | free tier | 21st.dev paid tiers |
| Live library docs (anti-hallucination) | context7 MCP (installed 2026-07-31) | free | Cursor docs-index — subscription |
| Screenshot-judged web output | playwright-cli + claude-in-chrome + judge | free | nobody enforces |

## Vision / QA (the eyes)

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Object detection real-time | **YOLO11 — 5.2 ms/frame (verified)** | free | Roboflow — metered |
| Face detection | **YOLO-Face (verified)** | free | cloud vision APIs — metered |
| Segmentation | **SAM 2.1 (verified)**; SAM 3 pending access | free | cloud APIs |
| Aesthetic judging as a primitive | qwen3-vl/llava via Ollama + judge_image.py | free | **nobody sells vision-QA-as-a-tool** |
| Two-tier cheap-gate→VLM-wake perception | pattern imported from vigil, judge adoption pending | free | nobody |

## Platform & Agent Infrastructure

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Job DB: cancel/retry/timeout/idempotency | **Beast Studio (tested)** | free | cloud platforms internally; not agent-exposed |
| GPU lease scheduler (heavy/light classes) | **Beast Studio (tested)** | free | nobody local |
| **Exact-replay provenance** (env+graph+model hashes) | **env_snapshot + beast replay (19 tests, 2026-07-31)** | free | **nobody — ComfyUI's defining pain** |
| **Tamper-evident chained run ledger** | **studio/ledger.py + beast ledger (from vigil, 2026-07-31)** | free | **nobody** — audit/compliance-grade |
| Backend registry: local-first, BYOK cloud parity | **registry.py + GET /api/registry (2026-07-31)** | free | Krea routes cloud-only; nobody does local-default+BYOK |
| Content-class policy routing (operator-owned) | **registry content_classes + named skip reasons** | free | Civitai bolted on mid-crisis; others hardcode |
| Python + TypeScript SDKs, OpenAPI | shipped (45 SDK tests) | free | cloud APIs only |
| SSE progress events | shipped | free | standard in cloud |
| Native MCP server (agent-drivable everything) | WEEK 2 — scoped | — | Pika Agents (cloud-only, no engine delivery) |
| Local LLM fleet | Ollama: qwen3.6:27b, nemotron, llama4:scout, gemma3, llava, bge-m3 | free | OpenRouter — metered |

## Provenance, Policy & Commerce

| Capability | Beast | Cost | Who else |
|---|---|---|---|
| Per-artifact manifest (SHA-256, params, seeds) | **shipped, 12 tests** | free | C2PA in Adobe — enterprise |
| Documented avoided-cost methodology | COSTS-BASELINE.md | free | nobody publishes theirs |
| Legal-floor-only content policy (minors/consent/age) | CONTENT-POLICY-ARCHITECTURE.md + registry | free | others: opaque blanket bans |
| Crypto-first billing design | BTCPay scoped (WIN-PLAN #5) | — | Civitai (forced into it mid-crisis) |

## Video understanding (watching, not just reading)

| Capability | Beast | Cost | Who else / their model |
|---|---|---|---|
| Any video → frames+transcript bundle an agent can "watch" | **beast watch (verified 2026-07-31: recovered visual facts absent from transcript)** | free (captions) / Whisper fallback | Gemini video-in ($, metered); transcript-only tools miss all visuals |
| Timestamp-correlated visual Q&A ("what graph appeared at 12:30?") | frames named f_MMSS + [MM:SS] transcript lines | free | same |
| Section-only processing (--start/--end) | shipped | free | rare |
| Competitor video analysis (score shots, pacing, judge frames) | watch bundle + judge/YOLO/SAM over frames | free | nobody |

## Knowledge & Automation (the surround)

- MemoryWeb (6,185 memories, 3-tier search) · UltraRAG · project-hub · NotebookLM
- Scheduled cloud agents, multi-agent workflows, browser automation, desktop control
- Gmail/AOL/GitHub/Hostinger/DNS/VPS via CLI+MCP — content can be *published*, not just made

## Scorecard

- **Capabilities where we're the ONLY one:** agent-driven brief→judged-asset→inside-Unreal;
  exact-replay provenance; tamper-evident run ledger; enforced judge loop; single-pass
  local audio+video; screenshot-judged game look; local-default + BYOK registry.
- **Parity or better, at $0 marginal:** image gen, i2v video, voice clone, TTS, music,
  detection/segmentation, motion graphics, upscale (image).
- **Honest gaps (all logged, most scoped):** style-lock LoRA training (WIN-PLAN #2),
  camera control / Act-One / Aleph-class video editing, canvas inpainting, video
  upscale (SeedVR2), SAM 3 (gated), MCP server (week 2), validation breadth vs
  months of paid production traffic.
