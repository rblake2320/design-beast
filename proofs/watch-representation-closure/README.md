# Historical receipt representation reconciliation

This supplemental verifier preserves all historical receipts and original failures.
Run `python scripts/verify_watch_receipt_representations.py` from a full-history
checkout. A shallow checkout missing named commits fails closed; fetch the four
explicit historical commits before verification. No media decoding or model calls
occur. Optional `--output <new-file.json>` exclusively creates a machine report.
Verify the retained supplemental report using
`python scripts/verify_watch_receipt_representations.py --check-report proofs/watch-representation-closure/verification.json`.

The verifier binds each original receipt and referenced artifact to its immutable
historical commit. It accepts raw byte identity or an explicitly named strict
UTF-8 LF-to-CRLF reconstruction for approved text extensions. It rejects bare CR,
mixed newlines, invalid UTF-8, NUL-bearing transformed text, unknown digests,
binary transformation and semantic-JSON substitution. The digest is computed on
the same bytes used to verify the transformation.

Coverage is deliberately enumerated: PR33 run-03 corpus manifest, eight intent
links, eight timelines and 128 referenced frames; PR34 all 122 original exported
entries; PR35 the two OCR-recovery input links; PR42 both score-to-report links.
This closes technical interpretation of those named packaging discrepancies, not
all historical hash fields, source-video availability, publication authorization,
semantic accuracy, or execution replay. Both raw and reconstructed digests are
retained; neither is mislabeled as the other's exact bytes. No historical manifest
is rewritten and no later correction is attributed to an earlier execution.

Root cause: local execution receipts hashed CRLF bytes while Git stored LF blobs;
prior local-only review did not verify this cross-representation edge. This
verifier is an explicit repeatable detection control, not a retroactive guarantee
that historical exporters were portable. Adoption into required release CI and
owner acceptance of the disclosed representation remain separate decisions.

Recorded verification: 271 receipt edges, zero unexplained mismatches. PR33:
128 raw plus 17 strict CRLF; PR34: 98 raw plus 24 strict CRLF; PR35: two strict
CRLF; PR42: two strict CRLF. The original raw-byte discrepancies remain visible
in every transformed row. The scoped suite passed 20 tests, using byte fixtures
and actual temporary Git repositories (no mocked Git); scoped Ruff passed.
