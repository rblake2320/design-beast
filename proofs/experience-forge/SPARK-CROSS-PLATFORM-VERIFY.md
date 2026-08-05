# Spark cross-platform signed-evidence verification

- Date: `2026-08-04` America/Chicago (`2026-08-05` UTC)
- Branch head tested: `c3bbf14`
- Host: `spark-3173` (`aarch64`, Python 3.12.3)
- Source archive SHA-256: `307f4ae2a8b94e43740a81240680b8734a6f21fea7ebf4c529f44a0ad15421e2`
- GPU workloads preserved: llama.cpp RPC PID `2705747`; `run_live.py` PID `2753581`

## Why this test was necessary

The first Linux transfer exposed a real custody defect: signed evidence that verified in the Windows worktree did not necessarily match the bytes committed and materialized on another platform. Git's text normalization changed some signed files. That initial committed-chain verification failed and is not represented as a pass.

The repair marks `proofs/experience-forge/**` as `-text` in `.gitattributes`, making Git retain exact signed bytes instead of performing platform line-ending conversion.

## Retest results

On a fresh archive of repaired head `c3bbf14`, extracted into a new Spark 2 temporary directory:

```text
tests/test_signed_evidence.py + tests/test_lifecycle.py: 11 passed in 0.16s
independent verifier: ok=true, entries=2
chain head: 4623d1a98924cf5849c5fbdae3888c9b21ccf2a3133ccc806e78581b3014f928
signing key SHA-256: 5112b37157919e442d52b22d7f9ddcd13dfa55d28377d6f7f1072d02f36c459a
```

Third-party pytest plugin auto-loading was disabled for the targeted tests because Spark 2's global pytest environment contains an unrelated AnyIO plugin with a missing `typing_extensions` dependency. Before disabling plugin auto-loading, collection failed. This host-environment failure is retained; it is not attributed to the PR 15 code.

A full repository test collection was also attempted and stopped on missing or incompatible host dependencies (`uvicorn` and the global `typing_extensions`/`referencing` combination). No packages were installed merely to make the run pass. Full repository validation remains supplied by Windows and CI; the Spark result supports only the targeted ARM64 lifecycle/signature and byte-portability claims.

## Claim boundary

This run reproduces the lifecycle/signature unit behavior and verifies the committed evidence chain on one ARM64 Linux host. It does not prove production key custody, scheduled execution, all-platform portability, Unreal execution on Spark, or the full repository suite on Spark.
