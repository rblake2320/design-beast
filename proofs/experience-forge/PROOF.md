# Experience Forge lifecycle foundation — proof report

Date: 2026-08-04  
Target: `ue58-enhanced-input-movement` Beast Pack  
Environment: live official UE 5.8 MCP at `127.0.0.1:8000`

Validation: lifecycle skill valid; Beast Core valid with 10 capabilities and
one pack; repository suite `301 passed, 7 deselected`.

## Acceptance results

| Gate | Result | Receipt |
|---|---:|---|
| Enrolled live probe remains eligible | PASS | `ue58-live-assessment.json` |
| Changed fingerprint demotes fail-closed | PASS | `ue58-deliberate-drift-assessment.json` |
| Stale pack blocked from trusted retrieval | PASS | `trusted_retrieval: false` in drift receipt |
| Planner-facing selection admits live pack and excludes drift/probe errors | PASS | `trusted-packs-live.json`; `test_trusted_pack_selection_*` |
| Expired evidence demotes | PASS | adversarial unit test |
| Fitness rejects unmatched runs/regressions/unsupported claims | PASS | adversarial unit tests |
| Practice retains failed and missing variants | PASS | adversarial unit test |
| Curriculum cannot execute its own proposals | PASS | `may_execute: false` test |
| Signed chain detects modification/deletion/wrong key | PASS | independent verifier tests |

The live MCP assessment observed the enrolled facts: protocol `2025-06-18`, 56
toolsets, and documented Blueprint DSL. Its fingerprint exactly matched
`61683607…a851b`, producing `active` and `trusted_retrieval: true`.

The negative receipt is a deliberate fixture derived from the same response
with only `toolset_count` changed from 56 to 55. It is **not** represented as a
real Unreal failure. It produced a different fingerprint, `stale_unproven`, and
`trusted_retrieval: false` without changing or stopping Unreal.

## What is proven

- The lifecycle implementation derives a current fail-closed eligibility
  overlay without rewriting historical pack proof.
- `beast_core.py trusted-packs` is the planner-facing selection path and admits
  only active packs whose current probe passes; unmanaged and unreachable packs
  are excluded.
- Its tested fitness gate refuses cherry-picked or harmful candidates.
- Its tested practice contract retains named success, failure, and missing
  coverage.
- Its curriculum output is proposal-only.
- Ed25519 plus hash chaining is independently verifiable against the tested
  mutation classes and can bind signatures to the current evidence-file bytes.

## What is not proven

- No real UE version drift occurred; the demotion path used a labeled deliberate
  mutation.
- The Enhanced Input movement behavior was not rerun by this proof; the live
  sentinel validates the MCP control surface only.
- No skill has yet demonstrated positive matched fitness or generalized across
  practice variants.
- No scheduler, automatic curriculum execution, SAM 3, reward model, video
  judge, or UniRig workload was installed or activated.
- Production signing-key custody and rotation remain an explicit human decision.
