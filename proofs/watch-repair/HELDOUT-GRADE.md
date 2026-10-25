# Independent held-out repair grade

**Disposition: PARTIAL; not a clean zero-false-claims pass and not procedure extraction.** The recorded states support all five coarse reference changes, but contain an incorrect application-icon identification and unsupported details. The report itself produces adjacent unverified candidates, not adjudicated semantic events.

Reviewer `/root/inspection_review`, 2026-09-18. Reference `HELDOUT-REFERENCE.md` was frozen before outputs, SHA256 `bf9b6daf5cba1453b5cdb9c6a951101dbd79a013a93404d6054eeed820477b80`, and was not edited. Graded `heldout-instruct-01/report.json`, SHA256 `45d84925775196a2fab5d2f918d1187f7c27ecb3b20ad8e95e37e867ad1005a8`. The completed report existed before grading began. Read all 61 observations and directly inspected input frames at clip 15, 16, 17, 17.5, 18, 20 and 20.5, supplementing the previously inspected 61-frame blind reference. No model rerun.

## Frozen five-event assessment

| Event | Recorded evidence | Assessment |
|---|---|---|
| H1 presenter to writing graphic | Presenter at 14.5, partial writing text/graphic at 15 | Supported coarse scene change; the partial paper is described imprecisely as a metallic bookmark-like shape. |
| H2 graphic and text completion | Partial text at 15, full sentence at 15.5/16; paper and pencil described at 16 | Supported before/after representation. No temporal animation mechanism inferred. |
| H3 research-card scene and text | Paper at 16, document cards at 16.5, research heading at 17 | Supported. |
| H4 research text disappears; cards remain/move | Heading at 17, document graphic with only PDF label described at 17.5; differing layered arrangements thereafter | Supports text-disappearance and persistent-card states. Motion is evident in the source; model states do not explicitly recover a motion trajectory. |
| H5 return to presenter | Document graphic at 20, presenter at 20.5 | Supported. |

**5/5 coarse event representations have supporting frame descriptions.** This is an independent reviewer-derived coverage finding, not a claim that the program automatically recovered five verified events. Precise graphic motion, shape transformation and causal instructions are not established by the output. Single-frame labels such as 'static graphic' are not treated as claims that the entire sequence was static; no sequence-level description was generated.

The no-Blender negative control passed in the reviewed descriptions: no sculpting, mesh edits, annotation erasure or arms-unhiding leaked from the previous clip. No application click, file transfer or reproducible action is claimed. Presenter content is mostly described accurately, with some unsupported posture specificity.

## False and unsupported claims

- **At least 1/61 frame-state records contains a clearly false identification:** clip 20 lists Microsoft Teams among the visible icons. Direct image inspection shows a blue cloud-shaped logo, a blue document icon and a green sheet icon; no Teams icon is visible. The same record's own blur disclaimer does not turn the positive identification into verified evidence.
- Clip 18 calls the blurred blue/green file icons Word and Excel. The images do not establish these brands; treat as unsupported specificity, not proven identification.
- Clips 11.5 and 30 describe the presenter as standing. The cropped head/torso view does not establish standing rather than sitting. The blind reference's own introductory 'seated' description is similarly stronger than the image alone proves; this clarification is recorded here without altering the frozen reference and is not used to penalize a contrary posture as definitely false.
- Several records say 'no uncertainty' despite blur or underdetermined state. These assertions are not calibration evidence.

The inventory is conservative, not exhaustive atomic-claim scoring. False model observations remain `unverified_visual_observation`; no false acceptance by a semantic Watch authority was observed. Procedure promotions are zero.

## Execution and custody checks

- 61/61 vision outputs were retained; all 61 OCR statuses are `observed_unverified`, with **zero null TSV fields**. OCR presence does not guarantee OCR accuracy.
- Independently checked **61 input frame hashes against result hashes** and **61 original-source clock mappings** (`source_ms = clip_ms + 300000`); all matched.
- Recorded model digest: `0533d74300e4f9bc367d675d4e64ffd073d50ff16a2b4096cc2e8a1cf8c96319` (`qwen3-vl:8b-instruct`). Protocol observer hash: `07f88e1b29ebb2044281b4e9b313dd34195cbdc1c012ea957b1c04d81213d04e`.
- Unlike the earlier dense original replay, this held-out process used the guard-repaired version. That distinction must remain explicit.

## Boundary

This held-out clip demonstrates stronger bounded description of scene/text changes in a talking-head/motion-graphic video. It is not an interactive software demonstration and cannot establish transferable software procedure learning. Different domain difficulty, dense 61-call sampling and a changed model variant prevent an equal-budget efficiency or generalized accuracy claim. The original Blender replay still fails its stricter semantic challenge; this easier held-out result must not replace that failure.
