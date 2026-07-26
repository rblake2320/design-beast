# Beast Studio Benchmark (P1)

Turns quality claims into evidence. Results are versioned in `results/` and every
number is reproducible: `python bench/run_bench.py --model <model>`.

## What runs automatically (protocol v0.2, 2026-07-26)
- Every brief in `briefs.json` goes through the FULL production loop:
  structured prompt → 4 controlled candidates (base unchanged + the brief's
  variation + 2 fixed control variations shared by all briefs) → vision judge →
  auto-improvement pass when winner < 8 → validated upscale → grade.
- The runner validates the candidate count on every result; a run that comes
  back with the wrong number of primary candidates is marked invalid and
  excluded from score aggregates.
- Recorded per brief: terminal phase, winner score, per-candidate scores/kills,
  candidate-count validity, whether auto-improvement fired, wall-clock latency,
  upscale validity.
- Summary: mean/median score, completion rate, improvement usage, mean latency,
  plus the protocol block (version, candidates per brief, control variations).

## Correction — prior runs were single-candidate (protocol v0.1)
All results dated before 2026-07-26 (`20260725_*` and `20260726_060905_*`) were
produced by a runner that sent `variations=[<one variation>]`. The server
generates one candidate per variation entry, so each brief ran exactly ONE
candidate whose prompt was "base; variation" — the base prompt alone never ran,
and no candidate competition happened. **Those results cannot substantiate any
multi-candidate quality-loop claim.** They are preserved unmodified in
`results/` for reference, but are not comparable to v0.2 results. Every v0.2
result file carries a `protocol` block so the two generations cannot be
confused.

## Current coverage vs ROADMAP target
- 50 fixed image briefs across product / character / environment / UI /
  game-asset / typography. The suite definition is complete; a full protocol
  v0.2 GPU run is still pending.
- `multimodal_tasks.json` fixes 20 edit, 15 image→video, and 15 image→3D
  tasks to exact source-brief IDs and acceptance criteria.
- `run_multimodal.py` runs any one suite from an explicit source-result map and
  keeps every fallback local-only. A completed protocol-v0.2 image run is
  required to create that source map; measurements are therefore still pending.

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
explanation). The local `comfy:flux.1-schnell` backend bypasses that wrapper and
has been verified on those two previously blocked briefs. That is a targeted
mitigation, not yet a full-suite quality claim: protocol v0.2 still needs a
complete 12-brief run.

## Honesty rules
- Never edit briefs.json and old results in the same commit (keeps runs comparable).
- A failed run counts against completion rate — no cherry-picking.
- Judge model/version is recorded implicitly by date; note qwen3-vl:8b changes in
  this file when they happen.
