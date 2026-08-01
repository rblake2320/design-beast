# Opportunity Ledger

Design Beast treats unexpected capability as a first-class output of engineering and
research. A discovery must not be discarded merely because it falls outside the
current task, and it must not be promoted merely because it sounds novel.

## Operating loop

When work reveals a previously unavailable capability, combination, dataset,
workflow, or product direction:

1. **Capture it immediately.** Record the triggering observation and preserve the
   artifact, measurement, source, commit, screenshot, or run ID that exposed it.
2. **Step back.** Ask what becomes possible now that was not possible before, who
   benefits, what it replaces, and whether its largest value may be outside the
   current project.
3. **Research the frontier.** Search current primary sources, official repositories,
   papers, documentation, and credible competing products. Distinguish an actually
   new opening from a known capability with a new local implementation.
4. **Form a falsifiable claim.** State the smallest useful claim that an experiment
   can prove or disprove. Do not use market language as evidence.
5. **Build the smallest real experiment.** Use actual inputs, actual tools, and the
   intended environment. No mocked success paths, fabricated measurements, or
   screenshots standing in for working behavior.
6. **Measure the result.** Preserve quality, latency, cost, failure modes, hardware,
   versions, and comparison conditions. Negative results remain useful evidence.
7. **Route deliberately.** Promote, integrate, research further, park with a revisit
   trigger, or reject with a recorded reason.

## Entry template

Copy this section for each discovery.

```markdown
## OPP-YYYYMMDD-NN — Short name

- Status: observed | researching | experiment | proven | integrated | parked | rejected
- Trigger: exact observation, artifact, run, or commit
- New capability: what is possible now that was not possible before
- Potential beneficiaries: users, agents, products, or domains
- Current-project value:
- Outside-project value:
- Prior art and primary sources:
- Falsifiable claim:
- Smallest real experiment:
- Measures and acceptance threshold:
- Risks, constraints, and rights/privacy implications:
- Evidence:
- Decision:
- Revisit trigger:
```

## Evidence language

Use these terms consistently:

- **Observed:** appeared once; cause and repeatability are not established.
- **Reproduced:** repeated under named conditions.
- **Measured:** quantitative result and method are recorded.
- **Verified:** acceptance criteria passed with retained evidence.
- **Generalized:** verified across materially different inputs or environments.
- **Novel:** use only after documented prior-art research; normally qualify the
  scope, such as “novel within this local pipeline,” rather than claiming global
  novelty.

## Parked opportunities

A parked item must include a concrete revisit trigger, such as a model release,
dependency fix, available dataset, hardware threshold, user demand, or completion of
another capability. “Later” is not a trigger.

## Current discovery from Watch v2

### OPP-20260731-01 — Verified procedural memory from visual demonstrations

- Status: experiment
- Trigger: Watch v2 now produces source-aligned, searchable visual evidence plus a
  state/action/validation procedure contract.
- New capability: demonstrations can become evidence-backed candidate procedures,
  then executable and validated skills—not merely summaries.
- Potential beneficiaries: Unreal/Blender automation, desktop GUI agents, software
  onboarding, QA reproduction, equipment maintenance, accessibility, and institutional
  knowledge capture.
- Current-project value: teach Beast production techniques and verify them inside
  disposable Unreal projects.
- Outside-project value: a general compiler from instructional video to practiced
  agent procedures may be more valuable than the video-watching feature itself.
