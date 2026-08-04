# The Beast Contract

Beast is a verified capability engine. Its defining input is demonstrated work,
especially information visible in video that a transcript cannot contain. It
observes how work is done, preserves source evidence, compiles demonstrations into executable
procedures, runs them in the real target environment, measures the result,
repairs failures, and retains only the capability its evidence supports.

Beast is not a model, a prompt collection, or a claim that every supported tool
is autonomous. It is the control system around intelligence and tools that makes
successful work inspectable, recoverable, and reusable.

## The Beast loop

Every promoted capability follows the same state machine:

```text
DISCOVER -> OBSERVE -> REINSPECT -> COMPILE -> EXECUTE
        -> MEASURE -> REPAIR -> PROVE -> REMEMBER -> REFLECT
```

Stages may move backward whenever evidence is missing. `REINSPECT` can seek a
different video interval, documentation version, screenshot, log, API surface,
or live application state. `REPAIR` returns to the earliest invalid assumption;
it does not merely retry the last action.

No stage implies the next:

- observation is not understanding;
- a compiled procedure is not an executable skill;
- execution is not correctness;
- measurement is not verification;
- one verified run is not generalization;
- reflection is not authority to modify durable rules.

## Anatomy

| System | Responsibility | Current implementation |
|---|---|---|
| Eyes | Acquire source-linked video, text, image, audio, UI, and live state | Watch, OCR/vision, documentation and engine probes |
| Brain | Track dependencies, uncertainty, versions, claims, and capability state | `beast/capabilities.json`, evidence maps, opportunity ledger |
| Hands | Execute through deterministic interfaces before GUI fallback | CLI, first-party MCP, APIs, engine scripts, SelfConnect |
| Memory | Retain replayable evidence and exact recovery points | proof bundles, manifests, hashes, checkpoints, green paths |
| Judgment | Apply predeclared gates and distinguish evidence strength | structural, behavioral, visual, and human-review gates |
| Immune system | Reject unsupported claims, unsafe permissions, drift, and resource overcommit | claim boundaries, approval gates, doctor, resource guard |
| Metabolism | Turn work and failures into bounded improvement proposals | Beast Reflection |
| Evolution | Promote only improvements that win controlled replay tests | Beast-loop benchmark protocol; benefit remains unproven until run |

## Evidence states

The authoritative meanings come from `docs/OPPORTUNITY-LEDGER.md`:

`observed -> reproduced -> measured -> verified -> generalized`

The states are evidence labels, not a progress animation. Promotion requires a
named acceptance condition and retained evidence. `generalized` additionally
requires materially different inputs or environments; repeated runs of one case
establish reliability for that case, not breadth.

Every machine-readable capability must state:

- its smallest supported claim;
- its explicit boundary—the nearby claim it does not support;
- evidence paths and their level;
- dependencies and target/version constraints;
- the next falsifiable promotion test.

`python scripts/beast_core.py validate` enforces the structural portion of this
contract. It cannot decide whether an image looks good or an experiment was
scientifically persuasive; those remain explicit validation gates.

## Capability promotion

A candidate may be packaged as a Beast Pack, but it is not promoted merely
because the package validates. A pack contains:

```text
pack.json              identity, version, claim, boundary, evidence level
procedure or skill     executable instructions
evidence               source map and proof references
validation             deterministic checks and human gates
recovery               checkpoint/resume contract
resource profile       admission class and expected pressure
```

Schema validity means the package is well formed. The manifest's evidence level
means only what its cited proof establishes.

Pack evidence is immutable. A stronger or corrected implementation creates a new
version; it does not rewrite the old pack's proof. The new manifest names every
version it `supersedes` and records the reason. Superseded and deprecated packs
remain discoverable for audit and replay, but planners select only `active` packs
unless reproducing history. Reflection may propose supersession; it cannot change
a pack lifecycle without human approval and a new validating proof.

## Operational invariants

1. Start from current remote `main` and run doctor before pipeline work.
2. Prefer deterministic APIs, CLIs, and MCP operations over GUI actions.
3. Preserve source time, versions, environment state, and hashes where relevant.
4. Stop or reinspect when evidence is insufficient; never fill gaps invisibly.
5. Check GPU admission before loading a model or starting a heavy workload.
6. Write a recovery checkpoint before long external operations and at every
   meaningful irreversible boundary.
7. Never stop a user process automatically to reclaim resources.
8. Cloud, paid, authentication, publication, and destructive steps retain their
   existing human-authorization boundaries.
9. Reflection proposes; a human approves; matched replay determines improvement.
10. Claims remain narrower than demonstrations until breadth is measured.

## The measurable promise

The system-level hypothesis is:

> Expensive intelligence and human demonstrations can be compiled into cheaper,
> verified, replayable execution without increasing unsupported claims.

That is not yet a generalized result. `bench/beast-loop-protocol.json` defines
the controlled runs required to test it. Until those runs exist, Beast may claim
the individual capabilities in its graph—not the universal promise.
