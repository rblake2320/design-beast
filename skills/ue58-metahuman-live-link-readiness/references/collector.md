# Trusted deformation collector

The `BeastEvidenceCollector` plugin is an editor-only UE 5.8 source plugin. Its Win64 package must compile successfully before installation. Install it only in a disposable project, enable it in the `.uproject`, and restart Unreal.

## Preconditions

- the active run has a matching `Saved/BeastProof/<run-id>/bound-ready.json` receipt;
- `BEAST_RUN_ID` still names that run;
- the level-editor viewport is active and framed tightly around the MetaHuman face;
- camera, exposure, actor transform, lighting, resolution, and viewport layout remain unchanged;
- the iPhone subject is connected and the selected UE 5.8 MetaHuman control curve exists.

Live Link Face in **MetaHuman Animator** mode does not use the legacy ARKit curve names. The reproduced UE 5.8 stream exposed `CTRL_expressions_*` properties through `LiveLinkBasicRole`; use `CTRL_expressions_jawOpen` for the jaw-open gate. A missing legacy `jawOpen` property is a channel-name mismatch, not evidence that the phone stopped streaming.

## Capture three poses

Call `scripts/request_pose_capture.py` through Unreal Python or `scripts/ue_remote_exec.py`. Set the subject and curve when needed; keep the labels exact.

```python
import os
os.environ["BEAST_CAPTURE_LABEL"] = "neutral-a"
os.environ["BEAST_LIVE_LINK_CURVE"] = "CTRL_expressions_jawOpen"
exec(open(r"<skill>/scripts/request_pose_capture.py", encoding="utf-8").read())
```

Poll `scripts/capture_status.py` until `pending` is false and require a non-empty receipt path. If it fails, require the persisted error and stop. Repeat for `neutral-b` while holding neutral, then `expression` while holding the deliberate expression.

Each successful receipt contains samples gathered over separate engine ticks, source/host timestamps, frame IDs, run and bound-actor identity/transform, the locked editor-view transform/FOV, the captured PNG path, dimensions, and SHA-256. The plugin refuses an output directory outside the active run, a missing or mismatched `BOUND_READY` receipt, an unloaded bound actor, and overwriting an existing label.

The plugin calculates SHA-256 through UE's `PlatformCryptoContext`. Do not use `FPlatformMisc::GetSHA256Signature` in the editor collector: UE 5.8 on Windows asserts with `No SHA256 Platform implementation`. Preserve any partial PNG from that failure under the run's `failed-captures` directory; it is not a valid pose receipt.

## Measure the receipts

Choose one face crop shared by all three unchanged viewport captures, then run outside Unreal:

```text
python scripts/verify_pose_receipts.py neutral-a.json neutral-b.json expression.json --crop LEFT TOP WIDTH HEIGHT --output measurement.json
```

The verifier rejects mismatched engine/project/subject/curve/view identity, incomplete or non-monotonic samples, escaped image paths, hash/dimension mismatches, unstable neutral captures, insufficient curve change, insufficient continuity, or insufficient rendered change.

`DEFORMATION_MEASURED` still has `promotion_allowed=false`. A visual-region reviewer must confirm that the hashed expression change is the intended facial region rather than hair, lighting, UI, background, or camera motion before any later promotion mechanism is added.
