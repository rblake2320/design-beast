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
- Evidence (2026-07-31):
  - `proofs/watch-001-lumen-emissive/` — the UE experiment RAN: emissive-material
    Lumen lighting executed in a real UE 5.8.0 project with retained before/after
    viewport captures (dark unlit sphere → emissive sphere with visible Lumen
    bounce), structural probe (`reflection-probe.json`: engine version +
    post-process state), and a replay-capture script. Evidence level:
    **reproduced + measured** (structural); formal acceptance writeup (PROOF.md
    with scored criteria) still owed before "verified".
  - `proofs/watch-002-devin/` — 38:05 tutorial → 206 frames / 1,225 segments /
    176 embeddings → structurally valid compiled `SKILL.md` + source-time
    evidence map + replay log; recovered UI-only facts (the four approval
    choices). Evidence level: **verified for compile-and-validate**; execution
    inside the target agent explicitly NOT claimed.
  - Side yield: two real watcher defects found + fixed with regression tests
    (audio-only stream selection → zero frames; HTTP 429 on caption refresh).
- Decision: build and measure before making broader claims. watch-001 owes its
  scored PROOF.md; watch-002 owes target-agent execution.
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

### OPP-20260801-01 — Beast Docs: instructional webpages as an evidence substrate

- Status: researching
- Trigger: scoping review (2026-08-01) of the iPhone → MetaHuman → Motion Design →
  Remote Control workflow concluded webpage tutorials need their OWN subsystem, not
  reuse of Watch's video-frame abstraction; no code exists yet.
- New capability hypothesis: an agent can ingest an image-rich instructional webpage
  (Epic's Motion Design quick start), preserve source evidence (URL + version
  selector + retrieval timestamp, DOM section paths, ordered instructions, figures
  with captions/alt text, screenshot crops, exact values, text↔figure links,
  confidence + unresolved ambiguities, reinspection history), compile a procedure,
  and reproduce it in the documented application. The adaptive-inspection concept
  from Watch carries over (back to prerequisites, reopen figures full-res, switch
  doc versions) WITHOUT pretending HTML is video.
- Engine-version policy (user decision, 2026-08-01): **UE 5.8 is the required
  target.** Epic currently serves the Motion Design tutorial as 5.8 docs; local
  descriptor diff confirmed real 5.6→5.8 drift (AvalancheDataLink/SceneState moved
  Experimental→VirtualProduction and →beta; core Avalanche no longer beta; new
  SequenceNavigator dep; new AvalancheMaterial/AvalancheFunctionalTest modules).
  Rules: 5.8 docs only · enable 5.8 Avalanche + StormSyncAvalancheBridge · every
  proof in a disposable UE 5.8 GUI project · record "5.8" in every manifest and
  compiled skill · 5.6 findings are drift evidence only, never implementation
  guidance · stop execution if a project opens under another engine version.
- Proof decomposition (each independently gated; combined workflow only after all):
  - A: Live Link Face → Unreal valid subject (network path proven; subject/render NOT)
  - B: MetaHuman renders + responds to that subject (not attempted in GUI)
  - C: Beast Docs compiles Epic's webpage into a reproducible Motion Design
    procedure (not implemented — the next honest artifact is an ingestion manifest
    + evidence map, not an Unreal execution)
  - D: Remote Control changes the resulting graphic externally (Epic-documented,
    locally unproven)
- Prior art and primary sources:
  https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-design-quickstart-guide-in-unreal-engine ·
  https://dev.epicgames.com/documentation/en-us/unreal-engine/your-first-graphic-with-motion-design-in-unreal-engine
- Falsifiable claim (proof C first): Beast Docs can recover Epic's "Your First
  Graphic" procedure — every step, exact values, prerequisites — into an evidence
  map whose each step cites its DOM section and figure, accurately enough that a
  human following only the compiled procedure reproduces the tutorial result.
- Decision: build the ingestion manifest + evidence map first; no Unreal execution
  claims until C passes, no combined-workflow claims until A–D pass independently.
- Revisit trigger: first Beast Docs ingestion manifest produced from the Epic page.

### OPP-20260803-01 — Graph-first consolidation of learned procedures and agent memory

- Status: observed
- Trigger: 2026-08-03 session. Three converging observations: (1) discussion of the
  "Claude Dreaming" video (YouTube jI4ZVB_MPhU — NOT inspected; transcript-only cap
  applies; no claim below is sourced from it) led to first-party verification that
  Anthropic ships Dreams, an async memory-consolidation job for Managed Agents:
  reads one memory store + 1–100 session transcripts, merges duplicates, resolves
  contradictions, surfaces patterns, emits a NEW store with inputs immutable
  (research preview, beta header `dreaming-2026-04-21`). (2) Watch v2 and the
  in-flight beast-reflection skill both consolidate into flat prose files
  (SKILL.md, report markdown) — merge/contradiction/dedup operations there are
  rewrites of prose, not queryable operations. (3) Cross-agent smoke run
  (2026-08-03, retained): the in-flight Codex reflection collector pointed at
  Claude Code's session root found 11 session files but parsed **0 messages** —
  the two agents' transcript schemas are disjoint (Codex `event_msg` envelope vs
  Claude `type: user/assistant` + nested `message.content`), so today each agent
  can only consolidate its own memory.
