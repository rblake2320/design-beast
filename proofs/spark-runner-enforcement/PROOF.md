# DGX Spark runner-enforcement proof

- Run ID: `SPARK-RUNNER-ENFORCEMENT-20260804A`
- Local date: `2026-08-04`
- Evidence state: **systemd enforcement reproduced on both Sparks; runner implementation not built or proven**
- Purpose: test the operating-system primitives proposed by PR 17 before accepting its design claims

## Claims this run supports

On the two tested DGX Spark hosts, systemd 255 with unified cgroup v2 enforced all of the following for a transient `Type=exec` service:

1. `DevicePolicy=closed` denied NVIDIA GPU discovery (`nvidia-smi -L` returned nonzero).
2. `IPAddressDeny=any` plus `RestrictAddressFamilies=AF_UNIX` denied both AF_INET socket creation and outbound network access.
3. `RuntimeMaxSec=2`, `TimeoutStopSec=3`, and `KillMode=control-group` stopped a deliberately long-running workload and left its child process dead.
4. The probes did not stop the pre-existing UltraRAG, llama.cpp RPC, or `run_live.py` processes.

These are observations on the two named hosts under the exact tested properties. They are not a generalized guarantee for other Linux hosts or alternative unit types.

## Claims this run does not support

- PR 17 is a design proposal; no overnight-runner implementation, timer, queue, restoration database, or signed-manifest admission path was executed.
- Disk-write isolation and quota exhaustion were not tested.
- A human-controlled signing key was not created, and no human authorization signature was fabricated.
- Lifecycle freshness, capability demotion, result quality, and multi-night reliability were not tested.
- No GPU model, benchmark task, cloud API, download, or paid action was run.
- No claim is made that `Type=oneshot` enforces the tested wall-clock limit. It did not.

## Hosts and preserved workloads

| Item | Spark 1 | Spark 2 |
|---|---|---|
| SSH alias | `spark1` | `spark2` via `ProxyJump spark1` |
| Host | `spark-3cdf` | `spark-3173` |
| Architecture | `aarch64` | `aarch64` |
| systemd | `255.4-1ubuntu8.16` | `255.4-1ubuntu8.12` |
| Cgroup mode | unified v2 | unified v2 |
| Kernel | `6.17.0-1021-nvidia` | `6.17.0-1008-nvidia` |
| NVIDIA driver | `580.159.03` | `580.126.09` |
| Initial GPU use | 0% | approximately 60-63% |
| Preserved workload | UltraRAG gunicorn workers | llama.cpp RPC and `run_live.py` |

Post-test process checks found all recorded workload PIDs still alive. Spark 1 remained at 0% GPU utilization and Spark 2 was observed at 63%. The differing kernels, systemd package revisions, drivers, and load levels are retained rather than normalized away.

## Evidence trail, including failures

### Attempt 0 — invalid local invocation

The first command used nonexistent aliases (`spark-1` / `spark-2`) and allowed PowerShell to expand Linux shell syntax locally. It caused no remote action and supports no enforcement claim.

### Attempt 1 — invalid command containment

The first remote transient-unit probe had incorrect quoting. `systemd-run` contained only the initial shell operation while GPU and network checks escaped the unit. Its exit code was therefore invalid evidence. The collected transient units exited without stopping existing workloads.

### Attempt 2 — isolation reproduced

The corrected probes transported their payloads without PowerShell interpolation and ran inside these cgroups:

```text
/system.slice/beast-pr17-sandbox-1785891828.service  (Spark 1)
/system.slice/beast-pr17-sandbox-1785891830.service  (Spark 2)
```

Tested properties included:

```text
DevicePolicy=closed
IPAddressDeny=any
RestrictAddressFamilies=AF_UNIX
RuntimeMaxSec=20
MemoryMax=128M
TasksMax=32
```

On both hosts, `nvidia-smi -L` returned 255, AF_INET socket creation returned 1, outbound access returned 1, and the enclosing `systemd-run` completed successfully. This is the retained basis for the GPU/network-denial claim.

### Attempt 3 — `Type=oneshot` timeout falsified

`Type=oneshot` with `RuntimeMaxSec=2` did **not** stop a 30-second workload at the declared limit on Spark 1. It completed in roughly 30 seconds and returned zero. The client-side parallel command timed out before a usable Spark 2 result was retained. This configuration is rejected for the proposed runner.

### Attempt 4 — `Type=exec` timeout reproduced

The corrected timeout contract was:

```text
Type=exec
RuntimeMaxSec=2
TimeoutStopSec=3
KillMode=control-group
MemoryMax=128M
TasksMax=32
```

Spark 1 returned nonzero after about 2 seconds; Spark 2 returned nonzero after about 3 seconds. Follow-up PID checks found neither child alive. A future implementation must probe the instantiated unit with `systemctl show` and refuse execution if these effective properties do not match the requested contract.

## Design consequence

The hardware test narrowed PR 17 in two ways:

1. The runtime unit must use the reproduced `Type=exec` contract. The disproven `Type=oneshot` timeout path must remain in the record, not be hidden by the later pass.
2. The authoritative user public key cannot live in the agent-writable repository. It must be installed outside the checkout (the reviewed design uses `/etc/beast-runner/trusted_user.pub`) and validated for owner, mode, and expected fingerprint before admission.

The second conclusion is architectural reasoning, not a signature-path execution result. A repo-pinned key would let an agent capable of pushing commits replace its own trust root.

## Verdict

**PASS:** GPU denial, network denial, and `Type=exec` runtime/cgroup termination were reproduced on both DGX Sparks without stopping the recorded existing workloads.

**FAIL (retained):** `Type=oneshot` did not enforce the proposed two-second wall-clock limit in the retained Spark 1 test.

**NOT RUN:** the runner, timers, signed authorization, restoration state machine, lifecycle probe, task execution, and multi-night operation.
