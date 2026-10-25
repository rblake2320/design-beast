import json
import pytest
from watch.teachability import InstructionUnit, gate


def unit(**updates):
    row = dict(unit_id="u1", kind="ambiguous_transition", start_ms=0, end_ms=2000,
        sentence="A confirmation is visible.", frame_refs=[{"clip_ms": 1000, "sha256": "a"*64}])
    row.update(updates)
    return InstructionUnit.model_validate_json(json.dumps(row))


def test_probability_cannot_promote_ambiguity():
    assert gate(unit(perception_confidence=1.,transition_confidence=1.,procedure_confidence=1.))["decision"] == "review_required"


def test_scene_change_omitted():
    assert gate(unit(kind="scene_change"))["decision"] == "omit"


def test_result_does_not_establish_action():
    assert gate(unit(kind="observable_action", verdict="accepted",reviewer="test-reviewer",result_evidence="Frame1 shows a banner"))["decision"] == "needs_recapture"


def test_result_only_export_stays_unverified():
    outcome = gate(unit(kind="observable_result", verdict="accepted", reviewer="test-reviewer",result_evidence="Frame1 shows a banner"))
    assert outcome["decision"] == "eligible_draft"
    assert outcome["verified_procedure"] is False and outcome["publication_allowed"] is False


def test_action_requires_full_declared_chain():
    assert gate(unit(kind="observable_action", verdict="accepted", reviewer="test-reviewer",control_evidence="Save button at1s",
        action_evidence="Pointer activation at1s",result_evidence="Banner at2s"))["decision"] == "eligible_draft"


def test_unnamed_verdict_rejected():
    with pytest.raises(ValueError): unit(verdict="accepted")


@pytest.mark.parametrize("attack", ["source", "frame", "foreign", "escape", "duplicate", "confidence"])
def test_gate_rejects_tampering_before_export(tmp_path, attack):
    from scripts.gate_watch_instruction import evaluate
    from watch.inspection_runtime import digest
    (tmp_path / "media").mkdir()
    (tmp_path / "media/source.mp4").write_bytes(b"synthetic source custody fixture")
    (tmp_path / "frame.jpg").write_bytes(b"synthetic frame custody fixture")
    sha = digest(tmp_path / "frame.jpg")
    data = {"source_sha256": digest(tmp_path / "media/source.mp4"), "end_ms": 2000,
        "frames": [{"clip_ms": 1000, "sha256": sha, "image": "frame.jpg"}]}
    row = unit(frame_refs=[{"clip_ms": 1000, "sha256": sha}]).model_dump(mode="json")
    payload = {"source_sha256": data["source_sha256"], "units": [row]}
    if attack == "foreign": row["frame_refs"][0]["sha256"] = "0"*64
    if attack == "duplicate": payload["units"].append(row)
    if attack == "confidence": row["procedure_confidence"] = 1.1
    if attack == "escape": data["frames"][0]["image"] = "../outside.jpg"
    (tmp_path / "review-data.json").write_text(json.dumps(data))
    (tmp_path / "report.json").write_text(json.dumps({"review_data_sha256": digest(tmp_path / "review-data.json")}))
    (tmp_path / "units.json").write_text(json.dumps(payload))
    if attack == "source": (tmp_path / "media/source.mp4").write_bytes(b"altered")
    if attack == "frame": (tmp_path / "frame.jpg").write_bytes(b"altered")
    with pytest.raises(ValueError): evaluate(tmp_path, tmp_path / "units.json", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_auto_queues_review_without_render_or_speech(tmp_path, monkeypatch):
    import sys
    from scripts import watch_training, draft_watch_explanations, gate_watch_instruction
    from scripts import narrate_watch_training
    calls = []
    monkeypatch.setattr(draft_watch_explanations, "draft", lambda *a: calls.append("draft"))
    monkeypatch.setattr(gate_watch_instruction, "evaluate", lambda *a, **kw: calls.append("gate"))
    def forbidden(*args, **kwargs):
        pytest.fail("unreviewed auto proposals must not render or narrate")
    monkeypatch.setattr(watch_training.render_watch_training, "render", forbidden)
    monkeypatch.setattr(narrate_watch_training, "narrate", forbidden)
    monkeypatch.setattr(sys, "argv", ["watch-training", "auto", "--review", str(tmp_path), "--output", str(tmp_path / "auto")])
    assert watch_training.main() == 0
    assert calls == ["draft", "gate"]
    assert json.loads((tmp_path / "auto/report.json").read_bytes())["status"] == "review_required_before_narration"
