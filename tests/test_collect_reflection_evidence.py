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


def write_scoped_session(path, now, session_id, cwd, message, workspace_roots=None):
    with path.open("w", encoding="utf-8") as handle:
        write_event(handle, now, "session_meta", {"id": session_id, "cwd": str(cwd)})
        if workspace_roots is not None:
            write_event(
                handle,
                now,
                "turn_context",
                {"cwd": str(cwd), "workspace_roots": [str(root) for root in workspace_roots]},
            )
        write_event(handle, now, "event_msg", {"type": "user_message", "message": message})


def test_repo_scope_excludes_unrelated_sessions_and_accepts_worktrees(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    repo = tmp_path / "repo"
    worktree = tmp_path / "repo-worktree"
    unrelated = tmp_path / "unrelated"
    for path in (repo, worktree, unrelated):
        path.mkdir()
    now = datetime.now(timezone.utc)
    write_scoped_session(sessions_root / "repo.jsonl", now, "repo", repo, "repo message")
    write_scoped_session(
        sessions_root / "worktree.jsonl", now, "worktree", worktree / "subdir", "worktree message"
    )
    write_scoped_session(
        sessions_root / "other.jsonl", now, "other", unrelated, "unrelated private message"
    )

    scope = MODULE.SessionScope("repo", [repo, worktree])
    sessions, events, stats = MODULE.collect_sessions(
        sessions_root, now - timedelta(minutes=1), 1_000, 100, scope
    )

    assert [event["text"] for event in events] == ["repo message", "worktree message"]
    assert len(sessions) == 2
    assert stats["sessions_in_scope"] == 2
    assert stats["sessions_out_of_scope"] == 1
    assert stats["messages_out_of_scope"] == 1
    assert "unrelated private message" not in json.dumps(events)


def test_parent_cwd_requires_an_in_scope_workspace_root(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    repo = tmp_path / "parent" / "repo"
    repo.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    write_scoped_session(
        sessions_root / "explicit.jsonl",
        now,
        "explicit",
        repo.parent,
        "explicit workspace",
        workspace_roots=[repo],
    )
    write_scoped_session(
        sessions_root / "broad.jsonl",
        now,
        "broad",
        repo.parent,
        "broad parent only",
        workspace_roots=[repo.parent],
    )

    scope = MODULE.SessionScope("repo", [repo])
    _, events, stats = MODULE.collect_sessions(
        sessions_root, now - timedelta(minutes=1), 1_000, 100, scope
    )

    assert [event["text"] for event in events] == ["explicit workspace"]
    assert stats["messages_out_of_scope"] == 1


def test_global_scope_is_explicit_and_includes_all_sessions(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    now = datetime.now(timezone.utc)
    write_scoped_session(sessions_root / "one.jsonl", now, "one", tmp_path / "one", "one")
    write_scoped_session(sessions_root / "two.jsonl", now, "two", tmp_path / "two", "two")

    _, events, stats = MODULE.collect_sessions(
        sessions_root,
        now - timedelta(minutes=1),
        1_000,
        100,
        MODULE.SessionScope("global"),
    )

    assert [event["text"] for event in events] == ["one", "two"]
    assert stats["messages_out_of_scope"] == 0


def test_explicit_session_override_is_auditable_and_narrow(tmp_path):
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    repo = tmp_path / "parent" / "repo"
    repo.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    write_scoped_session(
        sessions_root / "wanted.jsonl", now, "wanted-id", repo.parent, "wanted parent thread"
    )
    write_scoped_session(
        sessions_root / "other.jsonl", now, "other-id", repo.parent, "other parent thread"
    )

    scope = MODULE.SessionScope("repo", [repo], included_session_ids=["wanted-id"])
    _, events, stats = MODULE.collect_sessions(
        sessions_root, now - timedelta(minutes=1), 1_000, 100, scope
    )

    assert [event["text"] for event in events] == ["wanted parent thread"]
    assert scope.manifest()["included_session_ids"] == ["wanted-id"]
    assert stats["messages_out_of_scope"] == 1


def test_cli_emits_freshness_receipt_and_fingerprint(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sessions_root = tmp_path / "sessions"
    sessions_root.mkdir()
    now = datetime.now(timezone.utc)
    write_scoped_session(sessions_root / "repo.jsonl", now, "repo", repo, "fresh work")
    output = tmp_path / "evidence.json"

    result = MODULE.main(
        [
            "--repo",
            str(repo),
            "--sessions-root",
            str(sessions_root),
            "--output",
            str(output),
        ]
    )
    bundle = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert bundle["run_receipt"]["status"] == "completed"
    assert bundle["run_receipt"]["scope"]["mode"] == "repo"
    assert bundle["run_receipt"]["scope"]["included_session_ids"] == []
    assert bundle["run_receipt"]["source_activity"] == "recent"
    assert bundle["run_receipt"]["newest_retained_event_at"] is not None
    assert len(bundle["run_receipt"]["receipt_id"]) == 20
    assert len(bundle["bundle_fingerprint_sha256"]) == 64
