"""Serialize-then-replace writer shared by exporters: a failed export never leaves partial or replaced output."""
import os
import tempfile


def write_text_atomic(output_path: str, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(output_path))
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=".export-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output_path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
