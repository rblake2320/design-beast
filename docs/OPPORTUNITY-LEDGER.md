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

### OPP-20260801-02 — Unreal tutorial dependency-graph compilation
<!-- renumbered from -01 at merge: ID collided with Beast Docs entry above -->

- Status: observed
- Trigger: Watch proof 004 recovered a named Unreal movement procedure from a
  75-minute course: assets, prerequisites, ordered Blueprint actions, and
  compile/play checks are separable from the narration.
- New capability hypothesis: Beast can compile instructional chapters into a
  dependency graph before emitting a skill, then schedule reinspection whenever
  a prerequisite, property, or node is uncertain.
- Potential beneficiaries: Unreal/Unity tooling, Blender workflows, CAD, and
  any visual application with named objects and ordered state transitions.
- Falsifiable claim: a graph-first compiler produces fewer missing-precondition
  and wrong-target failures than direct transcript-to-skill compilation on a
  matched tutorial set.
- Smallest real experiment: compile the movement slice in proof 004 twice—once
  directly and once through an explicit asset/prerequisite graph—then run both
  in disposable UE5.8 projects with identical movement assertions.
- Measures and acceptance threshold: all referenced assets resolve, every action
  has source-time evidence, no compile errors, and W/A/S/D movement plus rotation
  checks pass with retained logs/screenshots.
- Evidence: `proofs/watch-004-ue58-first-game/`; currently a hypothesis with
  source evidence, not a demonstrated advantage.
- Decision: retain for the next UE execution experiment; do not claim improved
  reliability until the matched comparison is run.
- Revisit trigger: first disposable UE5.8 execution of the proof-004 skill.

### OPP-20260803-01 — Evidence-gated cross-session operational learning

- Status: observed
- Trigger: a Claude Code “dreaming” tutorial demonstrated cross-session memory
  reconciliation, while the local Codex install exposed readable JSONL sessions,
  reusable skills, noninteractive execution, and scheduled Codex Automations.
  A 24-hour Beast collector streamed a 292.9 MB active session plus a second
  session into a 52 KB private evidence bundle in 7.2 seconds including tests and
  skill validation: 9,571 JSONL records, 51 retained conversation messages, 11
  recent repository artifacts, zero parse errors, and zero truncations.
- New capability hypothesis: combining cross-session conversation with git,
  proof manifests, replay receipts, tests, and opportunity state can produce
  better evidence-gated knowledge and recovery proposals than transcript-only
  memory consolidation.
- Current-project value: detect repeated Unreal/Watch failure paths, stale or
  conflicting skills, claim debt, reusable procedures, missed opportunities, and
  verified resume points without feeding raw tool/image payloads back to a model.
- Outside-project value: the same proposal-and-approval pattern could support
  auditable operational memory for long-running engineering and creative agents.
- Prior art and current product evidence: the category is occupied. OpenAI Codex
  officially supports reusable Skills and scheduled Automations with results
  returned for review; community skills include `memory-reflect`,
  `session-reflection`, `dream`, and `openclaw-auto-dream`. The tutorial itself
  reports an Anthropic enterprise “dreaming” process. Sources:
  https://openai.com/index/introducing-the-codex-app/ ·
  https://openai.com/academy/codex-automations/ ·
  https://skills.sh/basicmachines-co/basic-memory-skills/memory-reflect ·
  https://skills.sh/jwilger/agent-skills/session-reflection ·
  https://skills.sh/boshu2/agentops/dream ·
  https://skills.sh/leoyeai/openclaw-auto-dream/openclaw-auto-dream
- Differentiation hypothesis, not novelty claim: Beast’s useful distinction may
  be cross-modal evidence and proof-state reconciliation plus strict authority
  gates, not the general idea of agent reflection or memory consolidation.
- Falsifiable claim: after approved reflection proposals update a bounded skill
  or instruction set, repeated matched tasks show higher correctness or lower
  retries/tool calls/elapsed time without new regressions than the pre-reflection
  baseline.
