# Design Beast operational optimization

Baseline: `1a7f7ab`. Platform: Windows, Python 3.12.10, RTX 5090 for the optional
local judge only. This is a reviewed development change, not a production-scale
or market-superiority claim. No existing services were restarted or deployed.

## Measured result

Final machine receipt: [run-1788574586147711800/receipt.json](run-1788574586147711800/receipt.json).
Synthetic source video, extracted frames, timeline and reinspection record are
retained in that run directory. No customer media or production databases were used.

| Check | Baseline | Revised |
|---|---:|---:|
| Recent 30 jobs from 20,000 stored rows, 100 warm queries, median | 3.15925 ms | 0.0426 ms |
| Same query, p95 | 3.3998 ms | 0.065 ms |
| Concurrent requests with one idempotency key, 16 threads | 10 errors | 0 errors, one created job |
| Attempt to restart a completed job through set_phase | Resurrected | Terminal state preserved |
| FFmpeg/FFprobe discovery on installed 9.0 | Doctor reports missing | Both executables run |

The roughly 74x median improvement applies only to `jobs.recent()` on this
synthetic, warm-cache, local SQLite workload. It does not measure HTTP latency,
rendering speed, concurrent tenants, cold disk, or sustained production load.
Raw timings and clock implementation/resolution are in the receipt.

Watch extracted three real frames from a CPU-generated three-second test video.
Seek added one new frame and retained the reinspection request. All four SHA-256
hashes were independently rechecked against the actual files. The local Qwen
judge returned a validated verdict in 2.526 seconds; its score of 3 is retained.
That proves integration, not artistic quality or judge agreement with humans.

## Failure mechanisms, escape analysis and controls

| Failure | Verified mechanism and why it escaped | Control and regression |
|---|---|---|
| Installed media tools appeared missing | Three consumers pinned the path to FFmpeg 8.1.2; doctor checked presence rather than execution | Shared version-aware discovery; executable probes; `test_winget_upgrade_and_numeric_version_order` |
| Short variation lists skipped comparison | Candidate count was the supplied list length; tests supplied four variations | Minimum four candidates, preserving user directions; `test_at_least_four_candidates_even_with_short_variations` |
| Fast candidates stayed invisible | Worker loop accumulated results without publishing until all workers finished | Publish each completed batch to authoritative job state; `test_finished_candidate_visible_while_slowest_is_blocked` |
| Malformed judge output could influence selection/refinement | JSON parsing supplied untyped dictionaries and CLI ignored kill when picking a winner | Structural generation schema plus strict semantic/duplicate-field validation and survivor selection; `tests/test_judge_contract.py`, `test_invalid_judge_is_contained_as_candidate_failure` |
| Retried concurrent submissions raised integrity errors | SELECT-before-INSERT raced; existing API test retried sequentially | SQLite unique-conflict arbitration; `test_concurrent_same_key_creates_exactly_one_job` and real before/after receipt |
| Terminal job could become running again | Direct writer guarded only terminal destinations; prior monotonicity tests covered update_progress | Guard all direct transitions; `test_direct_phase_writer_cannot_resurrect_terminal_job` |
| History lookup scanned/sorted all rows | No index on created; baseline had no realistic history volume | Created-time index; query-plan regression and 20k-row benchmark |

Job IDs now retain 12 UUID hex digits rather than four to reduce same-second
collision risk. The primary key remains authoritative. IDs are still opaque;
older run IDs remain readable.

Sweep boundaries: all three hardcoded FFmpeg consumers were migrated; both job
phase writers were examined; judge use through candidate/refine and direct CLI
was checked. This is not an exhaustive security or generation-quality audit.

## Verification and independent review

- Full Python suite: 312 passed, 7 live-GPU tests explicitly deselected. Independent
  reviewer reran the full suite: 312 passed, 7 deselected.
- TypeScript SDK: typecheck passed and 21 tests passed.
- OpenAPI contract current; Beast capability graph and pack validation passed;
  fatal-error lint, compileall and git diff whitespace checks passed.
- Doctor: 33 OK, one optional degradation (ComfyUI stopped), zero failing.
- Reviewer independently verified all final frame hashes and recomputed benchmark
  medians. A separate review probe with eight Python processes and 160 same-key
  requests returned one job and one creation, without errors; this supplementary
  probe is not part of the retained benchmark receipt.

Test boundary: new quality orchestration tests use real SQLite and worker threads
but replace model/generation operations. Parser tests use controlled responses.
The verification receipt uses actual subprocesses, SQLite, FFmpeg, Watch/Seek and
one actual vision-model request, with no mocked operations. It contains no complete
image-generation/refinement/upscale run. No paid backend was invoked.

Reproduce from the checkout:

```powershell
python -m pytest -q
python scripts/verify_optimization.py --output .beast/optimization-proof
# Optional real local vision check (loads a model only if GPU admission passes):
python scripts/verify_optimization.py --output .beast/optimization-proof --judge
```

The verifier creates unique run directories; repeated runs retain failures instead
of replacing earlier evidence. `.beast/optimization-proof` output is local;
inspect it before adding it to version control.

## Retained failed attempts

- `run-1788574303046896800`: verification fixture incorrectly requested 180px
  Watch height; CLI correctly rejected it. Fixture corrected to supported 240px.
- `run-1788574358745586600`: successful CPU proof before optional judge was added.
- `run-1788574440632223800`: detailed numeric/string schema constraints caused
  local inference grammar initialization to fail with HTTP 400. Generation schema
  narrowed to structural types; semantic limits remain enforced in Python.
- `run-1788574544027826300`: verifier used the more expensive image-generation
  resource profile for a judge-only call and correctly denied admission under that
  profile. Corrected to the existing `judge` profile; no policy was weakened.
- `run-1788574586147711800`: final successful CPU plus real local judge proof.

The local Qwen adapter returns an entire schema-constrained JSON answer in its
`thinking` field with an empty `response`. Compatibility is preserved only for
that whole-object form. Prose extraction, contradictory duplicate keys, and
fallback from a nonempty malformed response are rejected. This was discovered by
executing the live model, after controlled tests had passed.

## Remaining product gates

Artistic superiority requires a frozen diverse task set, actual multi-candidate
renders, matched competitor outputs, blinded human ratings, judge agreement,
failure rates, timing and cost. Existing open benchmark/evidence PRs should be
independently assessed before duplicating their implementations.

Current primary-source checks also limit earlier broad positioning claims:
[Comfy Registry](https://docs.comfy.org/registry/overview) supports node versioning,
and [Scenario's API](https://www.scenario.com/features/API) exposes custom model
training and multiple media types. Local ownership plus evidence-backed execution
is a differentiation hypothesis; these changes do not establish exclusivity.
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
documents schema support, but the actual local adapter needed the narrower schema
recorded above. This is why shipped-environment checks remain mandatory.
