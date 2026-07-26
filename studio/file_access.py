"""Constrained resolution for user-supplied Beast Studio file references."""
from pathlib import Path


def resolve_media(reference: str, uploads: Path, runs: Path) -> Path | None:
    """Resolve only files below uploads/ or runs/.

    Bare names mean uploads. Run artifacts must use ``runs/<id>/<file>``.
    Absolute paths, traversal, alternate roots, and directories are rejected.
    """
    if not reference or "\x00" in reference:
        return None
    normalized = reference.replace("\\", "/")
    candidate_ref = Path(normalized)
    if candidate_ref.is_absolute():
        return None
    if normalized.startswith("runs/"):
        relative = Path(normalized.removeprefix("runs/"))
        root = runs.resolve()
    elif "/" not in normalized:
        relative = Path(normalized)
        root = uploads.resolve()
    else:
        return None
    candidate = (root / relative).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        return None
    return candidate
