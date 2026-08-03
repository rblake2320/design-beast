# Claude concern proof — pilot 2026-08-03

## Outcome

This pilot **does not close the generalized improvement claim**. It proves that
the matched harness works, proves that frames recover information absent from
speech, proves one case where uncertainty-driven reinspection is necessary, and
finds a real compiler defect that prevents promotion.

Frozen envelope: Codex `gpt-5.4`, reasoning `none`, Codex CLI `0.145.0`, Windows,
RTX 5090, Blender `5.1.2`, FFmpeg `8.1.2`, Inkscape `1.4.4`; fingerprint
`fdff2b41289f0e3bcdda33073aef3c004216206239e28117bd5406e3091c07e1`.

| Task | Transcript only | Initial frames | Beast | Receipt |
|---|---|---|---|---|
| Blender flute state | abstained; 1/11 values | 11/11; artifact opens | 11/11; artifact opens | 136 evaluated vertices; Y/45° modifier |
| Audacity ENCNL state | abstained; 5/12 | abstained; 11/12, `-3` vs `-5` unresolved | 12/12; artifact opens | WAV measured exactly `-5.0 dB` |
| Silent Inkscape gradient | abstained; 0/11 | 11/11; artifact opens | failed, 10/11 correct | original pack did not promote |

The SVG failure had two stages. First, compilation transcribed the final pink
RGBA as `ec1dbeff`; original-pixel review established `ec146eff`. After that
correction, prose still encoded the UI label `Direct` without the typed SVG
value `repeat`, and the agent abstained. A separately labeled repair changed the
compiled state to a typed manifest. It then rendered a 640×640 PNG with 359
measured row transitions and the exact same SHA-256 as the raw-frame condition:
`DC3493F9A8FE2F26271C6D8AFEB433B8D7B765EA746C8CAA179BE2A6075A0085`.
That repair is evidence the defect is fixable; it is not substituted for the
failed matched run.

Other artifact hashes:

- adaptive Blender: `01CE1D3C2FBD1EF1690D602FA62BF588B643B3F0F22457B141D056885A97CB5B`
- Beast Blender: `6DDF78525823F457D87E25C992538639041D9E6D31D6CF51CB8766453FA38C3F`
- Beast audio: `F03CFC38CDA5E528966B6D65A7674D5848E82851744D0CCCEAEBDBAFC5382740`

## Evaluator defects closed

1. Missing metrics previously raised `TypeError` instead of failing closed.
2. The scorer did not enforce three tasks per domain.
3. The scorer did not require one frozen envelope or matched repetition IDs.
4. The two-condition protocol could not distinguish frames from reinspection;
   it now has transcript-only, adaptive-frames, and Beast conditions.
5. Blender returns exit code zero on Python traceback unless launched with
   `--python-exit-code`; benchmark execution now requires that flag.

## Claim boundary and remaining gates

Measured: true visual ingestion added facts in all three materially different
domains; reinspection resolved the audio task's transient-value conflict; the
successful manifests drove real `.blend`, `.wav`, `.svg`, and `.png` artifacts.

Not proven: generalized improvement, reliability, novelty, or product breadth.
The full frozen protocol still requires three distinct tasks per domain and
three repetitions per condition. The typed-compiler repair needs a held-out
video task before it can count as improvement rather than test-set repair.
Prior-art rarity remains a separate research question and is not implied by
this performance pilot.
