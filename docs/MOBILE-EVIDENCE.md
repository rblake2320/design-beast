# Shared Android evidence for Design Beast and Vigil

This is an original, local ADB adapter inspired by the useful separation of
accessibility targeting and screenshots in PhoneClaw. No PhoneClaw source was
copied, modified or contributed upstream. There is no downloaded script runner,
cloud vision dependency, credential store or background scheduler.

Design Beast owns `beast_studio_client.mobile`; Vigil consumes that same package.
The package is usable by other owner projects without another implementation.
It offers `AndroidDevice.observe`, `AndroidDevice.tap`, `load_observation`, and
`check_observation`. SDK 1.1.0 adds this optional mobile surface; the existing
Studio HTTP API contract is unchanged.

## Setup and operation

Use a dedicated test device with Android platform-tools installed and authorized
USB debugging. Install the SDK into the consumer's own virtual environment:

```powershell
python -m pip install "./sdk/python[mobile]"
python scripts/mobile_bridge.py observe --serial YOUR_SERIAL --package com.android.settings --output mobile-evidence
```

The device and foreground package are mandatory. There is no automatic device
selection or application launch. The user opens the allowed app. Observation
captures UI XML and a PNG between matching UI trees, checks foreground focus,
then writes a new immutable-by-convention bundle with hashes and timestamps.
Temporary UI dumps on the device are removed using their exact allocated paths.

For an exact UI check, pass the returned observation path and selector:

```powershell
python scripts/mobile_bridge.py check --serial YOUR_SERIAL --package com.android.settings --observation PATH_TO_OBSERVATION --selector '{"text":"Settings"}'
```

Shell JSON quoting differs between PowerShell versions. Python callers can pass
selector dictionaries directly, avoiding shell quoting.

A tap also requires `--allow-action`, a unique enabled clickable selector and an
expected post-tap selector. It records durable intent before sending the command,
rechecks UI/focus, and observes the postcondition afterward. Action uncertainty
is retained as `outcome_unknown`; this adapter never automatically reissues a tap.
Do not use taps for payments, publication, destructive actions or irreversible
workflow steps without that action's separate authorization.

## Trust and proof limits

- Checks mean an exact selector was uniquely present in a fresh UI hierarchy.
  They do not prove persistence, causality, backend acceptance or task completion.
- ADB snapshots are not atomic; matching trees and foreground checks narrow but
  cannot eliminate changes between inspection and input. Command failures,
  malformed artifacts, changed UI trees, wrong focus and ambiguous selectors
  fail closed. Valid black/redacted screenshots are not automatically detected;
  secure-screen semantics and OEM/API support need device tests.
- Hashes detect changed artifacts against this manifest. The local unsigned
  manifest is not authenticated against a hostile writer who can rewrite it.
- Raw UI text and screenshots may contain private information. Output stays
  local, is excluded from Git by default, and should have owner-defined retention.
- Device inference is not required. Pillow validates the screenshot encoding.

## Verification and existing work

`python -m pytest -q sdk/python/tests/test_mobile.py watch/evidence/tests` covers
freshness, target mismatch, tampering, ambiguity, invalid XML/PNG, explicit action
authority and durable unknown-outcome handling. Transport fault tests are
controlled tests, not device proof. A clean wheel installation must also run the
CLI. Physical-device proof is outstanding until ADB and a named device exist.

The legacy `compile_skill_bundle` now exports only explicitly unverified
candidate bundles; empty, rejected and execution-verified claims are rejected.
Execution promotion belongs to the stronger custody contract in existing PR #14,
with lifecycle in #15. This branch does not silently merge or replace those PRs.

PhoneClaw's accessibility selectors map to `select`; screenshot inspection maps
to `observe`; action/result separation maps to `tap` and `check_observation`.
These are the reusable contributions chosen for both owner projects.
