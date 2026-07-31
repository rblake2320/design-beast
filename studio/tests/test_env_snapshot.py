"""Offline tests for env_snapshot — no ComfyUI, git repo, or GPU required."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import env_snapshot


def _fake_comfy(tmp_path: Path) -> Path:
    comfy = tmp_path / "comfy"
    (comfy / "custom_nodes" / "some-node").mkdir(parents=True)
    (comfy / "models" / "checkpoints").mkdir(parents=True)
    (comfy / "models" / "checkpoints" / "tiny.safetensors").write_bytes(b"weights!")
    return comfy


def test_graph_model_names_finds_all_loader_keys():
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "a.safetensors"}},
        "2": {"class_type": "UNETLoader", "inputs": {"unet_name": "b.safetensors"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "c.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "not a model"}},
        "5": {"class_type": "LTXAVTextEncoderLoader",
              "inputs": {"text_encoder": "d.safetensors", "ckpt_name": "a.safetensors"}},
    }
    assert env_snapshot.graph_model_names(graph) == [
        "a.safetensors", "b.safetensors", "c.safetensors", "d.safetensors"]


def test_capture_and_write_roundtrip(tmp_path):
    comfy = _fake_comfy(tmp_path)
    run_dir = tmp_path / "run1"
    graph = {"1": {"class_type": "CheckpointLoaderSimple",
                   "inputs": {"ckpt_name": "tiny.safetensors"}}}
    target = env_snapshot.capture_and_write(
        run_dir, comfy, comfy / "venv" / "python.exe", graph)
    assert target is not None and target.name == env_snapshot.SNAPSHOT_NAME
    snap = env_snapshot.load(run_dir)
    assert snap["schema_version"] == env_snapshot.SCHEMA_VERSION
    assert snap["graph_sha256"]
    assert snap["models"]["tiny.safetensors"]["sha256"]
    # non-git dirs record commit None rather than failing
    assert snap["comfy"]["commit"] is None
    assert "some-node" in snap["custom_nodes"]
    # a missing venv python degrades to null digests, never an exception
    assert snap["packages_sha256"] is None


def test_model_hash_cache_persists_and_hits(tmp_path):
    comfy = _fake_comfy(tmp_path)
    names = ["tiny.safetensors"]
    first = env_snapshot._model_records(comfy, names)
    cache_file = comfy / env_snapshot.HASH_CACHE_NAME
    assert cache_file.exists()
    cached = json.loads(cache_file.read_text())
    assert len(cached) == 1
    second = env_snapshot._model_records(comfy, names)
    assert first == second


def test_missing_model_is_recorded_not_fatal(tmp_path):
    comfy = _fake_comfy(tmp_path)
    records = env_snapshot._model_records(comfy, ["ghost.safetensors"])
    assert records["ghost.safetensors"]["sha256"] is None


def _snap(**overrides):
    base = {
        "schema_version": "1.0", "python": "3.12.10",
        "comfy": {"commit": "aaaa" * 10, "dirty": False},
        "custom_nodes": {"nodeA": {"commit": "bbbb" * 10, "dirty": False}},
        "packages_sha256": "p1", "package_count": 100, "torch": "2.7.1+cu128",
        "graph_sha256": "g1",
        "models": {"m.safetensors": {"sha256": "m1", "bytes": 8}},
    }
    base.update(overrides)
    return base


def test_diff_no_drift_is_empty():
    assert env_snapshot.diff(_snap(), _snap()) == []


def test_diff_names_each_component():
    current = _snap(
        comfy={"commit": "cccc" * 10, "dirty": True},
        custom_nodes={"nodeA": {"commit": "dddd" * 10, "dirty": False},
                      "nodeB": {"commit": None}},
        packages_sha256="p2", package_count=101, torch="2.8.0+cu129",
        models={"m.safetensors": {"sha256": "m2", "bytes": 9}},
    )
    drift = "\n".join(env_snapshot.diff(_snap(), current))
    assert "ComfyUI:" in drift
    assert "nodeA" in drift and "ADDED" in drift and "nodeB" in drift
    assert "torch: 2.7.1+cu128 -> 2.8.0+cu129" in drift
    assert "package set changed" in drift
    assert "model changed: m.safetensors" in drift


def test_diff_flags_removed_node_and_missing_model():
    current = _snap(custom_nodes={}, models={})
    drift = "\n".join(env_snapshot.diff(_snap(), current))
    assert "REMOVED" in drift and "nodeA" in drift
    assert "model MISSING: m.safetensors" in drift
