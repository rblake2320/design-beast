import importlib.util
from pathlib import Path


BENCH = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_multimodal",
                                               BENCH / "run_multimodal.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)


class Response:
    ok = True
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_edit_is_local_only_and_judged(monkeypatch):
    calls = []

    def post(url, json, timeout):
        calls.append((url, json))
        if url.endswith("/api/judge"):
            return Response({"score": 8, "kill": False, "fix": ""})
        return Response({"id": "job-1"})

    monkeypatch.setattr(rm.requests, "post", post)
    monkeypatch.setattr(rm, "poll",
                        lambda *a, **k: {"phase": "done", "final": "final.png"})
    row = rm.submit({"id": "edit-01", "source_brief": "prod-01",
                     "instruction": "change color", "criterion": "color only"},
                    "edit_tasks", "runs/source/final.png")
    assert row["phase"] == "done" and row["judge"]["score"] == 8
    assert calls[0][1]["allow_cloud_fallback"] is False
    assert calls[1][1]["file"] == "runs/job-1/final.png"


def test_video_and_3d_never_enable_hosted_fallback(monkeypatch):
    bodies = []
    monkeypatch.setattr(
        rm.requests, "post",
        lambda url, json, timeout: (bodies.append(json) or Response({"id": "j"})))
    monkeypatch.setattr(rm, "poll", lambda *a, **k: {"phase": "done",
                                                    "final": "artifact"})
    rm.submit({"id": "v", "source_brief": "x", "motion": "move",
               "criterion": "stable"}, "i2v_tasks", "runs/x/final.png")
    rm.submit({"id": "d", "source_brief": "x", "criterion": "clean"},
              "i23d_tasks", "runs/x/final.png")
    assert bodies[0]["allow_cloud_fallback"] is False
    assert bodies[1]["allow_hosted_fallback"] is False
