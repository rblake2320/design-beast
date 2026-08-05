# Session state

- Goal: build and prove capability fitness, drift detection, controlled practice, proposal-only curriculum, and signed evidence.
- Branch: `codex/experience-forge`, stacked on draft PR #14 (`codex/evidence-intake`).
- Current evidence: doctor 34/34; Beast Core valid with 10 capabilities;
  301 tests passed; live UE 5.8 MCP read-only probe and trusted-pack selection
  succeeded; deliberate drift demoted; signed chain independently verified.
- Constraint: CPU-only while ComfyUI is active; do not stop user processes.
- Authority: implementation may propose lifecycle changes; it may not activate, supersede, download, spend, or publish without review.
- Review state: builder work is complete but must remain a draft PR until a
  different agent or the user verifies and merges it.
