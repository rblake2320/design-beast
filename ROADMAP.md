# Beast Studio Roadmap — from 8/10 to 9.2/10

Source: independent agent review 2026-07-25 (scored Beast 8.4 personal system,
8.7 agent-first design, 4.8 reliability). Strategy: do NOT chase Adobe/Krea breadth —
become the best **private, agent-operated creative production + game-asset pipeline**.

> **Competitive differentiation is scoped separately in [docs/WIN-PLAN.md](docs/WIN-PLAN.md)** — six moves + two novel plays (vision-gated creative CI, beast packs), sequenced against this roadmap.

State legend (audited 2026-07-26): `[x]` implemented and verified · `[~]` partial —
some of it exists, the rest does not; the note says exactly which half · `[ ]` not built.
Nothing below may be promoted to `[x]` without naming the verification.

## P0 — Dependability (reliability 5 → 8)
- [x] SQLite job database; states: queued / running / cancelled / done / failed
      (authoritative progress/lifecycle state, WAL, idempotent schema migration,
      boot orphan-recovery, terminal-state monotonicity, structured error codes;
      status.json is a best-effort compatibility export only; exercised by
      studio/tests/test_state_authority.py and test_p0.py)
- [x] Central GPU scheduler + VRAM lock (done 2026-07-26: durable SQLite
      `gpu_leases` with heavy/light resource classes — video/3D exclusive;
      image gen, refine and the improve pass bounded at LIGHT_CONCURRENCY=2
      and fully excluded while a heavy lease is held; lease waits are
      cancellation- and deadline-aware; crashed holders reclaimed via
      heartbeat staleness (30s) and boot recovery; verified by
      studio/tests/test_gpu_lease.py. Extended 2026-08-03 under approved BR-006:
      `studio/resource_guard.py` now checks live NVIDIA free VRAM against a
      workload budget plus protected reserve before granting the internal lease;
      it fails closed on unknown state and never terminates user processes.
      Deterministic tests plus one live Unreal-active admission/denial pair are
      retained in `proofs/beast-core/PROOF.md`. The check is point-in-time and
      cannot prevent later allocations by unrelated applications.)
- [x] Cancel / retry / timeout endpoints; idempotency keys (done 2026-07-26:
      cancel is job-specific down to ComfyUI's atomic per-prompt endpoint and
      observed at ≤1s intervals mid-generation; retry + idempotency keys work;
      per-job deadlines (per kind, from creation, queue wait included) are
      enforced server-side at checkpoints and lease waits → failed/E_TIMEOUT,
      never a cloud-credit retry; verified by studio/tests/test_cancel.py +
      test_gpu_lease.py. Known limits: blocking non-Comfy HTTP calls finish in
      detached workers after cancel; `to_ue` Blender/UE subprocesses are not
      preemptible mid-call — the job is marked cancelled but the subprocess
      runs to completion.)
- [~] SSE or WebSocket progress (replace polling) — PARTIAL: `/api/events/{run_id}`
      SSE endpoint exists and the Studio UI consumes it with polling fallback;
      the benchmark harness still polls every 10s.
- [x] Strict Pydantic enums/bounds; upload size+type validation; structured error
      codes (request models with enums/bounds, upload rejection, error codes in
      jobs.py; covered by test_p0.py)
- [~] Automated API + pipeline tests; health/readiness endpoint — PARTIAL:
      health endpoint + API tests (validation/idempotency/cancel/retry) exist and
      require a live server; there are no pipeline/generation tests and no CI.
- [~] Full provenance per artifact: model, version, seed, params, workflow —
      PARTIAL: every terminal run writes an atomic `manifest.json` with artifact
      SHA-256/size/type, request params, workflow identifier, model/source and
      retained local seeds (covered by `studio/tests/test_provenance.py`).
      2026-07-31 (WIN-PLAN #1): ComfyUI-backed runs now also capture an
      `environment` record — ComfyUI + custom-node commits (repo-root-strict),
      venv package digest + torch version, exact submitted graph hash, and
      SHA-256 of every referenced model file (persistent (size,mtime) cache) —
      via `studio/env_snapshot.py`; drift is named precisely by
      `beast replay <run-id> | --save-baseline | --check`
      (`scripts/replay_diff.py`; covered by `test_env_snapshot.py`, 7 tests;
      live baseline verified against D:\AI\ComfyUI). Remaining for [x]:
      cloud/hosted backend container digests, and same-seed re-run artifact
      comparison (needs seed plumbing through the comfy request path).
- [x] `execution policy`: cloud/hosted fallback opt-in only (done 2026-07-25 —
      `allow_cloud_fallback`, `allow_hosted_fallback`, truthful refine provenance)

## P1 — Prove output quality (benchmark before boasting)
- [~] Fixed benchmark suite: 50 image briefs · 20 edits (instruction-following +
      identity) · 15 i2v (temporal stability) · 15 i23D (geometry/texture/UE import)
      — PARTIAL: all 100 fixed task definitions and acceptance criteria now
      exist and the multimodal runner is implemented; completed measurements
      remain. All results before 2026-07-26 were SINGLE-candidate (runner bug,
      see bench/README correction) and cannot substantiate multi-candidate
      claims; the fixed 4-candidate protocol (v0.2) has no completed full run yet.
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
- [~] Versioned OpenAPI contract in repo plus Python and TypeScript SDKs
      covering all 19 API paths, including SSE/polling wait helpers and safe
      false defaults for credit/privacy fallbacks; endpoint/request drift and
      coverage are enforced by `scripts/generate_openapi.py --check`, 25 Python
      SDK tests, and 20 TypeScript SDK tests. PARTIAL: server response models
      are not declared, so OpenAPI response schemas are empty and SDK response
      types remain hand-maintained rather than generated.
- [ ] Native MCP server; capability-discovery endpoint
- [ ] Per-request budget + privacy policy; agent leases for shared backends
- [~] Event subscriptions; multi-stage pipeline endpoint; artifact manifests
      with checksums — PARTIAL: SSE subscriptions and checksum-backed manifests
      exist; no declarative multi-stage pipeline endpoint yet.

## Known gaps vs competitors (reference)
ComfyUI: composable graphs, queue/interrupt/history, ecosystem. InvokeAI: canvas
editing. Krea: real-time interaction, training. Runway: video production suite.
Adobe: enterprise/collab/rights. Beast's unmatched combo: local-first + agent-simple
API + enforced multi-candidate QA + judge + image/video-with-audio/3D/TTS + direct
Unreal delivery.
