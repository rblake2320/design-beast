# Held-out typed visual compiler experiment: Inkscape MetaBalls

## Result

The first held-out execution **failed**, and therefore this experiment does not
promote the typed visual compiler as held-out validated. A post-failure repair
then executed successfully without changing the learned filter values or lowering
any acceptance gate. The repair result is evidence for the specific defect and
repair, not an unbiased held-out pass and not generalization evidence.

The selected tutorial was
[`cT41th-pIJc`](https://www.youtube.com/watch?v=cT41th-pIJc). The compiler was
frozen first in commit `24a4c38`; candidate selection happened afterward. The
selection record is `selection-log.json`.

## Why this required watching

The retained Watch bundle contains 208 timestamped 1920×1080 frames and zero
transcript segments. A separate local Whisper base pass over the retained audio
produced punctuation only and no lexical words. That result is corroborating
evidence, not an absolute claim that the audio contains no speech.

The procedure came from pixels and on-screen text:

- create two circles, arrange them horizontally, and group them;
- add Gaussian Blur followed by two Color Matrix primitives;
- use linked standard deviations of `34.79`;
- use matrix type `matrix` with alpha row `0 0 0 20 -10`;
- enter the group and move one circle closer until the filtered result connects.

The final action is load-bearing. It was absent from the initial target contract
even though it was visible around source times 02:17–02:24.

## Evidence custody

- Source video SHA-256:
  `7385741a8bea4e02b97d3e5f68f743acf9e92ea1f2c7eed54c56b0c833549627`
- Watch timeline fingerprint:
  `c1e69c60cb87cff3b43c60d5deb517eddcdee70981630e71eab045737ceaaa88`
- All 208 timeline frames have ingestion SHA-256 values.
- Final target fingerprint:
  `f586ec2c2165503bd87e4e565ca22d35de759bcddff4ecb39b347f716f46761b`
- Final compiled-state fingerprint:
  `6d7141bf526a137cc5382822c317502abc26c9f822499ab566cfa9cc0325636e`
- Evidence rows bind exact frame IDs, source times, pixel regions, frame hashes,
  and RGBA-region hashes in `typed-state-feedback-repair.json`.

The source UI version is unreported. Execution used Inkscape 1.4.4
(`dcaf3e7`, 2026-05-05). The mapping from the GUI's displayed units to SVG user
units is not assumed universally; Inkscape documents the distinction between GUI
units and stored user units in its
[units documentation](https://wiki.inkscape.org/wiki/index.php/Units_In_Inkscape).
Filter primitive semantics were checked against the
[W3C Filter Effects specification](https://www.w3.org/TR/filter-effects-1/).

## Preserved failures

### Initial held-out run — failed

The original 26-field compiled state was structurally answered, but it omitted
source geometry and movement preconditions. Its execution retained the exact
filter chain yet measured two components and center alpha `0`. Both behavioral
gates failed. The receipt and pixels are in `initial-failure-artifacts/`.

### Fixed-geometry repair — failed

Adding the initial on-screen circle and group dimensions was still insufficient.
The exact filter chain again rendered two components with center alpha `0`. This
second failure, in `fixed-geometry-repair-failure-artifacts/`, proved that the
source's initial layout was not its final execution state.

## Feedback repair — passed on the same tutorial

Reinspection recovered the missing control action: enter the group and move one
circle closer. The repaired target represents that as `move_closer` with the
measurable stop condition `single_connected_component`.

The executor preserved the starting geometry and changed only center distance:

| Search step | Center distance | Components | Center alpha |
|---:|---:|---:|---:|
| 0 | 353.9350 | 2 | 0 |
| 1 | 329.0428 | 2 | 0 |
| 2 | 304.1506 | 2 | 0 |
| 3 | 279.2584 | 1 | 255 |

It stopped at the first measured success. All hard gates passed:

- compiled state was answered;
- primitive order was exactly Gaussian Blur → Color Matrix → Color Matrix;
- standard deviation remained exactly `34.79 34.79`;
- both matrices remained identical 20-value matrices;
- the control had two connected components and an empty center;
- the result had one connected component and center alpha `255`;
- output size was exactly 800×480.

The final execution receipt is
`feedback-repair-artifacts/execution-receipt.json`. The final PNG SHA-256 is
`3a4112e82833c4dc2b304559c1bce17898038e3e8ee867c227d7b71255f27608`.

## Claim boundary

Proven here:

- the frozen compiler exposed a real completeness defect on a tutorial selected
  after freeze;
- uncertainty-driven reinspection recovered a missed visual control action;
- a typed feedback repair executed in a real installed application and passed
  unchanged structural and pixel gates;
- both failed attempts remain in the evidence record.

Not proven here:

- that the original frozen compiler passed a held-out task;
- that the repaired feedback representation will pass a new unseen tutorial;
- that Beast improves performance across domains;
- novelty, uniqueness, or category ownership.

The next valid promotion attempt is a newly selected tutorial that the repaired
target/compiler/executor have not seen, followed by the predeclared matched-run
benchmark. The original pilot remains non-promoted.
