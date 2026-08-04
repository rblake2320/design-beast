# DGX Spark NvPanoptix3D preflight proof

- Run ID: `SPARK-NVPANOPTIX-20260803A`
- Local date: `2026-08-03`
- Evidence state: **cluster readiness measured; TAO software compatibility reproduced; NvPanoptix3D inference not proven**
- Target: two NVIDIA DGX Spark systems connected through their direct ConnectX-7 link

## Claims this run supports

1. Both DGX Sparks are reachable, ARM64, expose an NVIDIA GB10 GPU to Docker, and have enough aggregate unified memory for a future two-node NvPanoptix3D training experiment.
2. MPI can launch one rank on each Spark over the direct link.
3. NCCL `all_reduce_perf` completes across both nodes through the ConnectX-7 RoCE device with zero incorrect values.
4. The pinned ARM64 TAO 6.26.3 image runs on Spark 1, sees CUDA and the GB10 GPU, imports NvPanoptix3D, and exposes its real train/evaluate/inference/export entrypoint.

## Claims this run does not support

- NvPanoptix3D inference, training, quality, latency, or accuracy has **not** been measured.
- The two-node path is functional, not optimized or generalized.
- TAO 7.0.1 was not tested because its documented minimum driver is newer than the installed 580-series drivers.
- No claim is made that two DGX Sparks equal NVIDIA's published reference hardware or performance.

## Environment

| Item | Spark 1 | Spark 2 |
|---|---|---|
| Host | `spark-3cdf` | `spark-3173` |
| Architecture | `aarch64` | `aarch64` |
| GPU | NVIDIA GB10 | NVIDIA GB10 |
| Kernel | `6.17.0-1021-nvidia` | `6.17.0-1008-nvidia` |
| Driver | `580.159.03` | `580.126.09` |
| Direct-link address | `10.0.0.1` | `10.0.0.2` |
| ConnectX-7 | 200 Gb/s, MTU 9000 | 200 Gb/s, MTU 9000 |
| NCCL packages | `2.30.7-1+cuda13.3` | `2.30.7-1+cuda13.3` |

The differing kernel and driver versions are retained as a reliability risk. They were not upgraded merely to make this run look uniform.

## Retained measurements

### Network and collective communication

- Direct-link ping passed in both directions with zero packet loss and approximately 0.24–0.34 ms average latency.
- Cross-node MPI hostname launch returned both real hosts.
- Single-node NCCL all-reduce passed on each Spark with `Out of bounds values: 0 OK`.
- Two-node NCCL all-reduce tested 1 MiB through 64 MiB, one GPU/rank per node, and completed with `Out of bounds values: 0 OK`.
- The NCCL log selected `rocep1s0f0`, reported 200000 Mb/s, and stated `Using network IB`.
- At 64 MiB, the retained cross-node observation was approximately 9.26 GB/s bus bandwidth. This is an observation from this run, not a generalized benchmark.

### Known communication limitation

The same NCCL log reported GPU Direct RDMA disabled and missing `libmlx5` data-direct/dmabuf symbols. NCCL's internal IB transport still passed correctness. Optimizing GPUDirect is separate work and is not required to preserve this readiness result.

### TAO container smoke

Pinned image:

```text
nvcr.io/nvidia/tao/tao-toolkit@sha256:25e38610893454b09bc402f56647f873b0e1e28e7bfd949fb5e3a5f6fbdc8b81
```

Observed on Spark 1:

```text
CONTAINER_ARCH=aarch64
TORCH=2.9.0a0+50eac811a6.nv25.09
CUDA_AVAILABLE=True
CUDA_VERSION=13.0
DEVICE=NVIDIA GB10
NVPANOPTIX_IMPORT=nvidia_tao_pytorch.cv.nvpanoptix3d
actions={evaluate,export,inference,train,default_specs}
```

The local image ID was `sha256:eceddd8329cfbe687c264ec7d04e832a2333db78a86d631cfb78ee2263478bee` with architecture `arm64`.

## Why actual inference stopped here

The shipped inference code calls Lightning `load_from_checkpoint`; the packaged schema requires `inference.checkpoint`, and NVIDIA's official NvPanoptix3D documentation shows checkpoint paths as user-provided values. The inspected container contains model code but no `experiment_specs` directory, tutorial notebook, sample scene bundle, or NvPanoptix3D checkpoint. A current search of NVIDIA's official documentation, GitHub presence, and indexed NGC catalog did not find a published NvPanoptix3D checkpoint.

Therefore a real next run requires one of these:

1. NVIDIA publishes an official compatible checkpoint and sample input; or
2. an authorized 3D-Front or Matterport3D dataset is prepared and Stage 1 then Stage 2 are trained for real.

An untrained network, random weights, a fabricated scene, or a different model would not prove NvPanoptix3D inference and was not substituted.

## Operational recovery

The following pre-existing workloads were paused only for the clean GPU/communication test and then restored:

- Spark 1: `ultra-rag.service` active; `trtllm-multinode` running.
- Spark 2: `cheatvision.service` active; user `llama-rpc.service` active.

Post-restore GPU utilization was observed at 0% on Spark 1 and 5% on Spark 2. No user container, model, or dataset was deleted.

## Primary sources checked

- NVIDIA DGX Spark hardware: https://docs.nvidia.com/dgx/dgx-spark/hardware.html
- NVIDIA DGX Spark clustering: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
- TAO 6.26.3 release notes: https://docs.nvidia.com/tao/tao-toolkit/6.26.03/text/release_notes.html
- NvPanoptix3D documentation: https://docs.nvidia.com/tao/tao-toolkit/latest/text/cv_finetuning/pytorch/panoptic_3d_reconstruction/nvpanoptix3d.html

## Verdict

**PASS:** two-Spark distributed-compute preflight and pinned TAO/NvPanoptix3D software-entrypoint compatibility.

**NOT RUN:** actual NvPanoptix3D inference or training. The missing real checkpoint/data is a recorded dependency, not a lowered gate.
