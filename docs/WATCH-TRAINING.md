# Watch to source-faithful training drafts

One Design Beast entry point connects existing Watch ingestion, CPU pixel/OCR
measurement, real-video review, source-linked editorial planning and FFmpeg
assembly. It does not create another perception engine.

## Use

Run doctor and core validation first. FFmpeg/ffprobe, Tesseract, and the existing
Watch CPU dependencies must be installed. URL intake additionally needs yt-dlp.

```powershell
.\bin\beast.ps1 watch-training prepare --source tutorial.mp4 --start 1800 --end 1830 --output watched\lesson-01
# Open watched\lesson-01\review\index.html in installed Chrome or Edge.
# Play, seek, inspect before/after, enter an explanation, add segments,
# and download training-draft.json. Text is editorial, not machine-certified.
.\bin\beast.ps1 watch-training render --review watched\lesson-01\review --plan "$env:USERPROFILE\Downloads\training-draft.json" --output watched\lesson-render-01
```

Existing work is reused without another model run:

```powershell
.\bin\beast.ps1 watch-training prepare --bundle watched\dense-repair-01 --pixels proofs\watch-pixel-state\fresh-ocr-blender-01 --output watched\lesson-review-01
```

Outputs: real source video, sampled frames, measured-region review aids,
downloadable strict plan, captioned `training-draft.mp4`, and source/output
interval receipts. Caption bands sit below the original picture, never replace it.
The current renderer deliberately omits audio; it is not a narrated lesson.

## Existing components and ownership

| Existing work | Integration / boundary |
|---|---|
| Watch ingest, timeline, seek, typed evidence on main | Reused; perception still belongs to Watch. Use watch-seek for missing detail before rebuilding measurements. |
| Pixel measurement in PR36 | Reused by prepare; source and clip clocks now separated. No new GPU calls. |
| Source Cut review and interval renderer | New connection from evidence to an editorial draft. |
| Clipstitch, separate owned repo | Registered in repos.yml. Spoken-word supercuts remain separate; no claim that matching words selects the correct instructional screen action. No Clipstitch code imported or changed. |
| Full capture PR27 / event probe PR26 | Existing live desktop acquisition remains an unmerged lane. A captured MP4 can be Watch input; their privileged live services are not silently activated here. |
| OmniParser, V-JEPA, Jev | Not required by this CPU draft path. No new semantic-performance claim. |

## Boundaries

- Bounded review: 2–96 retained frames, up to50 segments, 500 characters/segment,
  minimum500ms/segment. Long videos should be explicitly divided into ranges;
  96 sparse frames do not establish full-video action recovery.
- Editorial captions require human semantic review and source-rights review.
  Frame hashes prove custody, not truth of an explanation. Every plan remains
  uncertain and publication-disabled; no procedure evidence is promoted.
- No fabricated images, generated presenters, cloned voices, publication, or
  external spend. No automatic narration or arbitrary-video comprehension claim.
- Installed Chrome was tested. The bundled Playwright Chromium lacked H.264
  decoding on this host. Open the local index directly; Python's basic HTTP server
  is not a seek-capable media server and is not the delivery path.
- A source's actual codec must be supported by the browser. There is no hidden
  generated-image or transcoding fallback.
- Outputs are exclusive. Interrupted directories retain intent/failure and must
  be reconciled; automatic replay into them is forbidden.
- FFmpeg output is30fps; accumulated rounding beyond150ms fails closed. General
  multilingual typography, arbitrary codecs and long-form edit workloads unproven.

## Verification

```powershell
python -m pytest tests/test_watch_training.py watch/tests -q
python scripts/verify_watch_training_ui.py --review watched\lesson-review-01\review --output proofs\watch-training\new-ui-run
```

The browser proof is intentionally frozen to the existing61-frame Blender fixture
(sample20=10s). The render verifier uses the existing1280x720 two-second offset
fixture, two segments and a500-character wide-letter caption; it checks decoded
source pixels and visible caption rows. These are proof cases, not generalized
video understanding benchmarks. See `proofs/watch-training/PROOF.md`.
