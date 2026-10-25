# Final independent scorer review B

Reviewed committed head `e2fa3571f891ca212b0859124a0c67dc1a5e98c1` for draft PR43. This is a bounded artifact/scorer review, not merge approval. Only this report was created; no media was rerun, no labels or inventoried evidence changed, and no score was overwritten.

## Verified outcome

Recomputed the complete context-repair score in memory by replacing only the scorer's output writer with an in-memory collector. The resulting object equals committed `context-repair/SCORE.json` exactly, including all rows, totals, report hashes, scorer hash and intent hash.

Both arms recover 10/11 inputs, 10 correct control identities and boxes, 10/10 results, and 9/10 temporal candidates with zero false event/result extras and zero false temporal pairs. Both correctly abstain on all 10 unknown-causality cases. Conditional adds zero events beyond baseline, so graduation remains **FAIL**. Unknown-causality agreement is abstention success, not demonstrated causal recovery. Both arms miss the brief case08 input.

Focused checks: `python -m pytest tests/test_watch_relationships.py -q -p no:cacheprovider` passed **25 tests**. The final code implements prefix normalization without relabeling, target identity/IoU plus temporal order for pair credit, event-span/ref agreement, frame path/hash/ref validation, prior-control-reference ordering, mode checks, finite wall/resource checks, scorer hash output, and separate causal correctness totals.

## Evidence custody

- Inventory verification passed: **4,134 files, 72,700,449 bytes**. Independently compared every inventory Git blob against `git ls-tree -r HEAD`; all match the reviewed commit. The inventory deliberately excludes itself and later appended review reports.
- All 20 final source.webm hashes match their report source identities; all report referenced pixels passed scorer verification. Independently checked every actual result interval against its frame-ref minimum/maximum; all match.
- Frozen A label hash remains `c5fe52c9a843093085c972601442d2c8ae8ac52b77686dfafe3ab03339315340`; B remains `5a936a0831b891dc48420bf5df6a3739d685597667a4b0d75bb264644380bf1a`. All four stage intents retain these hashes.
- Initial, ocr-repair and routing-repair each retain 20 reports plus original SCORE.json and separate SCORE-CUSTODY-RECHECK.json, all FAIL. Final context-repair retains its 20 reports and FAIL score. These are separate artifacts, not replacements of the original failures.
- All ten final baseline reports are byte-identical to ocr-repair baseline reports. Context-repair observer intent corresponds to `1248ec5`; ocr-repair intent corresponds to `0f11140`. The two modified observer files match those commits exactly. Six unchanged dependencies match after deterministic LF-to-CRLF checkout conversion; their execution-byte hashes therefore differ from raw LF Git blobs without a source-content mismatch.

## Remaining limits

The result side is less strictly validated than the event side: verify_refs allows an empty result frame_refs list, and grade does not require result start/end to match its refs. A synthetic in-memory copy of final case06 with Saved frame_refs cleared still passes verification and receives result/pair credit. No retained final artifact exhibits this defect: all actual final result spans and refs were independently checked. This remains a general scorer hardening gap, not evidence that the published score is inflated.

The scorer binds pixel bytes and declared refs but does not independently recompute OCR semantics from pixels or decode source PTS. This review did not repeat media/OCR or validate arbitrary hostile report semantics. Focused unit success and the checked corpus do not establish general benchmark robustness.

Final recovery follows repairs on known failed cases, using conditional code1248ec5 against retained baseline0f11140; it is not a fresh blind comparison or paired speed result. The reported160 requested frames per arm,160/140 OCR calls and35.110/31.921 seconds describe those retained executions only. No general causal, deployment, scale, or superiority claim follows.

Conclusion: the committed final score and stated failure boundary are supported by this bounded review; the generic result-reference validation gap should remain explicit. No merge approval is granted.
