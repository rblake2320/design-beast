# Bounded rewind experiment — 2026-09-19

Separate frontier branch stacked on PR39, which remains unchanged and unmerged.
Implementation: `watch/rewind.py`, `scripts/evaluate_watch_rewind.py` and
`beast watch-rewind-eval`. Reuses Watch's existing inspection executor.

## Actual evidence

`run-02/` retains protocol, seed, all inspection receipts and30 JPEGs (16 baseline,
14 rewind). Raw source MP4 remains local in the existing Watch review bundle and
is not distributed here. Its SHA256 is in protocol; remote reviewers can inspect
the committed extracted frames but cannot independently re-decode without source.

Both arms have16 charged-frame and60-second budgets, the same0..2000ms window,
same result seed and same720px extraction. Baseline uses deterministic Watch's
decision bounded to that window. Rewind takes five coarse samples then11 requests
over1000..1500ms, chosen from measured full-frame RGB differences. Two endpoints
are reused but still charged. No labels, OCR answers or hidden timing truth feed
the selection rule; the externally reviewed result anchor is shared by both arms.

Final CLI run: baseline1.306155s, rewind1.065399s for extraction/measurement,
excluding initial copying/setup. One fixed-order run is NOT speed evidence.
Earlier run01 (preflight validation/schema guards not yet strengthened) is kept
locally unchanged and is not substituted for final code proof.

Independent initial frame inspection found a result-label bracket of1200..1333ms
in baseline and1200..1250ms in rewind. No visible input activation was recovered.
The frames show intermediate rotation and the resulting Front Orthographic label,
not the shortcut/click responsible. Unknown action accuracy remains null; winner
is null. Final independently bound review is alongside this proof when available.

## Checks and scope

- Doctor33OK,1optionalComfyUIoffline,0fail; corevalidateOK.
- `python -m pytest -q -m 'not live_gpu'`:404passed,1Windows symlink skip,
  7GPU deselected.23 new contract/scheduler/preflight tests; preflight fixtures
  contain synthetic bytes and deliberately must not invoke FFmpeg. These are
  distinct from the real-video CLI runs and are not semantic accuracy tests.
- No GPU inference, paid API calls, narration, action execution, procedure
  promotion, public source-video upload, or PR39 modification.

Implemented: strict unresolved evidence debt; bounded backward-window selection;
coarse-to-dense pixel surprise; equal frame caps; source/frame provenance; retained
uncertainty; actual comparison through Watch.

Not implemented/proved: semantic action detector, event graph, causal verification,
reproducibility, learned scheduler, unseen-video gains, human-time savings or
industry superiority. No missing-evidence field is silently cleared by sampling.
This is the first scheduling experiment, not completion of the invention program.
