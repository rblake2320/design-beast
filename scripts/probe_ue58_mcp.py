"""Read-only proof probe for Unreal Engine 5.8's official MCP server.

The probe talks only to a loopback endpoint, performs the MCP handshake, and
exercises discovery plus read-only Unreal tools.  ``--capture`` additionally
captures the current viewport in memory and reports its hash; it never writes
the image to disk.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from typing import Any
from urllib import request
from urllib.parse import urlparse


PROTOCOL_VERSION = "2025-06-18"


class McpError(RuntimeError):
    """Raised when the UE MCP server returns an invalid or failed response."""


class McpClient:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("UE MCP has no authentication; only loopback URLs are allowed")
        self.url = url
        self.session_id: str | None = None
        self.next_id = 1

    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            if not self.session_id:
                self.session_id = response.headers.get("Mcp-Session-Id")
            body = response.read()
        if not body:
            return None
        decoded = json.loads(body)
        if "error" in decoded:
            raise McpError(json.dumps(decoded["error"], sort_keys=True))
        return decoded

    def initialize(self) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self.next_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "beast-ue58-proof", "version": "1.0"},
                },
            }
        )
        self.next_id += 1
        if response is None or not self.session_id:
            raise McpError("initialize did not return JSON and an MCP session ID")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return response["result"]

    def rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._post(
            {
                "jsonrpc": "2.0",
                "id": self.next_id,
                "method": method,
                "params": params,
            }
        )
        self.next_id += 1
        if response is None:
            raise McpError(f"{method} returned no JSON")
        return response["result"]

    def meta_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.rpc(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        content = result.get("content", [])
        if not content or "text" not in content[0]:
            raise McpError(f"{name} returned no text content")
        text = content[0]["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def call_tool(self, toolset: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        return self.meta_tool(
            "call_tool",
            {
                "toolset_name": toolset,
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )


def run_probe(url: str, capture: bool) -> dict[str, Any]:
    client = McpClient(url)
    initialized = client.initialize()
    listed = client.rpc("tools/list", {})
    toolsets = client.meta_tool("list_toolsets", {})
    current_level = client.call_tool(
        "editor_toolset.toolsets.scene.SceneTools", "get_current_level", {}
    )
    skills = client.call_tool(
        "ToolsetRegistry.AgentSkillToolset", "ListSkills", {}
    )
    dsl_docs = client.call_tool(
        "editor_toolset.toolsets.blueprint.BlueprintTools",
        "get_graph_dsl_docs",
        {},
    )

    if isinstance(toolsets, str):
        # UE's meta-tool returns a readable catalogue rather than JSON. Every
        # registered toolset starts on a top-level "- name: description" line.
        available_toolsets = [
            line[2:].split(":", 1)[0]
            for line in toolsets.splitlines()
            if line.startswith("- ") and ":" in line
        ]
    else:
        available_toolsets = toolsets.get("toolsets", toolsets)
    skill_map = skills.get("returnValue", {})
    dsl_text = dsl_docs.get("returnValue", "")
    result: dict[str, Any] = {
        "schema": 1,
        "endpoint": url,
        "protocol_version": initialized.get("protocolVersion"),
        "server_info": initialized.get("serverInfo"),
        "meta_tools": [tool["name"] for tool in listed.get("tools", [])],
        "toolset_count": len(available_toolsets),
        "current_level": current_level.get("returnValue"),
        "native_skill_count": len(skill_map),
        "native_skill_paths": sorted(skill_map),
        "blueprint_dsl_documented": "GRAMMAR OVERVIEW" in dsl_text,
        "blueprint_dsl_doc_characters": len(dsl_text),
    }

    if capture:
        editor = "EditorToolset.EditorAppToolset"
        camera = client.call_tool(editor, "GetCameraTransform", {})["returnValue"]
        viewport = client.call_tool(
            editor,
            "CaptureViewport",
            {
                # These are described as optional by the plugin, but UE 5.8's
                # dispatcher currently rejects them when omitted.
                "captureTransform": camera,
                "annotations": {
                    "gridSpacing": 0.0,
                    "gridExtent": 1000.0,
                    "gridHeight": 0.0,
                    "maxLabelDistance": 1_000_000_000.0,
                    "classFilter": {"refPath": "/Script/Engine.Actor"},
                    "maxLabels": 20,
                },
                "bShowUI": False,
            },
        )["returnValue"]
        image = base64.b64decode(viewport["image"]["data"], validate=True)
        result["viewport"] = {
            "mime_type": viewport["image"]["mimeType"],
            "bytes": len(image),
            "sha256": hashlib.sha256(image).hexdigest(),
            "png_signature_valid": image.startswith(b"\x89PNG\r\n\x1a\n"),
            "camera_location": viewport["cameraLocation"],
            "camera_rotation": viewport["cameraRotation"],
            "camera_fov": viewport["cameraFOV"],
            "labeled_actor_count": len(viewport.get("labeledActors", [])),
            "labeled_actors": viewport.get("labeledActors", []),
        }

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--capture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_probe(args.url, args.capture), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
