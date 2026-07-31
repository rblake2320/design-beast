# beast costs — avoided-cost baseline + methodology

The ledger's "dollars avoided" number is only as credible as its baseline. This file IS
that baseline: every price point dated and sourced, the mapping rule explicit, and the
claims we do NOT make listed alongside. Re-verify quarterly — cloud pricing moves.

## Methodology

1. Every local run already records backend + kind + duration/size (job DB + manifest).
2. Each local backend maps to its **cheapest commercially reasonable cloud equivalent**
   (not the most expensive — the number must survive a skeptic).
3. `beast costs` = sum over runs of (equivalent cloud price) − (local cost, which we
   book as $0 marginal; electricity is real but < $0.02/clip on a 575W GPU and is
   noted, not netted).
4. Anything without a defensible equivalent (e.g. judge passes) is EXCLUDED, not
   estimated.

## Baseline price points (captured 2026-07-31, external research)

| Local lane | Cloud equivalent | Price basis |
|---|---|---|
| Wan 2.2 i2v | Runway Gen-4 Turbo | ~5 credits/sec (~$0.05–0.10/sec effective); 10s 1080p clip ≈ $1–6 depending on model/plan |
| LTX-2.3 i2v + synced audio | Runway Gen-4 std/4.5 | ~12 credits/sec std, 25 credits/sec Gen-4.5 (~$0.12–0.48/sec); **no single-pass audio+video equivalent at any tier — priced as video-only, understating our side** |
| Flux images | Krea $30/mo tier throughput | Krea delivers ~1/3 the outputs per dollar of Higgsfield at same price (2026 reviews) |
| Chatterbox TTS/clone | ElevenLabs per-char pricing | map by generated seconds |
| ACE-Step music | commercial track licensing floor | map per track, conservative |

Caps context: Runway Standard = 625 credits/mo (≈25–125s of footage); Unlimited tier
retired June 2026 → Max = 9,500 credits/mo; "relaxed mode" queues are throttled, not
fast-lane. Local has no cap other than GPU time.

## What we do NOT claim (skeptic-proofing)

- **Not claiming quality parity on the hardest shots.** Runway Gen-4.5 leads on
  cinematic motion coherence; our smoke tests prove the pipeline, not failure-mode
  coverage across thousands of edge cases.
- **Not claiming feature parity on polish tooling.** Camera control (Motion Brush),
  face performance transfer (Act-One), and video-to-video editing (Aleph) have no
  local equivalent in this stack yet — logged in COMPETITIVE-LANDSCAPE as real gaps.
- **Not netting electricity or hardware amortization** in the headline number; both
  are footnoted (5090 ≈ $0.01–0.02/clip at US average rates; hardware amortizes
  across every lane, not just video).

## Where the ranking honestly sits (external read, 2026-07-31)

- **Unit economics: ahead of every Runway tier** once volume passes a handful of clips
  per month — no credit ceiling matters most for multi-candidate iterate-and-judge
  workflows, which is exactly Beast's loop.
- **Single-pass audio+video (LTX-2.3): a genuine capability edge**, not just a cost
  edge — no Runway tier bundles it.
- **Remaining gap: breadth of validation + polish tooling** — precisely what doctor
  --fix, the MCP server, and the benchmark suite (ROADMAP P1) are for.
