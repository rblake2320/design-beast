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
- Evidence update (2026-08-01, execution session; landed 2026-08-03): the
  original revisit trigger has FIRED. The proof-004 skill was executed
  end-to-end against live UE 5.8 (headless BeastLab via MCP): clean compile,
  mapping context runtime-verified via UE log, W/A/S/D signed-axis movement,
  and orient-rotation ±90/180/0 after the step-7 settings — see
  `proofs/watch-004-ue58-first-game/EXECUTION-PROOF.md`. This supplies the
  DIRECT-compilation arm of the matched comparison (measured: ~50 tool calls
  / ~1.5 h blind; ~20 calls / ~15 min with
  `docs/runbooks/UE58-MCP-BLUEPRINT-PATHBOOK.md`). The graph-first arm remains
  unbuilt; no reliability advantage is claimed until the matched comparison
  runs. Boundary: behavioral evidence is positions/velocities/yaw + UE log
  under nullrhi — no screenshots (headless).
- Decision: retain for the next UE execution experiment; do not claim improved
  reliability until the matched comparison is run.
- Revisit trigger (updated 2026-08-03): the graph-first compiler arm exists
  and can be run against the same movement assertions in a disposable project.

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
- Pilot update 2026-08-03: a three-domain, one-task-per-domain ablation measured
  transcript-only, initial adaptive frames, and full Beast. Frames recovered
  visual-only state in Blender, Audacity, and a silent Inkscape tutorial;
  reinspection resolved an Audacity `-3` transient versus the applied `-5` value.
  The run did not promote: an SVG color was mistranscribed during compilation and
  a prose UI label was not normalized to the typed SVG value. A typed evidence
  manifest repaired the artifact byte-for-byte, but that same-task repair is not
  held-out evidence. See `bench/concern-proof/PROOF.md`.
- Newly opened implementation value: the compiler should emit typed,
  target-schema-aware intermediate state (units, enums, transient/final state,
  source frame, confidence) before prose `SKILL.md`. This could reduce semantic
  loss across GUI-to-CLI/MCP translation beyond the current project, but is only
  an observed repair hypothesis until a held-out task passes.
- Revisit trigger: held-out validation of the typed compiler, then the first
  complete non-pilot Beast-loop benchmark report.
- Held-out update 2026-08-03: the compiler was frozen in `24a4c38` before a
  transcript-absent Inkscape MetaBalls tutorial was selected. The first execution
  failed because the target contract captured filter parameters but omitted the
  visual action “enter the group and move one circle closer.” Adding only fixed
  source geometry failed again. Reinspection recovered the feedback action; a
  post-failure repair then moved closer until an unchanged pixel gate measured
  one component and center alpha `255`. This is a measured repair on the same
  tutorial, not held-out validation. Both failures and the passing repair are
  retained in `bench/heldout-typed-compiler/PROOF.md`. The next trigger remains a
  new unseen tutorial under the repaired frozen contract.

### OPP-20260803-03 — Graph-first consolidation of learned procedures and agent memory

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

### OPP-20260803-04 — Evidence-gated distributed physical-AI training on DGX Spark

- Status: observed
- Trigger: run `SPARK-NVPANOPTIX-20260803A` measured correct two-node NCCL
  all-reduce over the direct 200 Gb/s ConnectX-7 path and reproduced the pinned
  TAO 6.26.3 NvPanoptix3D software entrypoint on a GB10 GPU.
- New capability hypothesis: the two local DGX Sparks can serve as a recoverable,
  resource-governed training lane for selected ARM64-compatible physical-AI models
  whose memory or distributed requirements do not fit the Windows creative lane.
- Potential beneficiaries: digital-twin reconstruction, simulation-data pipelines,
  robotics/physical-AI experiments, and Beast capabilities that need isolated
  multi-node GPU work without displacing Unreal or local video workloads.
- Current-project value: creates a measured remote compute lane and a compatibility
  preflight pattern without installing every NVIDIA skill or pulling large images
  onto both nodes before the single-node software path is real.
- Outside-project value: a small, auditable on-prem training appliance may be useful
  wherever datasets cannot leave the local network, but no product claim is made.
- Prior art and primary sources: distributed DGX Spark clustering and NvPanoptix3D
  are documented NVIDIA capabilities, not local inventions. Sources:
  https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html ·
  https://docs.nvidia.com/tao/tao-toolkit/latest/text/cv_finetuning/pytorch/panoptic_3d_reconstruction/nvpanoptix3d.html
- Falsifiable claim: using an authorized supported dataset, a pinned TAO image can
  complete at least one Stage 1 training step on both Sparks through DDP, save a
  reloadable checkpoint, and resume from it without NCCL errors or silent data loss.
- Smallest real experiment: one licensed 3D-Front or Matterport3D subset, a
  predeclared one-step/tiny-epoch training spec, two ranks across the direct link,
  and checkpoint reload on a clean process.
- Measures and acceptance threshold: both ranks participate; loss is finite; NCCL
  reports zero incorrect values/errors; peak memory and elapsed time are retained;
  checkpoint hash is stable and reload succeeds; no service exceeds its resource
  admission; all paused workloads are restored.
- Risks, constraints, and rights/privacy implications: supported datasets have
  their own access/licensing terms; the nodes currently have different kernel and
  driver revisions; GPU Direct RDMA was disabled in the measured correct path;
  NvPanoptix3D supports only FP32 and requires sequential Stage 1/Stage 2 training.
