# Source-faithful integration proof — 2026-09-18

Claim: existing Watch bundles and CPU measurements can be packaged for actual
video review, exported as a strict source-linked editorial plan, and rendered
into a private captioned draft using the original footage.

Executed: installed Chrome headless playback1280x720, seek10s, adjacent stills,
plan download, desktop and390px mobile layout. `ui-06/report.json` records no
page errors/no mobile overflow. Captions are explicitly operator-authored.

Source-offset proof: actual Watch intake from retained Blender source9–11s,
fresh CPU OCR/measurement, two output segments, original-source offset9000ms.
Decoded source regions checked against their matching output frames; no new
scene images. The renderer's source/output map, hashes and verification report
are retained beside this document. Raw working media stays under watched/.

Failures retained, not converted into passes:
- ui01: readiness timeout; ui02: stale helper HTTP child after shell termination.
- ui03: bundled Chromium reports DEMUXER_ERROR_NO_SUPPORTED_STREAMS for H.264.
- ui04: basic HTTP server cannot support the tested seeking path.
- ui05: playback/edit/download worked, mobile overflow failed; fixed footer wrap.
- render01: FFmpeg named-font lookup process crashed; explicit fontfile repaired.
- render02/03: actual image inspection found multiline caption truncation despite
  valid MP4/duration. Explicit per-line placement and pixel-row checks replace
  the insufficient duration-only gate. Final outputs are render04 and later.
- multisegment01: verifier used invalid FFmpeg seek spelling `.5`; corrected0.5.

Full suite:346 passed, one skipped, seven live-GPU tests deselected. Also114 focused tests passed, one pre-existing Windows symlink test skipped. These
include11 new no-model contract/clock/tamper tests; real media/browser runs are
separate and use no mocked renderer/browser. Independent review is separate.

Not established: automated semantic caption creation, all silent-action recovery,
narration/audio, rights clearance/publication, long-form scale, live-capture PR
merge, Clipstitch instructional matching, Jev performance or broader semantic
accuracy. Earlier failed visual-understanding scores remain unchanged.
