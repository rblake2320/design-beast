import subprocess

import pytest

from scripts.verify_watch_receipt_representations import GitSnapshot, representation, sha


def test_identity_allows_binary_without_conversion():
    value = b"\xff\x00\r\n"
    assert representation(value, sha(value), "frame.jpg") == "identity"


def test_strict_lf_to_crlf_recovers_only_exact_recorded_bytes():
    value = b'{"x": 1}\n'
    assert representation(value, sha(b'{"x": 1}\r\n'), "receipt.json") == "strict_lf_to_crlf"


@pytest.mark.parametrize("value", [b"a\rb\n", b"a\r\nb\n", b"\xff\n", b"a\x00\n"])
def test_bare_cr_mixed_newlines_invalid_utf8_and_nul_refused(value):
    with pytest.raises((ValueError, UnicodeError)):
        representation(value, sha(value.replace(b"\n", b"\r\n")), "receipt.json")


def test_binary_newline_reconstruction_refused():
    with pytest.raises(ValueError):
        representation(b"a\n", sha(b"a\r\n"), "frame.jpg")


@pytest.mark.parametrize("expected", ["0" * 64, "unknown", "A" * 64])
def test_tamper_and_unknown_hash_refused(expected):
    with pytest.raises(ValueError):
        representation(b'{"changed":true}\n', expected, "receipt.json")


def test_semantically_equal_json_is_not_byte_equivalent():
    with pytest.raises(ValueError):
        representation(b'{"x":1}\n', sha(b'{"x": 1}\n'), "receipt.json")


@pytest.fixture
def snapshot(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "receipt.json").write_bytes(b'{"x": 1}\n')
    subprocess.run(["git", "-C", str(tmp_path), "add", "receipt.json"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "-m", "fixture"], check=True, capture_output=True)
    commit = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    return GitSnapshot(tmp_path, commit)


def test_git_snapshot_ignores_dirty_checkout(snapshot):
    original = snapshot.read("receipt.json")
    (snapshot.repo / "receipt.json").write_bytes(b"tampered")
    assert GitSnapshot(snapshot.repo, snapshot.commit).read("receipt.json") == original


def test_missing_blob_refused(snapshot):
    with pytest.raises(ValueError, match="missing blob"):
        snapshot.read("missing.json")


@pytest.mark.parametrize("path", ["../receipt.json", "/receipt.json", "a\\receipt.json", "a:receipt.json", "a//b", "./receipt.json"])
def test_unsafe_paths_refused(snapshot, path):
    with pytest.raises(ValueError, match="unsafe"):
        snapshot.read(path)


def test_mutable_revision_refused(tmp_path):
    with pytest.raises(ValueError, match="immutable"):
        GitSnapshot(tmp_path, "HEAD")
