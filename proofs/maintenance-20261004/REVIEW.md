# Design Beast maintenance review - 2026-10-04

Reviewed remote `main` at `1edb5c2` in a separate clone. The existing
`D:\content\design-beast` checkout had unrelated edits; those were preserved.
Open PRs were inventoried in `open-prs.json`. Earlier Studio optimization,
Blender, and stacked Watch work remains in its own review branches; this change
does not merge those branches or claim their capabilities on `main`.

## Changes and observed outcomes

| Scenario | Original outcome | Result and permanent check |
| --- | --- | --- |
| Install TypeScript package into a consumer's node_modules | Failed: `ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING` | Worked: compiled JavaScript/declarations tarball installs, imports, calls real HTTP, and times out silent SSE; `npm run test:package` |
| 100 ms TypeScript deadline with silent SSE or stalled JSON body | Failed: ~900 ms, ending only when the watchdog closed the server | Worked: ~100 ms with abort and server-observed closure; real HTTP SDK tests |
| SSE split CRLF, multiline JSON, malformed/null/oversized events | Failed: split CRLF produced no terminal events | Worked: parsers join data lines, contain errors, cap incomplete events; transport regressions |
| Python heartbeat followed by silence with 400 ms deadline | Failed in first repair: 750 ms | Worked: caller returns around 406 ms; finite worker closes the socket within its inactivity budget and per-byte reads contain trickles; repeated-call cleanup regression |
| Healthy Python response delayed 150 ms within 800 ms budget | Failed in intermediate repair: read timeout after 125 ms | Worked: ~156 ms success; healthy-delay regression retained alongside timeout cases |
| Generate OpenAPI while a job and GPU lease are active | Failed: job changed running -> failed, lease disappeared | Worked: subprocess isolation preserves exact job/lease snapshots, existing connection, and missing caller database; contract regressions |
| Actual Studio and installed Python wheel | Worked | Health, browser HTML, exact 64x64 upload/download pixels, invalid inputs, unknown job rejection; `scripts/verify_runtime.py` |
| Updated Kokoro model integration | Worked | Local CPU synthesis, 52,736 samples at 24 kHz, 2.197 seconds, decodable non-silent WAV |

The original package error, original timeout failures, and recovery failure are
retained. `runtime-original-check.json` retains a failed case-sensitive HTML
assertion; the page title was uppercase. The corrected live check is `runtime.json`.
The Windows runtime harness terminates its entire owned process tree, including
venv launcher descendants. Independent before/after process inspection found no
surviving Studio processes.

## Technology research and updates

Runtime versions were checked against the public package registry and upstream
documentation, then installed and exercised in an isolated Python 3.12 environment.
FastAPI 0.142.2, Starlette 1.7.0, Pydantic 2.13.5, Requests 2.34.2,
Uvicorn 0.54.0, Kokoro ONNX 0.6.1, and SoundFile 0.14.0 are pinned.
Pillow 12.3.0 and TypeScript 7.0.2 were already current. Node types now match
the supported Node 24 runtime rather than a Node 26 API surface.

- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- [Starlette release notes](https://www.starlette.io/release-notes/)
- [Node TypeScript execution and node_modules restriction](https://nodejs.org/api/typescript.html)
- [TypeScript import extension rewriting](https://www.typescriptlang.org/tsconfig/rewriteRelativeImportExtensions.html)
- [Requests credential-leak advisory](https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7)
- [Kokoro releases](https://github.com/thewh1teagle/kokoro-onnx/releases)

The installed Python distribution also requires Requests >=2.34.2; upgrading
only the application requirements would have left SDK consumers with an older
permitted dependency. Python audit: 65 installed packages, zero known reported
vulnerabilities. npm audit: zero reported vulnerabilities. Audit outputs and a
CycloneDX SBOM are retained; these are dated vulnerability-database results.

CI now uses verified current Actions releases pinned to commit SHA, read-only
repository permission, strict `npm ci`, Python 3.12/3.13 on Windows, and Node
22/24 on Windows/Linux. Existing CI gains installed-package acceptance and
dependency-audit gates, with retained test, wheel, runtime, and SBOM artifacts.
Python transitive dependencies are inventoried in the SBOM, rather than claimed
to be fully hash-locked.

## UI audit

Fixed the false local-only banner while retaining explicit hosted engine choices.
Brighter hint/secondary tokens, named inputs, focus outlines, reduced-motion
states, and 44 px mobile buttons improve readability and accessibility.
Decorative amber glows were replaced with neutral elevation; backend readiness
uses a green fill. No browser console errors were observed. At a 390 px viewport,
document width was 380 px with no visible buttons below 44 px.

The manual design detector's remaining `side-tab` finding is a contextual false
positive: a single red, striped error-tape box intentionally distinguishes a
failure state. It is not a repeated card accent. No detector suppression was added.

| Audit dimension | Score (0-4) | Observed finding |
| --- | --- | --- |
| Accessibility | 3 | Named form controls, focus and reduced-motion treatment; generated media semantics need a separate content-flow review |
| Performance | 3 | One HTML document and no framework runtime; decorative grain remains |
| Responsive | 3 | Desktop and 390 px checks passed; controls stay usable |
| Theming | 3 | Existing dark theme uses shared color tokens |
| Implementation integrity | 4 | Product-specific controls and corrected data-disclosure text |
| Total | 16/20 | Good for the inspected screens; not a WCAG certification |

## Validation and review

Worked: baseline 266 Python tests; final 276 Python tests; 26 TypeScript tests;
typecheck/build; installed tarball and wheel; fatal lint; OpenAPI drift check;
capability graph; actual API/media/speech checks; independent review.
Tests mix deterministic mocks with real SQLite, subprocesses, HTTP sockets,
installed packages, native speech synthesis, and browser inspection. SDK suites
retain the mocked request-contract tests; real transport tests specifically cover
the escaped failures. Seven pre-existing generation/GPU tests remain excluded
by the repository's default test policy. This maintenance changes SDK/runtime
behavior, not generation quality or Watch action recovery.

Independent findings, original failures, artifact hashes and exact versions are
retained in this directory. Builders publish draft PRs and do not merge their
own changes; the remaining handoff is review and merge under the repository rule.

Owner rerun, after installing `requirements-dev.txt` and the Python wheel:

```powershell
python scripts/verify_runtime.py --output .beast/runtime --tts
```

`--tts` requires the existing local Kokoro model and voices; omit it on a clean
machine. The normal CI check does not require model files or GPU services.
