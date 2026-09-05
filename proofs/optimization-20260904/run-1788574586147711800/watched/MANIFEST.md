# Beast Watch evidence bundle

- schema: `beast.watch.timeline/v3`
- source: D:\content\design-beast\.worktrees\codex-optimize\proofs\optimization-20260904\run-1788574586147711800\synthetic.mp4
- selected source range: 00:00:00.000 – 00:00:03.000
- frames: 3 (0 scene, 0 targeted-dense)
- transcript: 0 segments (disabled)
- evidence fingerprint: `db5549a7fb37d9a2b97837148423df665b27a6323c6c083808667959abd03035`

## How an agent must read this

1. Search `transcript.txt` and `timeline.json`; do not consume every image blindly.
2. Inspect scene-change frames and frames around statements such as “click”, “set”,
   “change”, “as you can see”, “before”, and “after”.
3. For any uncertain action, rerun `beast watch` with
   `--dense-window START-END@FPS` and keep the new evidence.
4. A demonstrated action is not a learned skill until it has a precondition,
   action, observed postcondition, source timestamps, executable implementation,
   and a passing validation.
5. Cite source timestamps in every extracted procedure step.

## Files

- `timeline.json`: authoritative evidence index and transcript alignment
- `transcript.txt`: human-readable timestamped narration
- `frames/`: source-timestamped evidence frames (`f_<milliseconds>.jpg`)
- `procedure.template.json`: contract for compiling evidence into a verified skill
- `typed-target.template.json`: explicit application/version field types and mappings
- `typed-observations.template.json`: frame-region observations bound to that target
