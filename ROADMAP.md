# Beast Studio Roadmap — from 8/10 to 9.2/10

Source: independent agent review 2026-07-25 (scored Beast 8.4 personal system,
8.7 agent-first design, 4.8 reliability). Strategy: do NOT chase Adobe/Krea breadth —
become the best **private, agent-operated creative production + game-asset pipeline**.

## P0 — Dependability (reliability 5 → 8)
- [ ] SQLite job database; states: queued / running / cancelled / done / failed
- [ ] Central GPU scheduler + VRAM lock (no more manual "don't run cinema + images")
- [ ] Cancel / retry / timeout endpoints; idempotency keys
- [ ] SSE or WebSocket progress (replace polling)
- [ ] Strict Pydantic enums/bounds; upload size+type validation; structured error codes
- [ ] Automated API + pipeline tests; health/readiness endpoint
- [ ] Full provenance per artifact: model, version, seed, params, workflow
- [x] `execution policy`: cloud/hosted fallback opt-in only (done 2026-07-25 —
      `allow_cloud_fallback`, `allow_hosted_fallback`, truthful refine provenance)

## P1 — Prove output quality (benchmark before boasting)
- [ ] Fixed benchmark suite: 50 image briefs · 20 edits (instruction-following +
      identity) · 15 i2v (temporal stability) · 15 i23D (geometry/texture/UE import)
- [ ] Blind pairwise vs Krea / Runway / Firefly; multiple human raters
- [ ] Judge-vs-human agreement tracking; cost/latency/failure/VRAM logged
- [ ] Versioned results in repo

## P2 — Complete the quality loop (the moat)
- [ ] Automatic second round: feed judge's `fix` into refine/regenerate
- [ ] Stop criteria: score improvement threshold + max iterations/cost budget
- [ ] Split scores: aesthetic / brief-compliance / technical; multi-judge consensus
- [ ] Human approval checkpoints; judge regression tests

## P3 — Production workspace
- [ ] Project-based asset library; searchable runs + metadata; compare view
- [ ] Canvas: masks, regions, layers, outpainting, exact replay (vs InvokeAI)
- [ ] Storyboards / shot lists / timeline assembly; video+audio QC (vs Runway)
- [ ] UE import validation: naming, collision, LODs, materials

## P4 — Agent-native leadership
- [ ] OpenAPI contract in repo; generated Python/TS SDKs
- [ ] Native MCP server; capability-discovery endpoint
- [ ] Per-request budget + privacy policy; agent leases for shared backends
- [ ] Event subscriptions; multi-stage pipeline endpoint; artifact manifests w/ checksums

## Known gaps vs competitors (reference)
ComfyUI: composable graphs, queue/interrupt/history, ecosystem. InvokeAI: canvas
editing. Krea: real-time interaction, training. Runway: video production suite.
Adobe: enterprise/collab/rights. Beast's unmatched combo: local-first + agent-simple
API + enforced multi-candidate QA + judge + image/video-with-audio/3D/TTS + direct
Unreal delivery.
