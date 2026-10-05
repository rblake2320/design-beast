# Independent review — 2026-10-04

Verdict: no remaining actionable code findings in the reviewed diff. Independent verification supports the SDK timeout/parsing repairs, compiled TypeScript distribution, process-isolated schema generation, updated SDK dependency floor, CI changes, and the Windows runtime verification cleanup.

Reviewed `codex/review-upgrade-20261004` in the isolated design-beast checkout. Read CONSTITUTION.md, AGENTS.md, CLAUDE.md, and MULTI-AGENT-REVIEW.md. No code edits, merges, or external messages. This report and distinct reproducer scripts are the only reviewer-owned files.

## Observed final checks

- Worked — Python SDK suite: 42 passed in 8.94s after the final public streaming signature repair. This includes eight real HTTP transport cases plus OpenAPI subprocess/state-preservation tests and mocked request contract tests.
- Worked — TypeScript SDK: 26 tests passed; typecheck passed; a real packed tarball installed into an unrelated consumer imported and executed successfully.
- Worked — installed Python wheel client source hash matches the reviewed source. The installed wheel returned a timeout after 406ms for a 400ms overall wait while the server emitted a heartbeat at 350ms and then stalled.
- Worked — installed Python wheel accepted a healthy terminal status delayed 150ms within an 800ms wait budget, returning `{phase: done}` after 156ms.
- Worked — compiled TypeScript classifies JSON-null polling status as BeastStudioError. A never-ending SSE server observed socket closure 24ms after the terminal event and 110ms for a 100ms silent-stream wait deadline.
- Worked — `verify_runtime.py` exercised the installed wheel against the actual Studio process: health, browser HTML, image upload/download preserving dimensions and exact RGB pixel, and rejection of malformed image/brief plus unknown job. Receipt: `independent-runtime-proof/receipt.json`.
- Worked — Windows CIM process inventory scoped to the exact Studio checkout was empty before and after the runtime script, with no surviving venv-launcher descendants. The script kills its own launched tree via taskkill /PID /T /F and waits for exit.
- Worked — pip check reported no broken requirements. Reviewed the updated Python SDK Requests >=2.34.2 distribution floor, regenerated npm lockfile, compiled package exports, pinned CI actions, six-job OS/runtime matrix, dependency audit/SBOM, wheel build, and runtime artifact retention.

## Failures found and repaired during review

1. P1: Python inactivity timeout restarted after a heartbeat; a 400ms overall wait took 750ms. Reproducer: `independent-probe.py`. The finite wait now has a caller-side wall deadline. Socket/worker cleanup is independently exercised in repeated real HTTP tests and documented as occurring within the remaining finite socket budget.
2. P1: the first worker repair imposed a 100ms read limit and rejected a healthy 150ms response despite an 800ms wait budget. Reproducer: `independent-healthy-delay.py`. Retaining the configured/remaining socket budget restored healthy success; installed-wheel retest took 156ms.
3. P2: polling JSON null escaped as raw TypeError/AttributeError. Reproducer: `independent-null-status.mjs`. Both SDKs now check snapshot shape before accessing phase.
4. P2: the newly introduced public stream_events(timeout=...) argument still exceeded its apparent wall deadline (765ms for 400ms). Reproducer retained in `independent-direct-stream.py`. The original public stream_events(run_id) signature is now preserved, with deadline handling internal to bounded wait. Inspected signature and reran all 42 SDK tests.
5. P2: TypeScript README still described source-only packaging; Python SDK metadata still accepted Requests >=2.28. The distribution documentation and Requests floor were updated. Upstream [Requests advisory GHSA-9hjg-9r4m-mvj7](https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7) identifies the credential-leak boundary as <2.32.4.

Raw original failed observations remain recorded in the distinct probes and this report; the repair does not replace the red history. The reviewer did not run remote CI or speech synthesis; the builder owns those separate execution results.

Registry candidate, deduplicated read-only against REGISTRY.md: verify total deadlines against both slow trickles and late data followed by silence, preserve healthy responses inside the budget, and assert server-observed cleanup separately from caller return. No existing matching inactivity/wall-deadline/body-timeout/OpenAPI orphan entry was found. Builder captures the candidate under the constitution.

Final UI diff was also reviewed read-only: hosted-engine disclosure, form accessible names, hint colors, focus visibility, reduced-motion rules, and mobile target sizing. No new actionable implementation issue found. Browser viewport/console/target-size measurements were performed by the builder and are separate evidence. Final `git diff --check` passed.
