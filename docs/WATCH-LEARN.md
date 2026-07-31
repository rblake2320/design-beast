# Beast Watch → Learn

Beast Watch is an evidence pipeline for turning demonstrated work into verified,
repeatable agent skills. It is not a transcript summarizer and it does not claim
that sparse screenshots are continuous video understanding.

## Quick start

```powershell
# Adaptive scene samples + a safety frame every 10 seconds.
.\bin\beast.ps1 watch tutorial.mp4

# Work on one source range. Local files and URLs both preserve source time.
.\bin\beast.ps1 watch tutorial.mp4 --start 12:00 --end 18:00

# Reinspect an uncertain eight-second interaction at four frames/second.
.\bin\beast.ps1 watch tutorial.mp4 --dense-window 12:04-12:12@4

# Build semantic visual memory, then find relevant screens by meaning.
.\bin\beast.ps1 watch-index watched\tutorial
.\bin\beast.ps1 watch-index watched\tutorial "Unreal material editor roughness setting"
```

The base watcher requires ffmpeg and ffprobe. URL ingestion also needs yt-dlp.
If no captions are available, an installed `whisper` or `whisper-ctranslate2` CLI
is used locally. Semantic visual search uses the optional dependencies in
`requirements-watch.txt`; the OpenCLIP weights download on first use.

## Evidence strategy

The watcher merges three sampling lanes:

1. **Scene changes** found through ffmpeg's visual scene score.
2. **Periodic safety samples** for slow edits and missed transitions.
3. **Targeted dense windows** requested after an agent identifies uncertainty.

This is bounded by `--max-frames`. Scene and targeted samples are preferred over
periodic samples, and any required down-selection is distributed across the full
range rather than taking only the beginning.

Every frame stores original-source time, clip-relative time, its sampling reasons,
a perceptual hash, visual change from the prior sample, and near-duplicate status.
The original source range remains intact even when a local video is clipped.

## Bundle contract

```text
watched/<video>/
├── video.mp4                 selected local evidence copy
├── frames/                   source-timestamped JPEG evidence
├── transcript.txt           timestamped narration when available
├── timeline.json             authoritative machine-readable evidence
├── MANIFEST.md               model reading and uncertainty rules
├── procedure.template.json   state/action/validation contract
├── frames.faiss              optional semantic vector index
└── visual-index.json         optional frame/index metadata
```

`timeline.json` uses `beast.watch.timeline/v2`. Consumers must reject unsupported
major versions instead of guessing fields.

## From evidence to a learned Unreal skill

A model extracts procedure steps as:

```text
preconditions → demonstrated action → observed postconditions
```

Each step must cite transcript segments and visual frames. Unclear operations are
not silently filled in; they become uncertainties that trigger a dense reinspection
window or documentation lookup.

The observed GUI action is then mapped in this order:

1. Unreal Python or native MCP operation;
2. Editor Utility Blueprint/Widget;
3. Unreal console command;
4. grounded GUI action as the fallback.

The compiled skill is practiced in a disposable Unreal project and cannot be
published until structural, behavioral, and visual validation pass. A proper skill
package should contain:

```text
learned-skills/<name>/
├── SKILL.md
├── procedure.json
├── evidence/
├── scripts/build.py
├── scripts/validate.py
└── tests/reference-view.png
```

Structural checks confirm assets, actors, nodes, properties, and connections.
Behavioral checks compile/run the result. Visual checks compare viewport captures
with tutorial evidence and the project's art direction. Human approval remains a
separate publication gate.

## Semantic visual memory

`beast watch-index` embeds nonduplicate evidence frames with OpenCLIP and stores
normalized vectors in a Faiss inner-product index. A text query is embedded in the
same space and returns the most relevant source frames with timestamps. This makes
visual evidence across long tutorials searchable without loading every image into
the reasoning model.

Perceptual hashes handle exact/near duplicates. OpenCLIP handles semantic similarity.
They solve different problems and both are retained.

## Safety and epistemic rules

- Watching is evidence collection, not proof of understanding.
- A summary is knowledge, not a skill.
- Generated code is a candidate implementation, not a learned skill.
- Only sandbox execution plus validation promotes a candidate to verified.
- Video-derived facts retain source timestamps and fingerprints.
- Tutorials can be version-specific; Unreal/plugin/version context belongs in every
  final procedure.
