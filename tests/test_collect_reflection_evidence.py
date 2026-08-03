import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[1]
    / "skills"
    / "beast-reflection"
    / "scripts"
    / "collect_reflection_evidence.py"
)
SPEC = importlib.util.spec_from_file_location("collect_reflection_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_event(handle, timestamp, item_type, payload):
    handle.write(
        json.dumps({"timestamp": timestamp.isoformat(), "type": item_type, "payload": payload})
        + "\n"
    )


def test_collects_only_recent_conversation_and_redacts(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    session_file = sessions_root / "rollout.jsonl"
    now = datetime.now(timezone.utc)

    with session_file.open("w", encoding="utf-8") as handle:
        write_event(
            handle,
            now,
            "session_meta",
            {"id": "session-1", "cwd": str(tmp_path)},
        )
        write_event(
            handle,
            now - timedelta(hours=30),
            "event_msg",
            {"type": "user_message", "message": "old message"},
        )
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "user_message", "message": "Use api_key=supersecretvalue for this"},
        )
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "agent_message", "message": "Verified recovery path"},
        )
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "agent_message", "message": "Verified recovery path"},
        )
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "mcp_tool_call_end", "result": "password=do-not-include"},
        )
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "user_message", "message": "<environment_context>generated</environment_context>"},
        )

    sessions, events, stats = MODULE.collect_sessions(
        sessions_root, now - timedelta(hours=24), max_chars=1_000, max_events=100
    )

    assert len(sessions) == 1
    assert [event["role"] for event in events] == ["user", "assistant"]
    assert events[0]["text"] == "Use api_key=[REDACTED] for this"
    assert events[0]["source"] == "rollout.jsonl"
    assert events[0]["line"] == 3
    assert stats["redactions"] == 1
    assert stats["duplicates_removed"] == 1
    assert "do-not-include" not in json.dumps(events)


def test_truncates_and_hashes_sanitized_text(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    session_file = sessions_root / "rollout.jsonl"
    now = datetime.now(timezone.utc)
    with session_file.open("w", encoding="utf-8") as handle:
        write_event(
            handle,
            now,
            "event_msg",
            {"type": "user_message", "message": "abcdefghij"},
        )

    _, events, stats = MODULE.collect_sessions(
        sessions_root, now - timedelta(minutes=1), max_chars=5, max_events=100
    )

    assert events[0]["text"] == "abcde\n[TRUNCATED]"
    assert events[0]["truncated"] is True
    assert events[0]["original_chars"] == 10
    assert events[0]["sha256"] == MODULE.sha256_text(events[0]["text"])
    assert stats["messages_truncated"] == 1
