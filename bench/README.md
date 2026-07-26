# Beast Studio Benchmark (P1)

Turns quality claims into evidence. Results are versioned in `results/` and every
number is reproducible: `python bench/run_bench.py --model <model>`.

## What runs automatically
- Every brief in `briefs.json` goes through the FULL production loop:
  structured prompt → 2 candidates (base + one variation) → vision judge →
  auto-improvement pass when winner < 8 → validated upscale → grade.
- Recorded per brief: terminal phase, winner score, per-candidate scores/kills,
  whether auto-improvement fired, wall-clock latency, upscale validity.
- Summary: mean/median score, completion rate, improvement usage, mean latency.

## Current coverage vs ROADMAP target
- 12 image briefs across product / character / environment / UI / game-asset /
  typography (target: 50)
- TODO: 20 edit tasks (instruction-following + identity preservation via judge
  on before/after pairs), 15 image→video (temporal stability), 15 image→3D
  (geometry/texture + UE import success via /api/to_ue)

## What requires humans (cannot be automated honestly)
- **Blind pairwise vs competitors** (Krea, Runway, Firefly): the harness can
  generate Beast's side; a human must produce competitor outputs for identical
  briefs and rate pairs blind. Protocol: shuffle pairs, ≥3 raters, majority vote,
  report win-rate with rater agreement.
- **Judge-vs-human agreement**: sample 30 judged images, humans score 1-10 blind,
  report correlation. If agreement is weak, calibrate the judge prompt before
  trusting benchmark deltas.

## Known platform limitation (found by run 20260725_233956, diagnosed 2026-07-26)
The FLUX NIM containers include a **prompt-text guardrail** that rejects some benign
prompts before generation (log: "Returning prompt filtered response in 0.3s" — no GPU
work). Reproduced deterministically on `ui-02` ("3D clay chef hat") and `typo-02`
("OPEN LATE" neon). Rewording and cross-model retry (flux.1↔flux.2) do NOT help —
the filter component is shared. Pipeline handles it honestly (dead-frame kill +
explanation). Fix in progress: `comfy:flux.1-schnell` backend running raw Apache-2.0
weights without the NIM wrapper. Until then, expected NIM completion ceiling ≈ 10/12
on this suite.

## Honesty rules
- Never edit briefs.json and old results in the same commit (keeps runs comparable).
- A failed run counts against completion rate — no cherry-picking.
- Judge model/version is recorded implicitly by date; note qwen3-vl:8b changes in
  this file when they happen.
