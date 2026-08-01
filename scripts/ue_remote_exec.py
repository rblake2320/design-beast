"""Execute a Python file in a running Unreal Editor through Epic's remote channel."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--discover-seconds", type=float, default=3.0)
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Set a validated BEAST_* run-control value in the remote Unreal Python process",
    )
    args = parser.parse_args()

    remote_env: dict[str, str] = {}
    for item in args.env:
        name, separator, value = item.partition("=")
        if not separator or not re.fullmatch(r"BEAST_[A-Z0-9_]+", name):
            parser.error(f"invalid --env value: {item!r}")
        remote_env[name] = value

    remote_python = (
        args.engine_root
        / "Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"
    )
    sys.path.insert(0, str(remote_python))
    import remote_execution  # type: ignore[import-not-found]

    script_path = args.script.resolve()
    file_source = script_path.read_text(encoding="utf-8")
    source = (
        "import os as _beast_os; _beast_os.environ.update("
        + repr(remote_env)
        + "); exec(compile("
        + repr(file_source)
        + ", "
        + repr(str(script_path))
        + ", 'exec'), {'__file__': "
        + repr(str(script_path))
        + ", '__name__': '__main__'})"
    )
    session = remote_execution.RemoteExecution()
    session.start()
    try:
        deadline = time.monotonic() + args.discover_seconds
        nodes = []
        while time.monotonic() < deadline:
            nodes = session.remote_nodes
            if nodes:
                break
            time.sleep(0.1)
        if len(nodes) != 1:
            print(json.dumps({"ok": False, "nodes": nodes}, default=str))
            return 2
        session.open_command_connection(nodes[0]["node_id"])
        result = session.run_command(
            source,
            unattended=True,
            exec_mode=remote_execution.MODE_EXEC_FILE,
            raise_on_failure=False,
        )
        public_result = dict(result)
        public_result["command"] = str(script_path)
        print(json.dumps(public_result, default=str))
        return 0 if result.get("success") else 1
    finally:
        session.stop()


if __name__ == "__main__":
    raise SystemExit(main())
