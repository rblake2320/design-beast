# Higgsfield creative proof

## Observed outcome

Four GPT Image 2 candidates completed through the authenticated Higgsfield MCP
connector. Lighting was the requested comparison axis; generated geometry also
varied, so this is a creative comparison, not a controlled model benchmark.
Candidate 3 was selected by direct visual inspection. Nano Banana 2 refinement
completed (provider reports model `nano_banana_flash`) at 5504 x 3072, versus
2688 x 1520 candidates. The refinement combines higher resolution and grading;
no separate super-resolution run is claimed. It improves frame visibility,
ceramic glare, and right-edge clutter. This is concept art, not a product UI or
proof that the pictured geometry was reconstructed.

User authorized up to 500 existing credits. Preflights were 4 x 6.5 + 3 = 29.
Observed balance was 3000 before and 2971 after. Five jobs, no resubmissions.
Intent, submission, completed receipts and original image bytes are retained.

## Beast consumer and containment

`test_higgsfield_asset_import.py` uploads the actual refined image through the
existing Studio HTTP route in FastAPI TestClient, verifies byte-identical output
and resolves it through the existing refine/animate input resolver. This is a
real local route test with isolated storage, not a running-production UI test.
No animation, 3D conversion, or downstream cloud request was performed.

Independent review reproduced a failed CLI command containing an input image
URL being falsely accepted by `hf_generate`. The helper now rejects nonzero
exits and contains launch failures/timeouts. Five adversarial process tests
exercise the real helper with substituted process responses. These are not live
CLI generation tests. Successful-exit regex parsing, durable CLI submission IDs,
download limits/redirect validation and exact CLI response schema remain open;
the defect class is CONTAINED, not declared fully fixed.

The installed CLI reports no selected workspace and workspace listing received
no response. This does not establish expired credentials. Local CLI generation
is unverified; MCP access must not be reported as Beast runtime authentication.

## Repeatable offline check

    python scripts/verify_higgsfield_proof.py
    python -m pytest studio/tests/test_higgsfield_failure_barrier.py studio/tests/test_higgsfield_asset_import.py studio/tests/test_higgsfield_proof_integrity.py -q

Ten tests passed: five simulated process failures, one real-pixel route test,
one actual artifact audit, three hostile manifest cases. The offline audit checks
the exact five-file set, distinct job IDs, contained receipts, completed status,
hashes and decoded dimensions. It is not cryptographic provider attestation.

A broader invocation used `-m 'not live'`, accidentally overriding the repo's
`not live_gpu` default. It produced 132 passed and 7 failed: all seven live
Studio tests received connection refused on 127.0.0.1:8787. No server accepted
their requests. `studio-suite.xml` retains that failed run. Do not reuse this
marker override; use the repository default. Passed cases were not rerun just
to replace the failed transcript with a green one.

No Vigil, PhoneClaw, Unreal project, user authentication or billing settings were
changed. No capacity or general autonomous creative-production claim is made.
