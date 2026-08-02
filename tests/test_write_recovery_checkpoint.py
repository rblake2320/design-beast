from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_checkpoint_is_atomic_and_hashes_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    tracked = repo / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    evidence = repo / "evidence.bin"
    evidence.write_bytes(b"proof")
    session = repo / "session" / "test"
    script = Path(__file__).resolve().parents[1] / "scripts" / "write_recovery_checkpoint.py"

    subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--session-dir",
            str(session),
            "--goal",
            "recover",
            "--current",
            "testing",
            "--next-action",
            "verify",
            "--evidence",
            str(evidence),
        ],
        check=True,
    )

    payload = json.loads((session / "latest.json").read_text(encoding="utf-8"))
    assert payload["goal"] == "recover"
    assert payload["evidence"][0]["sha256"] == "c1cda26362828b69266512052b97cb3729e3b052e4ade47c0a1e3383defe73c7"
    assert payload["secrets_stored"] is False
    assert not (session / "latest.json.tmp").exists()
    assert (session / "RECOVER.md").is_file()
