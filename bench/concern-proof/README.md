# Beast concern proof

This directory holds the frozen, matched ablation prompted by the 2026-08-03
Claude review. It separates three questions that must not be collapsed:

1. Can a transcript-only agent recover the demonstrated state?
2. Do initial adaptive frames add facts absent from speech?
3. Does uncertainty-driven reinspection correct an ambiguous or transient state?

All conditions use the same Codex model, schema, task wording, target adapter,
and clean initial state. Baselines run first in isolated ephemeral workspaces.
The agent may return `insufficient_evidence`; honest abstention is not counted as
an unsupported claim. A response counts as correct only when its manifest drives
a target artifact and the artifact passes the predeclared validator.

The first run is explicitly a pilot. It can validate the harness and provide a
measured data point. It cannot satisfy the full breadth gate in
`../beast-loop-protocol.json`, which requires three domains, three distinct tasks
per domain, and three repetitions per condition.
