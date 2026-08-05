---
name: manage-capability-lifecycle
description: Fitness-test, revalidate, practice, demote, supersede, or retire Beast Packs. Use when admitting a compiled skill, checking whether an environment or dependency change made a proven pack stale, testing controlled variants, reviewing skill usefulness against a no-skill baseline, or proposing what Beast should learn next.
---

# Manage Capability Lifecycle

Keep capabilities trustworthy after their first proof. A passing schema is not
fitness, a prior proof is not freshness, and a proposal is not authority.

## Workflow

1. Run `python scripts/doctor.py` and `python scripts/beast_core.py validate`.
2. Locate the pack manifest and its `lifecycle_policy`.
3. Revalidate with `python scripts/beast_lifecycle.py assess <lifecycle.json>`.
   Planners must select through `python scripts/beast_core.py trusted-packs`;
   reading an `active` field directly bypasses current eligibility.
4. If the result is `stale_unproven`, block trusted retrieval immediately. Do
   not delete history or silently rewrite the enrolled baseline.
5. For a new or repaired skill, run matched baseline/candidate trials and score
   every run with `python scripts/beast_lifecycle.py fitness <results.json>`.
6. Exercise predeclared variants and build the bounded envelope with
   `python scripts/beast_lifecycle.py practice <results.json> --required ...`.
7. Use `python scripts/beast_lifecycle.py curriculum` only to create a review
   queue. It may not browse, download, spend, or execute the proposals.
8. Retain receipts, update the capability graph only to the evidence actually
   earned, and submit the lifecycle change for independent review.

## Gates

- Fitness requires matched envelopes, all candidate hard gates, zero unsupported
  claims, no score regression, and at least one measured improvement.
- Drift or expiration demotes to `stale_unproven` and sets
  `trusted_retrieval=false`.
- Practice reports named successes, failures, and missing variants. Never hide a
  failed variant or translate variant count into arbitrary generalization.
- Activation, supersession, deprecation, and curriculum execution remain human
  decisions. The scripts emit proposals and current eligibility only.

## Evidence signing

For evidence that must survive outside Git history, use
`scripts/signed_evidence.py` with an Ed25519 private key kept outside the repo,
then verify with the independent `scripts/verify_signed_evidence.py`. Never
commit a private key. A valid signature proves chain integrity and key custody;
it does not prove the underlying claim is true.

See [lifecycle-contract.md](references/lifecycle-contract.md) for the status and
claim boundaries.
