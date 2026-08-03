# Beast core foundation proof — 2026-08-03

## Verified implementation

- `python scripts/beast_core.py validate` accepted eight capability records and
  one versioned Beast Pack with graph fingerprint
  `3b09ebeea0e871a66a88fc589d4ad22239aa3678c2a9ad2c3c8880fd067294be`.
- The full non-live suite passed: **212 passed, 7 deselected**.
- A real RTX 5090 measurement reported 32,607 MiB total, 19,893 MiB used, and
  12,295 MiB free while Unreal was open.
- Under the approved BR-006 policy, the 6,144 MiB `judge` workload was admitted
  because its workload plus the protected 4,096 MiB reserve fit. The 24,576 MiB
  `video_generation` workload was denied because it required 28,672 MiB free.
  The denial returned exit code 3 and did not stop any process.
- The Watch-004 real bundle passed the new watching gate using frame `frame-0161`
  at source time 00:15:05: the UI visibly shows the A-key Swizzle order `YXZ`,
  while exact transcript search found no `YXZ`. The fact also references
  `seek-0003`, a retained level-3 forensic reinspection request.

## Boundaries

- The capability graph validates structure and evidence references; it does not
  independently judge whether every cited claim is scientifically persuasive.
- External VRAM admission is a point-in-time check. Another application can
  allocate memory after admission.
- The Beast-loop benchmark scorer is implemented, but the protocol status remains
  `protocol_only_unrun`. No before/after improvement claim has been made.
- One retroactively validated visual-only Watch fact does not establish accuracy
  across arbitrary videos. Existing multi-video proofs establish ingestion
  breadth; the new watching-gate metric still needs the frozen benchmark.