- Prior art and primary sources (corrected 2026-07-31 after a deeper search): the
  broad category is **not unoccupied**. Google's *Watch and Learn: Learning to Use
  Computers from Online Videos* (arXiv 2510.04673v3, dated 2026-03-16) reports a
  framework that converts online human computer-use videos into executable UI
  trajectories using inverse dynamics and retrieval. Earlier work includes automatic
  procedure learning from web instructional videos (AAAI 2018), procedure planning
  from instructional videos (ECCV 2020/CVPR 2022), and learning web procedures from
  explanations plus demonstrations (ACL 2020). A 2026 defensive publication titled
  *GUI-OBSERVE-API-LEARN (GOAL)* also describes producing callable workflow skills
  from demonstrations, tutorials, and documentation by reproducing workflows in a
  sandbox and capturing APIs. Primary/source records:
  https://arxiv.org/abs/2510.04673 ·
  https://doi.org/10.1609/aaai.v32i1.12342 ·
  https://arxiv.org/abs/1907.01172 ·
  https://arxiv.org/abs/2205.02300 ·
  https://aclanthology.org/2020.acl-main.684/ ·
  https://www.tdcommons.org/dpubs_series/10260/
- Differentiation hypothesis, not novelty claim: Beast may still contribute a useful
  combination of source-time evidence chains, uncertainty-driven reinspection,
  application-native Unreal/Python/MCP compilation, deterministic replay provenance,
  and structural + behavioral + visual validation. That combination must be compared
  experimentally against the retrieved prior art before any narrower novelty claim.
- Falsifiable claim: for a bounded Unreal tutorial, Beast can recover the required
  settings and ordered actions, implement them through supported APIs, and produce a
  result that passes structural and visual acceptance checks.
- Smallest real experiment: one 5–15 minute Unreal lighting tutorial, one clean test
  project, one generated procedure, one replay, and retained before/after evidence.
- Measures and acceptance threshold: all required assets/settings present, no editor
  errors, deterministic replay, target visual score met, and every implemented step
  traceable to source evidence or official documentation.
- Decision: build and measure before making broader claims.
- Revisit trigger: completion of the first end-to-end tutorial-to-verified-skill run.

### OPP-20260731-02 — Evidence-linked, cross-agent skill compilation

- Status: observed
- Trigger: Watch proof 002 compiled a Devin tutorial into a structurally valid
  `SKILL.md`; current Devin documentation states that it follows the open Agent
  Skills standard and scans `.agents`, `.codex`, `.claude`, `.cursor`, `.github`,
  `.cognition`, and `.windsurf` skill locations.
- New capability hypothesis: one source-evidenced procedure may be packaged once
  and behaviorally tested across multiple agent runtimes instead of compiled to a
  target-specific prompt.
- Potential beneficiaries: teams using multiple coding agents, skill marketplaces,
  tutorial authors, enterprise governance, and regression-testing systems.
- Current-project value: make Beast Watch's compiler output portable and expose
  agent-specific behavioral differences using the same evidence and acceptance
  contract.
- Outside-project value: an interoperability test suite for learned procedures may
  be valuable independently of video ingestion.
- Prior art and primary sources: Devin's official Skills documentation describes
  the open Agent Skills format and multi-tool locations:
  https://docs.devin.ai/product-guides/skills . Each named agent's current official
  implementation and deviations still require independent verification; directory
  scanning by Devin is not evidence that all named products execute the same skill
  equivalently.
- Falsifiable claim: the same evidence-linked skill can complete a fixed disposable
  task in at least two independently implemented agent runtimes while satisfying
  identical safety and output assertions.
- Smallest real experiment: one portable skill, two installed agents, one disposable
  repository, five permission scenarios, and retained decision/execution logs.
- Measures and acceptance threshold: both parsers accept the package; both agents
  complete safe cases; both refuse or escalate unauthorized destructive, global,
  paid, and cloud actions; outputs pass the same structural and behavioral checks.
- Risks, constraints, and rights/privacy implications: syntax may be portable while
  tool names, trigger semantics, permission models, and instruction precedence are
  not. Tutorial rights and source attribution must remain attached to derived work.
- Evidence: `proofs/watch-002-devin/`; schema validation is not behavioral validation.
- Decision: retain as a testable opportunity; do not claim cross-agent portability
  until the two-runtime experiment passes.
- Revisit trigger: a second compatible agent is installed and available for a
  disposable behavioral run.
