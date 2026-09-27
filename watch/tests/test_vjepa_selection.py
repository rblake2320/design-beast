"""No mocked models: deterministic selection/scoring and hostile-input tests."""
import math

import pytest
from scripts.benchmark_vjepa_selection import GitInputs, choose, covered, distance, retain, union_seconds


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