- Evidence: `proofs/spark-nvpanoptix3d/PROOF.md` and
  `proofs/spark-nvpanoptix3d/manifest.json`. Inference/training is explicitly not
  proven because no official NvPanoptix3D checkpoint or sample bundle was found.
- Decision: retain the cluster lane and compatible image on Spark 1; do not pull
  the roughly 80 GB expanded image to Spark 2 or start training until real data and
  the acceptance spec exist.
- Revisit trigger: NVIDIA publishes a compatible NvPanoptix3D checkpoint/sample,
  or an authorized supported dataset subset is prepared for the two-node smoke.

### OPP-20260804-01 — DeepStream MV3DT as the multi-camera 3D tracking substrate

- Status: researching
- Trigger: 2026-08-04 council review (GPT-5.6 arm) surfaced DeepStream 9.1's
  Multi-View 3D Tracking (multi-camera fusion into one 3D coordinate system with
  stable object IDs) + AutoMagicCalib auto-calibration + 10 shipped agent skills.
- New capability hypothesis: Hawk-Eye-grade world-space tracking on our own
  cameras/Sparks — the missing foundation any credible force/motion analysis
  needs; wrap NVIDIA's skills rather than rebuild.
- Hard constraint (single-model claim, verify first): bare-metal DeepStream is
  NOT supported on SBSA/DGX Spark — must run in NVIDIA's SBSA container.
- Prior art and primary sources: NVIDIA DeepStream 9.1 docs/repo (to be verified
  directly — this entry rests on ONE model's research; Gemini returned nothing).
- Falsifiable claim: two calibrated views of one moving object produce a single
  stable 3D track with consistent IDs in the SBSA container on Spark hardware.
- Smallest real experiment: SBSA container on Spark 1, sample multi-view data,
  one MV3DT run, retained track output + calibration receipts.
- Decision: verify NVIDIA docs before any hardware time; then smallest experiment.
- Revisit trigger: primary-source verification of MV3DT + SBSA constraints.

### OPP-20260804-02 — Transformation ledger for media evidence (C2PA/ExifTool)

- Status: observed
- Trigger: same council review; enhancement-vs-recovered-fact boundary needs
  mechanical enforcement once enhancement enters evidence flows.
- New capability hypothesis: every media artifact carries a hash-chained record
  separating original / deterministically-transformed / generatively-enhanced,
  extending studio/ledger.py's custody chain to media transformations.
- Prior art: C2PA standard, ExifTool; our own chained ledger is the native fit.
- Falsifiable claim: given an original frame and an enhanced derivative, the
  ledger proves lineage and transformation class, and the watching gate refuses
  generatively-enhanced pixels as visual-only evidence.
- Decision: park until enhancement is actually used in an evidence path;
  revisit trigger: first enhancement step proposed inside Watch.

### OPP-20260804-01 — Impeccable 4.0: dealt worlds + live decision surfaces

- Status: observed; skill upgrade routed to owner (adoption gate in intake doc)
- Trigger: full beast watch of youtube RVeCbPg0liw (bundle `watched/RVeCbPg0liw`,
  fingerprint `e4655135…f400e01`) plus live release/npm verification 2026-08-04.
- New capability: our adopted website-lane skill now deals human-reviewed design
  "worlds" (188 in deck, hand dealt from the 177 highest-rated by a seeded roll
  API with on-page roll/pool receipts) on a localhost decision page, and its
  live mode does element-picked 1–4-variation iteration with per-variation
  tuners, a Detect pass, and a DESIGN.md token panel — the terminal session
  polls live-mode events. Local install is 2026-04-28-era, pre-worlds.
- Potential beneficiaries: every website/landing-page build routed through
  CLAUDE.md rule 4; any future design-direction selection step in Beast.
- Current-project value: convergent prior art for our multi-candidate → judge
  quality loop, with deterministic deal receipts that echo our provenance
  culture; upgrade closes a two-generation gap in an already-adopted tool.
- Outside-project value: the challenger-deal pattern (reviewed catalog + seeded
  roll + human pick + committed build) generalizes to any generative direction
  choice, not just web design.
- Prior art and primary sources: `github.com/pbakaus/impeccable` (Apache-2.0,
  skill 4.0.4 / CLI 3.5.0, releases read 2026-08-04); impeccable.style worlds
  and slop pages (frames f_000000095000, f_000000235000). No novelty claim —
  this is an upstream feature intake.
- Falsifiable claim: after upgrade, `/impeccable init` on a throwaway project
  opens the worlds decision page locally and live mode round-trips one accepted
  element variation back to the terminal session.
- Smallest real experiment: the post-upgrade verification steps in
  `docs/references/IMPECCABLE-4-INTAKE-20260804.md`.
- Risks and constraints: live mode runs a localhost server (per-session ports
  observed 4750/51905) — loopback-boundary caveats apply as elsewhere; bare
  `npx impeccable install` inside a repo writes a project `.github` install
  (observed and reverted 2026-08-04); Higgsfield's own MCP page says Claude
  Code/Codex should prefer the CLI, which matches our existing lane.
- Evidence: `docs/references/IMPECCABLE-4-INTAKE-20260804.md` (frame-cited).
- Decision: upgrade the global Claude skill via
  `npx impeccable skills install -y --providers=claude --scope=global` (owner
  action; agent write to `~/.claude/skills` is permission-blocked), then run the
  verification; no design-beast pipeline changes until that passes.
- Revisit trigger: post-upgrade verification result, or the next time we design
  a direction-selection step (cite worlds as prior art).
