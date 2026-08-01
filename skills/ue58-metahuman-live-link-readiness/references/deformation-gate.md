# Numerical deformation gate

`BOUND_READY` is the v1 skill result. This gate can identify a `DEFORMATION_CANDIDATE`, but it cannot promote a run to `ANIMATION_CONFIRMED` because the current script accepts user-supplied images and summary values rather than collecting raw UE samples and captures itself.

## Capture protocol

1. Start UE 5.8 with SM6 active and no pending restart.
2. Lock viewport camera, resolution, exposure, quality, and character transform.
3. Capture two neutral frames at least 500 ms apart.
4. Collect at least 10 Live Link samples for the neutral pose.
5. Hold one deliberate expression for at least 5 consecutive samples and capture its frame. Prefer `jawOpen`; otherwise name the chosen ARKit coefficient.
6. Crop the same face region from all three frames. Align the crops to the eye centers. Do not include UI, background motion, or camera changes.

## Required thresholds

All gates must pass:

1. **Source delta:** absolute difference between the neutral and expression coefficient medians is at least `0.20` on the normalized `[0,1]` Live Link scale.
2. **Continuity:** the coefficient remains at least `0.20` from the neutral median for at least 3 of 5 consecutive expression samples.
3. **Neutral stability:** normalized grayscale RMSE between the two neutral crops is at most `0.01`.
4. **Rendered deformation:** normalized grayscale RMSE between the neutral reference and expression crop is at least `max(0.03, 5 × neutral_RMSE)`.
5. **Visual validity:** a human or vision model confirms the changed pixels are on the intended facial region and not caused by camera, lighting, hair, UI, or background movement.

Run:

```text
python scripts/measure_two_pose.py neutral-a.png neutral-b.png expression.png --curve-neutral <median> --curve-expression <median> --continuity-passes 3 --visual-validity-confirmed
```

Omit `--visual-validity-confirmed` until a human or vision review has checked the changed region. Even when all gates pass, the script exits with code 3 and returns `DEFORMATION_CANDIDATE`, `promotion_allowed=false`.

## Missing trusted collector

Promotion remains blocked until a collector can produce one run-scoped receipt containing:

- raw timestamped Live Link coefficient samples captured from UE;
- neutral and expression frames captured from the locked UE viewport;
- hashes and paths for every source image;
- camera, exposure, resolution, actor-transform, subject, engine, and project identity;
- crop/alignment parameters and metric outputs;
- a visual-region review tied to those exact hashed frames.

Only that collector—not manually typed curve medians or unrelated images—may authorize an `ANIMATION_CONFIRMED` claim.

The thresholds are a version-one operational gate, not a universal scientific standard. Record the raw values. Recalibrate only from repeated controlled captures, never to make a failing run pass retroactively.

## Failure interpretation

- Source fails, render fails: phone/source problem; animation remains unproven.
- Source passes, render fails: binding/AnimBP/render problem; remains `BOUND_READY` at best.
- Source fails, render passes: uncontrolled visual change; reject the capture.
- Metrics pass but visual validity fails: reject the capture.
