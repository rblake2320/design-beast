"""No mocked models: deterministic selection/scoring and hostile-input tests."""
import math
import hashlib
import json
import subprocess

import pytest
from scripts.benchmark_vjepa_selection import GitInputs, choose, covered, distance, retain, union_seconds
from scripts.benchmark_vjepa_selection import STARTS, case, run


def test_rank_is_score_driven_and_ties_are_early():
    assert choose({i: float(i) for i in range(1, 7)}) == [6, 5]
    assert choose({i: 1.0 for i in range(1, 7)}) == [1, 2]


@pytest.mark.parametrize("scores", [{1: 1.0}, {i: math.nan for i in range(1, 7)}])
def test_bad_candidates_fail(scores):
    with pytest.raises(ValueError):
        choose(scores)


@pytest.mark.parametrize("vector", [[math.nan, 0], [math.inf, 0], [2, 0], []])
def test_invalid_vectors_fail(vector):
    with pytest.raises(ValueError):
        distance(vector, vector)


def test_distance_is_recomputed():
    assert distance([1, 0], [0, 1]) == 1
    assert distance([1, 0], [1, 0]) == 0
    with pytest.raises(ValueError):
        distance([1, 0], [1])


def test_partial_coverage_does_not_get_credit():
    assert covered((15, 16), [(12, 19.5)])
    assert not covered((15, 16), [(8, 15.5), (20, 27.5)])
    assert not covered((1, 3), [(1, 2), (2, 3)])  # must fit one inspected window
    with pytest.raises(ValueError):
        covered((3, 1), [])


def test_union_does_not_double_count_overlap():
    assert union_seconds([(12, 19.5), (8, 15.5)]) == 11.5
    assert union_seconds([(8, 15.5), (20, 27.5)]) == 15


@pytest.mark.parametrize("path", ["../outside", "/outside", "frames/../../outside", "frames\\outside"])
def test_paths_reject_escape_before_git(tmp_path, path):
    with pytest.raises(ValueError):
        GitInputs(tmp_path).read(path)


def test_atomic_json_rejects_nonfinite(tmp_path):
    target = tmp_path / "receipt.json"
    with pytest.raises(ValueError):
        retain(target, {"score": math.nan})
    assert not target.exists()


class FixtureInputs:
    """Synthetic storage fixture only, never an inference or media-quality proof."""

    def __init__(self):
        self.data = {}
        frames = []
        for index in range(61):
            payload = f"fixture-{index}".encode()
            self.data[f"proofs/watch-repair/inputs/fixture/frames/{index}"] = payload
            frames.append({"file": f"frames/{index}", "clip_seconds": index/2,
                           "sha256": hashlib.sha256(payload).hexdigest(),
                           "perceptual_hash": "0000000000000000"})
        self.put("proofs/watch-repair/inputs/fixture/timeline.json", {"frames": frames})
        for index, start in enumerate(STARTS):
            self.put(f"proofs/watch-pixel-state/vjepa-fixture-01/window-{index:02d}.json", {
                "window": index, "frames": [{"clip_ms": int(f["clip_seconds"]*1000),
                    "sha256": f["sha256"]} for f in frames[start:start+16]],
                "embedding": [1.0]+[0.0]*1023,
                "distance_from_previous": None if index == 0 else 0.0})
        self.put("proofs/watch-pixel-state/vjepa-fixture-01/report.json", {})

    def put(self, path, value):
        self.data[path] = json.dumps(value).encode()

    def read(self, path):
        return self.data[path]


def test_complete_case_selection_with_storage_fixture():
    assert case(FixtureInputs(), "fixture", "fixture")["selections"]["vjepa"] == [1, 2]


@pytest.mark.parametrize("mutation,reason", [
    ("frame", "frame bytes differ"), ("membership", "window membership differs"),
    ("distance", "forged distance"), ("clock", "unexpected sample clock")])
def test_case_rejects_tampering(mutation, reason):
    inputs = FixtureInputs()
    if mutation == "frame":
        inputs.data["proofs/watch-repair/inputs/fixture/frames/0"] = b"replaced"
    elif mutation == "clock":
        path = "proofs/watch-repair/inputs/fixture/timeline.json"
        value = json.loads(inputs.read(path))
        value["frames"][0]["clip_seconds"] = 0.1
        inputs.put(path, value)
    else:
        path = "proofs/watch-pixel-state/vjepa-fixture-01/window-01.json"
        value = json.loads(inputs.read(path))
        if mutation == "membership":
            value["frames"][0]["clip_ms"] += 1
        else:
            value["distance_from_previous"] = 1.0
        inputs.put(path, value)
    with pytest.raises(ValueError, match=reason):
        case(inputs, "fixture", "fixture")


def test_run_failure_receipt_and_no_overwrite(tmp_path):
    output = tmp_path / "run"
    with pytest.raises(subprocess.CalledProcessError):
        run(tmp_path / "missing-repository", output)
    failure = (output / "failure.json").read_bytes()
    assert json.loads(failure)["type"] == "CalledProcessError"
    assert not (output / "report.json").exists()
    with pytest.raises(FileExistsError):
        run(tmp_path, output)
    assert (output / "failure.json").read_bytes() == failure
