# Beast Watch proof 005 — agent-built game benchmark

## Result

Beast Watch ingested the 12:23 RemakeBench video into a source-timed,
searchable evidence bundle. The initial pass extracted 186 adaptive frames and
679 caption entries. OpenCLIP/Faiss indexed 176 non-duplicate frames on CUDA.
A confidence-driven reinspection around 00:01:25 added 27 half-second frames,
bringing the visual evidence set to 213 frames.

This is genuine video inspection, but it is **not** an execution proof for any
model or game. It proves that Beast can recover a benchmark's method, displayed
cost/time evidence, visual comparisons, reported failure modes, and stated
limitations. The original projects, prompts, receipts, and game behavior were
not independently replayed here.

Source: <https://www.youtube.com/watch?v=MsFYd8EdAXw>

## What the video establishes

- 00:14–00:28: this is a workflow comparison, not a bare-model comparison;
  each model uses its provider's agent stack.
- 00:29–00:46: runs use one request without human correction, while recording
  output, elapsed time, tokens, cost, and process evidence.
- 01:11–01:38: the narrator reports invisible vehicle parts, obstructed cockpit
  cameras, and a repeated-camera-angle blind spot.
- 03:08–03:50: temporal defects include flicker and a ship launching in the
  wrong orientation; the narrator connects the latter to failure to inspect the
  launch sequence visually.
- 09:58–10:14: the shrine task ran 7h41m until manually stopped and received a
  reported independent-LLM score of 14/40 after two review/revision passes.
- 10:43–10:58: reported long-horizon failures concentrate in animation,
  character quality, and collision; static environments are stronger than the
  interactive components needed for a complete game.
- 11:03–11:32: the displayed `$204.17+` cost is explicitly incomplete because
  seven sub-agents' token categories were unavailable. The video reports their
  aggregate token count but does not establish their exact dollar cost.

## Pixel-only and cross-modal findings

- Frame `f_000000129000.jpg` displays the off-road comparison with elapsed time
  and cost together: Opus 5 Max at 2h48m08.6s / $124.35 and GPT 5.6 Sol Max at
  1h02m40.9s / $19.10.
- Frame `f_000000261000.jpg` displays four space-flight results simultaneously,
  including model labels, costs, and elapsed times.
- Frame `f_000000351000.jpg` makes the cathedral lighting/detail comparison
  visible; this aesthetic difference is not recoverable from prose alone.
- Frame `f_000000627000.jpg` shows the shrine scene with 7h41m36.5s and
  `$204.17+`, where the plus sign is an important uncertainty marker.
- Dense frames from 00:01:18–00:01:32 confirm changing gameplay states and an
  obstructed cockpit view. They support the need for temporal and multi-angle
  validation, but do not independently prove every narrated missing-part claim.

## What Beast learned for its own Unreal process

The reusable lesson is not "run the agent longer." It is that an Unreal build
must be validated as an interactive system from deliberately different
perspectives. A single attractive screenshot, successful compile, or rear-view
playtest can hide broken geometry, collision, controls, cameras, animation, and
state transitions.

`benchmark-protocol.json` records a candidate evaluation protocol derived from
that lesson. It keeps visual quality, behavioral completeness, evidence quality,
time, and cost separate. It also requires repeated runs before making a
reliability claim.

## Honest boundaries

- The video's comparisons are single recorded attempts; they do not establish
  model reliability or a universal ranking.
- Its visual judgments include editorial taste and are not all objective.
- Provider stack, tool access, effort settings, and hardware are confounders, so
  results must not be described as bare-model performance.
- An LLM judge score is advisory unless the rubric, inputs, judge version, and
  scoring trace are retained and reproducible.
- Exact dollar totals remain estimates when cache/input/output token categories
  or sub-agent usage are missing.
- The candidate Beast protocol has not yet been validated across repeated Unreal
  builds; it is a testable proposal, not a proven superior benchmark.

## Beast ingestion defect observed

The source captions use rolling duplicate entries. Of 679 timestamped entries,
only 337 have unique exact text and 334 are adjacent exact duplicates. This can
overweight repeated speech during retrieval. It does not affect the pixel
evidence, but transcript normalization should collapse adjacent duplicates while
retaining their source-time span.

## Next proof

Run one frozen UE 5.8 build task three times with the same agent configuration.
For every run, retain the project, prompt, tool/version manifest, replay inputs,
front/rear/left/right/top/interior captures, before/during/after transition
captures, build logs, elapsed time, and fully qualified cost estimate. Report all
three outcomes and pass rate—not only the best-looking run.
