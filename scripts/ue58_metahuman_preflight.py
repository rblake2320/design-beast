"""Safe UE 5.8 MetaHuman/Live Link preflight.

Run inside Unreal Editor's Python environment. This script never requests cloud
autorigging, texture downloads, or assembly. It reports those readiness gates so
an agent can stop before an unsupported or external operation.

Optional environment variables:

- BEAST_MH_PRESET: source MetaHuman preset asset path.
- BEAST_MH_TARGET: project-scoped destination asset path.
- BEAST_LIVE_LINK_CONNECT=1: attempt a Live Link Face connection.
- BEAST_PHONE_HOST: required when connection is enabled.
- BEAST_PHONE_PORT: defaults to 14785.
- BEAST_LIVE_LINK_SUBJECT: defaults to ``me``.
"""

from __future__ import annotations

import json
import os

import unreal


MARKER = "BEAST_METAHUMAN_PREFLIGHT="
DEFAULT_PRESET = "/MetaHumanCharacter/Optional/Presets/Ada"
DEFAULT_TARGET = "/Game/Characters/MetaHumans/AdaProof"


def _engine_version() -> str:
    return str(unreal.SystemLibrary.get_engine_version())


def _require_ue58(version: str) -> None:
    if not version.startswith("5.8"):
        raise RuntimeError(f"UE 5.8 is required; active engine is {version}")


def _ensure_character(preset: str, target: str):
    assets = unreal.EditorAssetLibrary
    preset_exists = bool(assets.does_asset_exist(preset))
    if not preset_exists:
        raise RuntimeError(f"MetaHuman preset is missing: {preset}")

    created = False
    if not assets.does_asset_exist(target):
        created_asset = assets.duplicate_asset(preset, target)
        if created_asset is None:
            raise RuntimeError(f"Failed to duplicate {preset} to {target}")
        created = True

    character = unreal.load_asset(target)
    if character is None:
        raise RuntimeError(f"Failed to load project MetaHuman: {target}")

    class_name = character.get_class().get_name()
    if class_name != "MetaHumanCharacter":
        raise RuntimeError(f"Unexpected target class {class_name}: {target}")

    saved = bool(assets.save_asset(target, only_if_is_dirty=False))
    return character, {
        "preset": preset,
        "preset_exists": preset_exists,
        "target": target,
        "created": created,
        "saved": saved,
        "class": class_name,
    }


def _assembly_readiness(character) -> dict:
    subsystem = unreal.get_editor_subsystem(
        unreal.MetaHumanCharacterEditorSubsystem
    )
    can_build = bool(subsystem.can_build_meta_human(character, log_error=True))
    return {
        "can_build": can_build,
        "high_resolution_textures": bool(character.has_high_resolution_textures),
        "external_work_performed": False,
        "next_gate": None if can_build else "inspect Unreal log; do not auto-rig silently",
    }


def _live_link() -> dict:
    enabled = os.environ.get("BEAST_LIVE_LINK_CONNECT") == "1"
    if not enabled:
        return {"attempted": False}

    host = os.environ.get("BEAST_PHONE_HOST", "").strip()
    if not host:
        raise RuntimeError(
            "BEAST_PHONE_HOST is required when BEAST_LIVE_LINK_CONNECT=1"
        )

    port = int(os.environ.get("BEAST_PHONE_PORT", "14785"))
    subject = os.environ.get("BEAST_LIVE_LINK_SUBJECT", "me")
    handle, created = (
        unreal.LiveLinkFaceSourceBlueprint.create_live_link_face_source()
    )
    connected = unreal.LiveLinkFaceSourceBlueprint.connect(
        handle, subject, host, port
    )
    return {
        "attempted": True,
        "source_created": bool(created),
        "connected": bool(connected),
        "host": host,
        "port": port,
        "subject": subject,
    }


def main() -> dict:
    version = _engine_version()
    _require_ue58(version)
    preset = os.environ.get("BEAST_MH_PRESET", DEFAULT_PRESET)
    target = os.environ.get("BEAST_MH_TARGET", DEFAULT_TARGET)
    character, asset_result = _ensure_character(preset, target)
    result = {
        "schema": 1,
        "engine_version": version,
        "asset": asset_result,
        "assembly": _assembly_readiness(character),
        "live_link": _live_link(),
    }
    unreal.log(MARKER + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
