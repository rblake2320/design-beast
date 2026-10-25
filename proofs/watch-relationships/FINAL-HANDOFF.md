# Final checks and explicit execution attribution

Draft PR43 remains stacked on PR42 and unmerged. No doctrine changes were made.
The owner instruction to test and repair gaps was already an approved registry
entry; the new scorer lesson was captured as a candidate, not active policy.

- Whole suite after inventory repair:439passed,1Windows symlink skip,
  7live-GPU deselections (`TESTS-FINAL.xml`).
- Final result-reference guard:27focused tests passed. The scorer now rejects
  empty result refs and intervals inconsistent with retained refs, in addition
  to independent order/control/source checks. Final rescore preserves the exact
 10/11input,10control,10result,9/10temporal-pair tie and zero false candidates.
- `ARTIFACTS.json` was built from staged Git blobs and verified4134files,
  72,700,449bytes. `.gitattributes` preserves proof bytes across checkouts.
  Later final-review/diagnostic files are separate committed additions; the
  original inventory is not silently regenerated to claim it covered them.
- The inventory creator's first actual invocation failed on an unnecessary
  string `.decode()`. That first publication contained the evidence but no
  inventory. The repaired invocation and create/tamper regression passed before
  the inventory was committed. No failed check was reported as a pass.

The source-native case08 diagnostic explicitly supplies the independently known
1360ms presentation. It uses one real OCR call and recognizes `mouse_down` in
`f-0035.jpg`, hash
`d95fad59440753a64f7aeb1af159c17980728a296ccc1722665e4a9647d3b2fb`.
The pointer still obscures the control text in that isolated frame (raw OCR says
`See`, not `Save`). This is a diagnostic separating input perception from frame
selection, NOT a recovered autonomous event, a control-identity success or an
extra score. Neither16-request schedule selected this input; graduation remains
FAIL. `NATIVE-FRAME-DIAGNOSTIC.json` retains the complete raw result.

Independent reviews verified committed blobs, native frames, one-to-one scoring,
negative cases and retained baseline lineage. Six unchanged imported source
files' execution hashes reflect CRLF checkout bytes while their Git blobs use
LF. Reviewers checked that exact newline transformation; this is not described
as raw-byte equality. New implementation files use LF attributes.

No narration, causal-chain acceptance, procedure publication, GPU model or paid
provider call ran. These recordings test an instrumented local UI and temporal
candidates; the all-unknown causal labels exercise abstention only.
