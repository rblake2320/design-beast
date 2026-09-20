# Independent repair review A

Reviewed repair implementation reported as commit 0f11140 and retained output watched/relationship-comparison-repair-01. No media extraction, OCR, observer rerun, or label modification was performed. The original CODE-REVIEW-A.md remains unchanged.

## Outcome

The demonstrated routing custody defect is repaired in the reviewed implementation: snapshot_changes operates on the exact source-image bytes already SHA-256 checked inside inspect_pixels. It never reopens paths. OCR now consumes a deterministic PNG mosaic derived from that snapshot, rather than the original JPEG bytes directly; both original image and border-free crops are included. Crop word coordinates are mapped back into source coordinates. This is derived-image custody, not a claim that Tesseract receives the original source JPEG unchanged.

The repair also establishes a shared expected source hash for both arms, freezes eight implementation dependencies, appends supporting repeated-result frame references, starts the arm clock at entry and reports its final-write exclusion, and explicitly retains the inspected interval. These address the corresponding findings in the original review. Requested extraction timestamps still are not verified native frame PTS; retain the scoring tolerance and do not claim exact onset recovery from those timestamps.

## Retained output checks

All 20 arm reports were present and completed at review completion. Read-only verification recomputed all 300 observation frame SHA-256 values, each retained arm source hash, and all eight intent implementation hashes: no mismatch. All reports remained within 16 frame requests, 16 OCR calls and 120 seconds. Each summary retained causal_sufficiency unknown, no accepted causal chains and publication_allowed false. No observed control reference pointed to a later source timestamp in these outputs. These checks inspect existing artifacts; they are not another evaluation run.

Case 01 now yields Idle/Saved in both arms, with Save input and one temporal candidate. Cases 02-04 recover the visible result text in both arms, but conditional arms miss the input. Case 05 retains zero temporal candidates in both arms despite the later Save press; this agrees with its result-before-input visual evidence. The revised OCR path therefore repairs the zero-result-recognition symptom on these retained cases, without demonstrating that conditional scheduling improves event recovery.

## Remaining defects and limits

- Case 06 conditional reports control strings Inseect and See/e, while baseline reports Inspect and Save. A temporal candidate referring to an incorrect control identity is not an identity-correct relationship.
- Case 09 conditional splits Save at 990 ms and See/e at 1100 ms into separate event proposals, then reports Inseect at 2200 ms. OCR instability changes the grouping key and can inflate event count. Scoring must enforce one-to-one event matching and must not award two recoveries for one labeled press.
- The known_controls association uses panel IoU and a single-match test, then overwrites the current control string. It does not explicitly require reference_ms <= event_ms. Coarse frames are processed before rewound frames, so a later source frame could in principle supply the alleged prior label. This was not observed in the 20 retained reports, but the implementation does not enforce the prior-reference claim. Panel relabeling at the same coordinates is another unsupported generalization; current evaluation uses a fixed instrumented UI.
- The mosaic transform is deterministic and covered by the evaluator code hash, but its derived PNG bytes/hash and transform mappings are not retained separately in OCR receipts. Reproduction currently requires reconstructing the transform using the retained source JPEG and the recorded implementation/environment. Do not describe a separately retained mosaic receipt that does not exist.
- Causal abstention is unconditional policy. Twenty abstentions demonstrate conservative output behavior, not discrimination of causal sufficiency. No causal learning, autonomous procedure, or arbitrary-video generalization claim is supported.

No new custody or budget blocker was observed in the completed artifacts. The repaired evaluation is a same-case diagnostic follow-up after the original result-recognition failure, not an untouched blind holdout. Preserve both runs and report the measured misses and wrong identities without further tuning this set.
