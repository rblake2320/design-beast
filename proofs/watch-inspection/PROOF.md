# Watch inspection contract — bounded proof

Date: 2026-09-18. Base: `origin/main` at `1a7f7ab`.
Final implementation run: `run-03/report.json`. Runs 01/02 are retained earlier
iterations and do not certify the later hardening. None is a held-out model test.

## Proven within this experiment

- Strict immutable recommendation contract, existing Watch escalation/seek adapter,
  independent confidence fields and optional uncalibrated option-score provenance.
- Actual FFmpeg extraction from four committed owner-authored synthetic videos.
  Frozen corpus hash: `15323c1157d4898a68ee52b8cbe5a6d20e63d4402c2826905a084c140dfd4a07`.
- Two deterministic schedules run against identical one-inspection, 25-frame and
  60-second budgets. Input context is identical and excludes hidden case labels.
- Eight run-03 executions retained 128 frame references with hashes, original
  video identity, context, decision, intent/result linkage, sampling plan and time.
- Fixed 1-fps sampling: 7 frames per case, found 2/3 pixel-change-positive cases.
  Watch 4-fps schedule: 25 frames per case, found 3/3. Both rejected the static
  control. Zero false transition acceptances and zero procedure promotions.
- The denser baseline cost more frames/time. No efficiency improvement is claimed.
- Three Brier components are emitted separately; the constant control scores are
  not calibrated estimates. Perception target here is only successful decoding.
- Provider spend: USD 0. GPU/model calls: 0. CPU extraction only.

## Validation and review repairs

`tests.xml`: 84 passed, one skipped (OS symlink privilege unavailable), covering
Watch core/seek/typed evidence, evidence tests and new inspection boundaries.
`gate-tests.xml` retains existing Watch publication/injection regression results.
Doctor: 33 OK, one optional degradation (ComfyUI offline), zero failures.
`beast_core validate`: 8 capabilities / 1 pack, no errors; graph not promoted.

Independent review caught pre-write path containment, bundle-writer concurrency,
pre-allocation frame budget, corpus path/empty-case validation and copied-source
custody gaps. Repairs are in run-03 with regressions. Planned and existing frame
paths are checked before mutation; exclusive bundle lock blocks overlapping policy
writers; deadlines propagate to FFmpeg; copied source and runtime expected hash
must match frozen media. Failed/abandoned intents are not silently replayed.

## Not proven

These are luminance controls, not screen-understanding or application-action
evidence. No real silent-action, narration, version-drift or live-capture accuracy
claim. No Jev, SemIf model, VLM or trained local policy run. No new perception
engine, causal procedure recovery, calibrated confidence or generalized speedup.
Legacy direct seek callers must not write the same bundle concurrently. Gate
references are trusted validator inputs, not self-authenticating proof. In-process
policy inputs are segregated but not an OS sandbox for malicious backends.

See `docs/WATCH-INSPECTION.md` for replay and exact operating limits.