- New capability hypothesis (graph-first): represent learned procedures and session
  learnings as a graph — nodes = states/steps/settings/assets/claims, each carrying
  a source-evidence pointer; edges = ordering/dependency/duplicate-of/contradicts —
  instead of flat markdown. Then Dreams-style consolidation (merge, contradiction
  resolution, pattern surfacing) becomes a deterministic graph operation with
  per-step provenance preserved, independently watched tutorials can compose into
  larger procedures, and agent-specific transcripts (Codex, Claude) become thin
  adapters feeding one shared substrate rather than parallel memory silos.
- Potential beneficiaries: OPP-20260731-01 (its compiled procedures are this
  entry's input), OPP-20260731-02 (a shared substrate is the natural home for
  cross-agent skills), beast-reflection (adapter model gives it Claude coverage),
  brain repo memory, any multi-agent fleet with per-agent transcript formats.
- Current-project value: Watch/Docs proofs gain lossless merge + drift detection
  across tutorials (e.g. the 5.6→5.8 Avalanche drift in OPP-20260801-01 is exactly
  a "contradicts" edge between two evidence-backed nodes).
- Outside-project value: an open, evidence-first consolidation substrate that is
  agent-agnostic — Anthropic's Dreams store is managed and closed; nothing
  retrieved so far does this over executable, validated procedures.
- Prior art and primary sources (searched 2026-08-03; sweep NOT yet exhaustive —
  no novelty wording until it is): extends OPP-20260731-01 — read that entry
  first; it owns video→procedure, this entry owns only the
  consolidation/representation layer. Anthropic Dreams (first-party, fetched
  2026-08-03): https://platform.claude.com/docs/en/managed-agents/dreams —
  consolidation over a managed store; store format closed, single-vendor.
  Secondary sources describe a Claude Code "Auto Dream" CLI face (observed,
  secondary only; absent from a direct check of Claude Code 2.1.220).
  Watch-and-Learn (arXiv 2510.04673): video→executable trajectories, no graph
  memory or cross-source consolidation. GOAL (tdcommons 10260): demonstrations→
  callable skills, no consolidation layer described. GraphRAG-family systems do
  graph-first consolidation for *documents*; none retrieved so far target
  *procedures with executable validation and source-time evidence chains* — that
  gap is the differentiation hypothesis, stated as hypothesis only.
- Falsifiable claim: for the two existing Watch proofs (watch-001, watch-002), a
  graph representation can be generated such that (a) every node's evidence
  pointer resolves to a retained artifact, (b) a deterministic query reconstructs
  each original compiled SKILL.md losslessly (empty or whitespace-only diff), and
  (c) merging the two graphs deduplicates genuinely shared steps/settings and
  flags at least one real contradiction or version-drift pair with zero human
  editing.
- Smallest real experiment: one script; inputs = the two existing proof
  directories; outputs = two graphs + one merged graph + round-trip diffs,
  retained under `proofs/`. No new video ingestion required.
- Measures and acceptance threshold: round-trip diff empty/whitespace-only for
  both proofs; 100% of evidence pointers resolve; dedup and contradiction output
  spot-checked against the source artifacts and recorded.
- Risks, constraints, and rights/privacy implications: graph schema churn could
  strand early proofs (mitigate: SKILL.md stays the compiled artifact of record;
  the graph is derived until proven); session transcripts contain user content —
  the beast-reflection redaction/local-only rules apply to any transcript-fed
  node; source attribution must survive graph transforms.
- Evidence: Dreams API — verified (first-party doc fetched 2026-08-03; corrected
  same day from an earlier over-confident "does not exist in Claude Code" via
  direct re-verification). CLI Auto Dream — observed, secondary sources only.
  Codex↔Claude schema disjointness — reproduced + measured (collector run
  2026-08-03: 11 files / 0 messages parsed). Graph substrate itself — no evidence;
  hypothesis only, nothing built.
- Decision: log as observed; run the round-trip experiment before any build-out;
  no novelty claim without a documented exhaustive prior-art sweep (agent-memory
  graphs are an active area — assume occupied until shown otherwise). Requesting
  Dreams research-preview access is independently worthwhile as a first-party
  consolidation baseline to compare against.
- Revisit trigger: OPP-20260731-01 completes its first end-to-end
  tutorial-to-verified-skill run (producing this entry's input data), OR Dreams
  research-preview access is granted, whichever comes first.
