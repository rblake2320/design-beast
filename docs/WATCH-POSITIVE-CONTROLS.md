# Visible-input controls

This separate experimental branch retains the Blender clip as a negative fixture
and tests actual browser-recorded inputs where the source visibly contains an
input indicator. PR39/40/41 are unchanged.

```powershell
python scripts/record_watch_positive_controls.py --output watched/NEW-CONTROLS
python scripts/prepare_watch_positive_controls.py --root watched/NEW-CONTROLS
# Independent reviewer labels review directories without opening parent telemetry,
# freezes BLIND-LABELS.json and produces case-XX-units.json result-only seeds.
python scripts/compare_watch_positive_controls.py --root watched/NEW-CONTROLS --seeds REVIEWED-SEEDS --output watched/NEW-COMPARISON --tesseract TESSERACT_EXE
python scripts/score_watch_positive_controls.py --run watched/NEW-COMPARISON --labels REVIEWED-SEEDS/BLIND-LABELS.json --output NEW-SCORE.json
```

Requires Python Playwright, installed Chrome, FFmpeg/ffprobe and Tesseract. All
output directories/files must be new. Do not substitute the supplied labels for
a new capture: native recordings are nondeterministic and receive fresh hashes.

The fixture is a local test app, not a natural tutorial. Playwright sends real
browser mouse/keyboard inputs. A DOM-event-driven indicator is rendered as part
of the source UI; it is not added to video after capture. Independent event logs
are withheld from recovery, then exposed only for audit after labels are frozen.
Browser performance timestamps and video PTS are different clocks; do not
subtract them without independently measured alignment. Actual capture is25FPS.

The pixel-only observer uses Tesseract and a narrow grammar for explicit on-screen
DOWN indicators. It does not detect arbitrary button presses or authenticate
input telemetry from any third-party video. OCR words and boxes, requested-frame
timestamps and hashes are retained. It emits input observations, never causal
chains or publication approvals. Scores count each case once, not repeated hits
on the same held input. Semantic checking of emitted frame references remains
part of the independent evaluation.

Identical per-arm caps:16requests,16decodes,16OCRcalls,0VLMtokens;60seconds for
sampling and60seconds for OCR. Actual unique work is reported, not equated with
the cap. This experiment introduces real OCR, not GPU/model performance claims.
The private ground truth files remain absent from scheduler/observer inputs.

Current frozen run: both arms recover all3positive input-indicator cases and
abstain on the matched trimmed negative. The predeclared requirement of MORE
recovered cases for rewind fails on this set (tie). Do not tune these labels or
recapture favorable timings and relabel this run a win.
