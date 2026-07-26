# Beast Studio Roadmap — from 8/10 to 9.2/10

Source: independent agent review 2026-07-25 (scored Beast 8.4 personal system,
8.7 agent-first design, 4.8 reliability). Strategy: do NOT chase Adobe/Krea breadth —
become the best **private, agent-operated creative production + game-asset pipeline**.

State legend (audited 2026-07-26): `[x]` implemented and verified · `[~]` partial —
some of it exists, the rest does not; the note says exactly which half · `[ ]` not built.
Nothing below may be promoted to `[x]` without naming the verification.

## P0 — Dependability (reliability 5 → 8)
- [x] SQLite job database; states: queued / running / cancelled / done / failed
      (studio/jobs.py: WAL, boot orphan-recovery, structured error codes;
      exercised by studio/tests/test_p0.py)
- [~] Central GPU scheduler + VRAM lock — PARTIAL: a single `GPU_HEAVY` semaphore
      serializes heavy video/3D jobs. Image-generation jobs are outside that
      scheduler; backend-specific serialization has not been verified. There is
      no central scheduler and no VRAM-aware admission control.
- [~] Cancel / retry / timeout endpoints; idempotency keys — PARTIAL: cancel
      (queued jobs instant; during candidate generation `pool.map()` completes all
      candidates before cancellation is observed; ComfyUI `/interrupt` is global,
      not job-specific), retry, and idempotency keys work. No server-side per-job
      timeout enforcement.
- [~] SSE or WebSocket progress (replace polling) — PARTIAL: `/api/events/{run_id}`
      SSE endpoint exists, but nothing has adopted it: the Studio UI polls every 4s
      and bench polls every 10s. "Replace polling" has not happened.
- [x] Strict Pydantic enums/bounds; upload size+type validation; structured error
      codes (request models with enums/bounds, upload rejection, error codes in
      jobs.py; covered by test_p0.py)
- [~] Automated API + pipeline tests; health/readiness endpoint — PARTIAL:
      health endpoint + API tests (validation/idempotency/cancel/retry) exist and
      require a live server; there are no pipeline/generation tests and no CI.
- [ ] Full provenance per artifact: model, version, seed, params, workflow — NOT
      built. Model name is recorded; seeds are generated per-call and thrown away;
      no version/params/workflow manifest accompanies any artifact.
- [x] `execution policy`: cloud/hosted fallback opt-in only (done 2026-07-25 —
      `allow_cloud_fallback`, `allow_hosted_fallback`, truthful refine provenance)

## P1 — Prove output quality (benchmark before boasting)
- [~] Fixed benchmark suite: 50 image briefs · 20 edits (instruction-following +
      identity) · 15 i2v (temporal stability) · 15 i23D (geometry/texture/UE import)
      — PARTIAL: 12 image briefs only. All results before 2026-07-26 were
      SINGLE-candidate (runner bug, see bench/README correction) and cannot
      substantiate multi-candidate claims; the fixed 4-candidate protocol (v0.2)
      has no completed runs yet.
- [ ] Blind pairwise vs Krea / Runway / Firefly; multiple human raters
- [ ] Judge-vs-human agreement tracking; cost/latency/failure/VRAM logged
      (latency/failure are logged per run; cost/VRAM are not)
- [x] Versioned results in repo (bench/results/, timestamped, never overwritten)

## P2 — Complete the quality loop (the moat)
- [x] Automatic second round: feed judge's `fix` into refine/regenerate
      (improvement pass in the run loop via local Kontext, re-judged)
- [~] Stop criteria: score improvement threshold + max iterations/cost budget —
      PARTIAL: score ≥ 8 threshold, max 2 iterations, stop-on-no-improvement exist;
      no cost budget (pass is local-only today).
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
