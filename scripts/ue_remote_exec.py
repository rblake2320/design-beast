"""Execute a Python file in a running Unreal Editor through Epic's remote channel."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--discover-seconds", type=float, default=3.0)
    args = parser.parse_args()

    remote_python = (
        args.engine_root
        / "Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"
    )
    sys.path.insert(0, str(remote_python))
    import remote_execution  # type: ignore[import-not-found]

    source = args.script.read_text(encoding="utf-8")
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
        print(json.dumps(result, default=str))
        return 0 if result.get("success") else 1
    finally:
        session.stop()


if __name__ == "__main__":
    raise SystemExit(main())
