# Research landscape — adjacent-field prior art (2026-08-05)

Truth-maintenance companion to CAPABILITY-MATRIX.md and COMPETITIVE-LANDSCAPE.md.
Those documents compare Beast against **commercial creative-production products**.
This one records **adjacent-field prior art** (research systems, agent-infrastructure
products, standards) that constrains how broadly Beast's categorical claims may be
stated. Rule applied: no "nobody/only" claim survives here without a documented
search, and every retired or scoped claim is preserved as superseded in the source
document's amendment block — history is not rewritten.

Verification status legend: **fetched** = primary source read on the stated date;
**cited** = reported by fleet research, primary source not independently fetched yet.

## Skill governance and signing

**NVIDIA Verified Agent Skills** — fetched 2026-08-05 (also independently verified
by a second fleet session the same day).
<https://developer.nvidia.com/blog/nvidia-verified-agent-skills-provide-capability-governance-for-ai-agents/>
Provides: security scanning (SkillSpector — dependency risks, prompt injection,
trigger abuse, excessive agency, tool poisoning), detached cryptographic signatures
(OpenSSF Model Signing), machine-readable skill cards (ownership, dependencies,
limitations, verification status), a reviewed catalog with distribution.
Stated boundary (the article's own framing): it governs which capabilities
enter a workflow, not how they behave during execution. From that boundary the
following are inferred as out of scope — runtime execution tracking, per-run
generation provenance ledgers, tamper-evident logs during operation,
post-deployment monitoring — inferred, not itemized by the article.
**Implication:** any Beast claim of the form "nobody has verified/signed skills"
is false and retired. Beast's surviving distinction is **per-run, execution-side**
signed evidence (run ledger, proof chains, lifecycle demotion) — a layer outside
the stated scope of NVIDIA's offering. Interop with OpenSSF Model Signing is an open
opportunity, not a rivalry.

## Demonstrations and resources compiled into skills

**Microsoft Resource2Skill** — fetched 2026-08-05. <https://microsoft.github.io/Resource2Skill/>
Distills tutorials, code, documents, and reference artifacts into a hierarchical
Skill Wiki, and **executes chosen skills through MCP into each domain's real
software backend** — domains include web, Excel, Reaper, PowerPoint, Blender, CAD,
and **UE5**. Does not describe result verification, evidence chains, failure
handling, or limitations; success metrics only.
**Implication:** "nobody compiles tutorials into executable skills" and "nobody
executes into real engines via MCP" are false as categorical statements. Beast's
surviving distinction is the custody chain: frame-linked source evidence,
acceptance gates, measured results, retained failures, lifecycle management.

**Google Watch and Learn** (arXiv 2510.04673) — already recorded with primary
sources in OPPORTUNITY-LEDGER.md OPP-20260731-01. Converts online computer-use
videos into executable UI trajectories at scale.

**Microsoft CUA-Skill** — fetched 2026-08-05. <https://microsoft.github.io/cua_skill/>
Large-scale engineered skill library for computer-using agents: skill cells
(minimal intent), parameterized execution graphs (GUI-grounded interactions +
scripts), skill composition graphs; LLM planner selects and instantiates skills;
57.5% on WindowsAgentArena. Does not describe verified execution, evidence chains,
or skill lifecycle management.
**Implication:** formal skill representation and composition is occupied ground.
Beast's surviving distinction is evidence-gated verification and lifecycle
(fitness, drift demotion, signed custody).

## Evaluation and lifecycle research

- **SkillsBench** (arXiv 2602.12670, cited): curated skills averaged large gains;
  **self-generated skills averaged no improvement**. This is the dividing line the
  matched Beast-loop benchmark must beat; until it runs, Beast's self-improvement
  claim stays unproven (BEAST.md already states this).
- **Library drift** (arXiv 2605.19576, cited): uncontrolled skill accumulation
  degrades libraries — the failure mode Beast's lifecycle engine (PR #15) targets.
- **Skill-library survey** (arXiv 2607.10113, cited): reviews 20+ systems; reports
  lifecycle management largely neglected across the field.
- **OSWorld / OSWorld-V2** (github.com/xlang-ai, cited): standardized real-desktop
  computer-use benchmarks; the external yardstick any broad computer-use claim
  will be measured against.

## What this changes in the companion docs

Scoped (not retired) as of 2026-08-05 — see each file's amendment block:

1. CAPABILITY-MATRIX "Tamper-evident chained run ledger — nobody": scoped to
   creative-generation products; adjacent skill-signing and enterprise agent-audit
   infrastructure exists (above).
2. CAPABILITY-MATRIX "Asset delivery INTO engine — nobody": scoped to commercial
   asset SaaS; Resource2Skill (research) executes into UE5 via MCP.
3. CAPABILITY-MATRIX "Competitor video analysis — nobody": scoped to creative
   competitor-analysis tooling; large-scale video-understanding platforms exist
   (e.g. NVIDIA VSS-class, cited).
4. Scorecard "ONLY one" list: now explicitly scoped to the surveyed
   creative-production field.

Claims that survived this pass with their scope intact (documented search, no
counterexample found as of 2026-08-05): enforced multi-candidate judge loop in a
creative suite; vision-QA-as-a-tool; exact-replay provenance for creative runs;
agent-driven brief→judged-asset→inside-Unreal as a shipped pipeline; screenshot-
judged game-look enforcement. These carry their dates and fall to the first
verified counterexample.
