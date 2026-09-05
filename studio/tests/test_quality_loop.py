"""Real job store + workers; controlled generation, no model calls or GPU use."""
import threading

import pytest

import jobs
import server


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(jobs, "_LOCAL", threading.local())
    jobs.init()
    yield
    jobs._db().close()


@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 8])
def test_at_least_four_candidates_even_with_short_variations(tmp_path, monkeypatch, count):
    req = server.RunReq(brief="test composition", model="gpt_image_2",
                        variations=[f"angle {i}" for i in range(count)])
    jid, _ = jobs.create("create", req.model, req.brief, req.model_dump())
    run_dir = tmp_path / jid
    run_dir.mkdir()
    prompts = []

    def generate(rd, i, prompt, req):
        prompts.append(prompt)
        return {"i": i, "state": "done", "score": 2, "kill": True}

    monkeypatch.setattr(server, "_generate_one", generate)
    server._run_loop(run_dir, req)
    assert len(prompts) == max(4, count)
    assert len(jobs.get_status(jid)["candidates"]) == max(4, count)
    assert jobs.get(jid)["phase"] == "failed"
    for variation in req.variations:
        assert f"{req.brief}; {variation}" in prompts


def test_finished_candidate_visible_while_slowest_is_blocked(tmp_path, monkeypatch):
    req = server.RunReq(brief="progress before slowest", model="gpt_image_2")
    jid, _ = jobs.create("create", req.model, req.brief, req.model_dump())
    run_dir = tmp_path / jid
    run_dir.mkdir()
    release = threading.Event()
    published = threading.Event()
    original_status = server._status

    def status(rd, **updates):
        original_status(rd, **updates)
        if updates.get("candidates") and updates.get("phase") == "generating":
            published.set()

    def generate(rd, i, prompt, req):
        if i != 1:
            assert release.wait(10)
        return {"i": i, "state": "done", "score": 2, "kill": True}

    monkeypatch.setattr(server, "_generate_one", generate)
    monkeypatch.setattr(server, "_status", status)
    worker = threading.Thread(target=server._run_loop, args=(run_dir, req))
    worker.start()
    try:
        assert published.wait(5), "completed candidate hidden behind unfinished workers"
        snapshot = jobs.get_status(jid)
        assert snapshot["phase"] == "generating"
        assert [c["i"] for c in snapshot["candidates"]] == [1]
        assert worker.is_alive()
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive()
    assert len(jobs.get_status(jid)["candidates"]) == 4


def test_best_surviving_candidate_is_graded(tmp_path, monkeypatch):
    req = server.RunReq(brief="select actual best", model="gpt_image_2")
    jid, _ = jobs.create("create", req.model, req.brief, req.model_dump())
    run_dir = tmp_path / jid
    run_dir.mkdir()

    def generate(rd, i, prompt, req):
        return {"i": i, "state": "done", "score": {1: 10, 2: 8, 3: 9, 4: 6}[i],
                "kill": i == 1, "fix": "", "file": f"cand{i}.png"}

    graded = []
    monkeypatch.setattr(server, "_generate_one", generate)
    monkeypatch.setattr(server, "upscale", lambda *_: False)
    monkeypatch.setattr(server, "grade", lambda src, dst: graded.append(src.name))
    server._run_loop(run_dir, req)
    snapshot = jobs.get_status(jid)
    assert snapshot["phase"] == "done"
    assert snapshot["winner"] == 3
    assert graded == ["cand3.png"]


def test_invalid_judge_is_contained_as_candidate_failure(tmp_path, monkeypatch):
    from judge_image import JudgeOutputError
    from contextlib import nullcontext
    req = server.RunReq(brief="invalid judge boundary", model="gpt_image_2")
    jid, _ = jobs.create("create", req.model, req.brief, req.model_dump())
    monkeypatch.setattr(jobs, "gpu_lease", lambda *a, **kw: nullcontext())
    monkeypatch.setattr(server, "hf_generate", lambda *a, **kw: {"file": "cand1.png"})
    monkeypatch.setattr(server, "dead_frame", lambda _: False)

    def invalid(*_):
        raise JudgeOutputError("invalid score")

    monkeypatch.setattr(server, "judge", invalid)
    candidate = server._generate_one(tmp_path / jid, 1, req.brief, req)
    assert candidate["state"] == "failed"
    assert "JudgeOutputError" in candidate["error"]
    assert "score" not in candidate