- Smallest real experiment: run `beast-reflection` manually on one 24-hour window,
  approve at most three evidence-backed proposals, then replay five matched tasks
  before and after the changes.
- Measures and acceptance threshold: every proposal has source pointers and a
  validation step; no unattended authority-file edits; no leaked secret fixture;
  at least one predeclared performance or correctness measure improves, none of
  the matched acceptance tests regress, and rejected proposals do not recur
  without new evidence.
- Risks, constraints, and rights/privacy implications: session logs may contain
  private conversation and credentials; raw evidence stays gitignored, common
  secret forms are redacted, reasoning/tool payloads are excluded, and substantive
  changes remain user-approved. “Learning” here means durable instruction/skill
  updates, not model-weight training.
- Evidence: `skills/beast-reflection/`,
  `tests/test_collect_reflection_evidence.py`, and local gitignored bundle
  `.beast/reflection/evidence-20260803T171233Z.json`.
- Decision: retain and manually forward-test before scheduling. No community
  reflection skill was installed because none found was an official trusted
  OpenAI package and the Beast evidence boundary is project-specific.
- Revisit trigger: first reviewed report with accepted/rejected proposal outcomes
  and a matched before/after replay.

### OPP-20260803-02 — Video-grounded verified capability engine

- Status: experiment
- Trigger: Watch retained visual facts absent from tutorial transcripts, sought
  denser source windows when evidence was ambiguous, and two Unreal proof paths
  reached retained execution evidence. MetaHuman work independently demonstrated
  executable evidence-state gates and crash-resumable recovery.
- New capability: the existing eyes, hands, proof, recovery, resource, and
  reflection mechanisms can be governed as one explicit Beast loop rather than a
  collection of creative tools. A procedure cannot satisfy the new watching gate
  without frame-linked visual-only evidence; transcript parsing alone fails.
- Potential beneficiaries: agents operating visual applications, tutorial
  learners, creative-production teams, engine/tool vendors, and regulated
  workflows needing auditable procedure provenance.
- Current-project value: one claim graph, immutable versioned Beast Packs, VRAM
  admission, recovery verification, and a matched benchmark make unsupported
  scope expansion mechanically visible.
- Outside-project value: if controlled tests succeed, demonstrated human work may
  be compiled into cheaper replayable execution without losing provenance or
  increasing unsupported claims.
- Prior art and primary sources: not researched in this implementation pass; no
  novelty or category-ownership claim is made. Video procedure learning, learning
  from demonstration, workflow capture, agent skills, and resource schedulers all
  have established prior art. The experiment concerns their local composition and
  measured effect.
- Falsifiable claim: on a frozen matched task set, the Beast condition improves at
  least one correctness or efficiency measure, does not regress a hard gate, does
  not increase unsupported claims, recovers predeclared visual-only facts, and
  triggers reinspection for intentionally ambiguous video evidence.
- Smallest real experiment: one pilot task followed by three tasks in each of three
  materially different domains, with baseline and Beast conditions repeated three
  times under an identical model/tool/version/hardware envelope.
- Measures and acceptance threshold: `bench/beast-loop-protocol.json`; report all
  runs, hard-gate pass rate, time, tool calls, retries, interventions, recovery,
  peak VRAM, visual-only precision, reinspection recall, and claim errors.
- Risks, constraints, and rights/privacy implications: tutorial rights and site
  terms remain source-specific; recorded UI may contain private data; a point-in-
  time resource admission cannot control later allocations by unrelated programs;
  reflection remains proposal-only until human approval.
- Evidence: `BEAST.md`, `beast/capabilities.json`, `beast/pack.schema.json`,
  `bench/beast-loop-protocol.json`, `scripts/validate_watch_procedure.py`, and
  `docs/decisions/BR-006-APPROVAL-20260803.md`.
- Decision: integrate the contract and measurement machinery; keep the system-level
  improvement hypothesis explicitly unproven until the matched benchmark runs.
- Revisit trigger: first complete non-pilot Beast-loop benchmark report.
