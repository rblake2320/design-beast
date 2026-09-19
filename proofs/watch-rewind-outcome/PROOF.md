# Tested rewind outcomes — 2026-09-19

The owner requested tests of the previously unresolved claims, not another list
of unattempted limitations. This branch adds counterbalanced execution order and
an executable native-frame/timing proof runner. PR39 and PR40 are unchanged.

## Speed test: PASS on the frozen two-second case

Before execution, `run-01/protocol.json` set the passing condition to at least
8/10 faster pairs and >=10% median paired inspection-time reduction. Ten actual
pairs ran, alternating which arm executed first (five each). Both retained their
16-request and60-second caps, and the same source/result seed.

- Rewind faster in10/10 pairs.
- Median paired time reduction15.2896%.
- Baseline median1.254532s; rewind median1.084917s.
- All ten pairs took23.825727s total wall time including per-pair setup.
- Measured arm times cover extraction and pixel measurement, excluding initial
  copying/setup. Rewind decodes14unique frames versus16baseline, with16charged
  requests each. This is a workload reduction, not evidence of faster GPU hardware.
- No paid inference, TTS, GPU model or cloud credits used in these tests.

The executable report and all pair protocols, timelines, decisions and receipts
are under `run-01/`. The criterion was selected for this experiment, not a claim
of statistical significance or a universal minimum improvement.

## Action recovery test

All60 decoded native frames at30FPS across [0,2s) are retained in
`run-01/native`, with exact presentation timestamps and SHA256 values. Ten contact
sheets provide navigation; full1280x720 JPEGs remain available for close review.
The acceptance criterion is a visible initiating input plus identifiable control
and resulting state. `ACTION-REVIEW.md` records the independent visual test verdict
and its inspected coverage. The machine timing report deliberately leaves the
manual review field pending rather than inventing its result.

## Reproduce

```powershell
python scripts/prove_watch_rewind_outcome.py --review watched/assembled-watch-03/review --units proofs/watch-teachability/result-unit.json --output watched/NEW-OUTCOME-RUN
```

Source video remains in the local review bundle; its hash is frozen in protocol.
Native images and timing receipts are committed for remote artifact inspection.
`scripts/evaluate_watch_rewind.py` defaults to the original arm order; only this
runner alternates the new optional reverse_order argument.

Doctor33OK/1optionalComfyUIoffline/0fail; corevalidateOK. Full local suite:
405passed,1Windows symlink skip,7liveGPU deselected. These software tests are
separate from the10real-media pairs and native-frame semantic review.
