# Independent scorer review B

Reviewed `scripts/score_watch_relationships.py`, `tests/test_watch_relationships.py`, the frozen protocol, observer implementation, and retained comparison-01 reports. No source edits, media reruns, label changes, or observer calls were performed. Synthetic dictionaries were passed directly to `grade` in memory to check scoring behavior. Review began against implementation 174a8ce; the builder subsequently added status-prefix normalization while this review was in progress.

## Findings

1. **Result vocabulary mismatch, confirmed and reported immediately.** Original scorer compared identities literally; frozen B labels say `Status: Saved` while observer emits `Saved`. A synthetic correctly timed result scored results_correct=0, false_result_extras=1, temporal_pairs_correct=0, false_temporal_pairs=1. Frozen labels must stay unchanged. During review a scorer-only prefix normalization appeared at lines 53-54. This is a scoring repair, not an observer improvement; preserve the original score and identify revised scorer separately.

2. **Temporal order is not independently checked by scorer, reproduced.** The candidate loop maps event/result indices to allowed truth pairs without checking predicted event end against predicted result start or validating event spans against frame references. Synthetic event frame_ref=100ms matched truth100-140ms, but predicted end_ms=300 and result start_ms=200 still received temporal_pairs_correct=1 and false_temporal_pairs=0. The normal summarizer excludes this, so no such false credit is observed in the retained run; this is a scorer trust-boundary defect and missing adversarial regression. Validate candidate order and summary/reference consistency before awarding credit.

3. **Metric presentation gaps.** `causal_sufficiency_correct` is emitted per row but omitted from totals despite protocol requiring separate causal-sufficiency scoring. `abstention_correct` always returns false when required_abstention=false, regardless of prediction; dormant in this all-unknown corpus, but incorrect as a general correctness metric. Temporal/control scores are intentionally independent under the frozen protocol: temporal credit cannot be presented as correct control-grounded relationship recovery. Current graduation does not require successful result or causal recovery; its claim must remain the protocol's bounded input-event comparison.

4. **Integrity validation is partial.** Label bytes and exact ten-case coverage are checked, as are report source identity, completion, resource caps, and causal/publication containment. However the scorer does not verify report `mode` against its directory, reconstruct summaries from observations, check referenced frame hashes, or bind its own implementation hash into intent/output. Intent binds observer code but excludes scorer. Preserve original artifacts and record scorer revision/hash for any corrected rescore. There is no evidence that these gaps were exploited in this run.

5. **Existing tests do not exercise grade/score.** They cover grouping, ambiguous alternatives, no-backward-candidate behavior in summarize, absent target debt, keyboard modality, duplicate timestamps, empty input, snapshot changes and pre-OCR hash rejection. They miss result vocabulary, duplicate event fragments in scorer, false temporal credit, report-mode/source tampering, frozen-label mismatches, and metric aggregation. Direct synthetic duplicate-event check passed: two predicted fragments against one true event produce recovered_events=1 and false_event_extras=1. One-to-one sets prevent simple count inflation; merged long-span events cannot produce multiple true-event credits.

## Retained run observations

All 20 comparison-01 reports were present at review. Every report has zero results and zero temporal candidates. Baseline event counts across cases01-10: 1,1,1,1,1,2,1,0,2,0 (10 total); conditional: 1,0,0,0,1,1,0,0,1,0 (4 total). These are raw observer counts, not independently matched recovery totals. There is no actual temporal recovery to claim and zero false temporal pairs is vacuous here.

Case08 conditional retained observations have result=null even at 2180,3270,4360ms, where the frozen blind review saw Saved. The observer result parser requires adjacent Status/value OCR words to share OCR line identifiers. Result extraction is therefore a separate upstream investigation from the score vocabulary defect. No root cause is asserted solely from code inspection, and this reviewer did not rerun media.

## Freeze checks

Both labels match comparison-01 intent: A `c5fe52c9a843093085c972601442d2c8ae8ac52b77686dfafe3ab03339315340`; B `5a936a0831b891dc48420bf5df6a3739d685597667a4b0d75bb264644380bf1a`. All eight implementation files enumerated by intent matched their hashes at readback. B labels and blind review remain unchanged. Current scorer hash observed after builder prefix edit: `5a4b47c46b82db0291e98502c5cd19c6a042d66023d9436f15120299c5b73601`; tests hash: `d17238ed3d11703d304b4618f679044c843e8587d2014a57c3b2e49ef3cfdc10`.

Verdict: retain failed experiment honestly; scorer normalization is warranted, but cannot recover absent observer results. Fix scoring trust-boundary and regression gaps before treating scoring as an adversarially robust gate. Do not revise frozen media/labels or tune this observer run after its outcome.
