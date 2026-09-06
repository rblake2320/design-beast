# Mobile evidence and legacy promotion containment

Base: `1a7f7aba07be3616a5091a8d038a661c6845941a`. Owner request: reuse useful
PhoneClaw concepts in owner projects, leave PhoneClaw untouched. Companion:
Vigil branch `codex/beast-mobile-20260906` based on `e33834a`.

## Outcome and boundaries

Implemented original ADB observation, exact UI checks, foreground/package/serial
guards and explicitly authorized tap with durable intent and unknown-outcome
receipt. One shared Python SDK serves Beast CLI and Vigil. No upstream code copied.
Physical-device execution is UNVERIFIED: ADB absent from checked locations/PATH.
No device attached/selected, model loaded, screenshot captured or paid call made.

## Defect closure record

Observed: legacy exporter labeled empty/rejected/unverified claims evidence-backed;
validator accepted a nonempty dictionary containing a failed replay. Mechanism:
unconditional flags and truthiness. Escape: narrow tests exercised approval flags,
not empty/rejected/failed execution. Sweep: legacy exporter and validator both
contained; PR #14's stronger independent custody contract is not modified here.
Control: legacy exports are explicitly non-promotable candidate bundles and reject
verified/rejected/empty claims. Regression: `test_legacy_promotion_boundary.py`.
Residual: verified promotion requires integrating the existing receipt-bound path;
this branch does not declare that integration complete.

Independent review found malformed-shape escapes, stale action guards and XML
hash/parse double-read. All three addressed with regressions in `test_mobile.py`.
Capture and tap use monotonic age budgets; parsed UI is the hash-checked bytes.
Reviewer's retest: 26 SDK/export tests and nine Vigil tests passed; no remaining
code blockers in reviewed scope. Secure/redacted-screen claim narrowed as requested.

## Executed checks on Windows / Python 3.12.10

- Full Beast suite: **292 passed, 7 live-GPU tests deselected**, 7.66 seconds.
- Focused mobile plus evidence tests: **49 passed**, 0.48 seconds.
- Capability graph: eight capabilities, one pack, zero structural errors.
- OpenAPI generation check: unchanged/up to date.
- Fatal-error Ruff and `git diff --check`: passed.
- Built `beast_studio_client-1.1.0-py3-none-any.whl`, SHA-256
  `9558c6c1b64aa3ac97b682e2f0e0bc8ec67b1316bd3510ab95420c5623848805`.
- Installed wheel without dependency changes into `D:\content\beast-mobile-installed-proof`.
- From Vigil's checkout, imported installed `mobile.py` from that directory.
- Installed SDK and actual Vigil command both classified missing ADB and returned
  failure, rather than fabricated device evidence.

These are actual package/CPU and denial-path checks, not Android success proof.
Transport fault tests use controlled replacements; real device transport tests: zero.
Source tests do not establish 10/1,000/500,000-user readiness or creative quality.

Reproduce CPU checks: `python -m pytest -q`. Build SDK:
`python -m pip wheel --no-deps sdk/python --wheel-dir YOUR_OUTPUT_DIR`.
Real device acceptance instructions and privacy limits: `docs/MOBILE-EVIDENCE.md`.
