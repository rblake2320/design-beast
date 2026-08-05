# Lifecycle contract

## Current-status overlay

Pack manifests preserve the historical, reviewed lifecycle. The lifecycle
assessment is a current eligibility overlay:

- `active`: the enrolled probe passes, fingerprint matches, and freshness has
  not expired.
- `stale_unproven`: an assertion failed, the fingerprint changed, the probe
  expired, or the probe could not run. Trusted retrieval is blocked.

Automatic demotion is fail-closed operational behavior, not an irreversible
repository edit. Reactivation requires a new passing receipt and independent
review; a tool must not merely enroll the changed environment as the new truth.

## Fitness

Each baseline run must have exactly one candidate mate with the same task,
variant, repetition, and frozen-envelope fingerprint. Every run is retained.
Promotion eligibility requires no candidate regression and at least one positive
score delta. Eligibility remains a proposal.

## Practice

The generalization envelope lists only executed variants. Three passing variants
may raise the *structural ceiling* to generalized, but semantic diversity and
independent review are still required before the capability graph may use that
evidence word.

## Signed custody

Ed25519 signatures and previous-entry hashes detect modification, deletion,
reordering, and wrong-key verification. They establish tamper evidence, not
semantic correctness. Keep production private keys outside Git and backup them
under the user's normal secret-management policy.
