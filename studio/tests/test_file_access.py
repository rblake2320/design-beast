from file_access import resolve_media


def test_bare_upload_and_run_artifact_resolve(tmp_path):
    uploads, runs = tmp_path / "uploads", tmp_path / "runs"
    uploads.mkdir()
    runs.mkdir()
    assert resolve_media("image.png", uploads, runs) == uploads / "image.png"
    assert resolve_media("runs/job-1/final.png", uploads, runs) == runs / "job-1" / "final.png"


def test_traversal_absolute_and_alternate_roots_are_rejected(tmp_path):
    uploads, runs = tmp_path / "uploads", tmp_path / "runs"
    uploads.mkdir()
    runs.mkdir()
    bad = [
        "../server.py",
        r"..\server.py",
        "runs/../../server.py",
        r"runs\..\..\server.py",
        "other/file.png",
        "",
        "\x00.png",
        str((tmp_path / "outside.png").resolve()),
    ]
    assert all(resolve_media(value, uploads, runs) is None for value in bad)


def test_root_directory_itself_is_rejected(tmp_path):
    uploads, runs = tmp_path / "uploads", tmp_path / "runs"
    uploads.mkdir()
    runs.mkdir()
    assert resolve_media("runs/", uploads, runs) is None
