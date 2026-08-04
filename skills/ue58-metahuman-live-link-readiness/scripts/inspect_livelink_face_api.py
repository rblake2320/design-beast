"""Print the generated UE Python signatures for the Live Link Face API."""

from __future__ import annotations

import json
import unreal


def main() -> dict:
    api = unreal.LiveLinkFaceSourceBlueprint
    library = unreal.LiveLinkBlueprintLibrary
    result = {
        "create_doc": str(api.create_live_link_face_source.__doc__),
        "connect_doc": str(api.connect.__doc__),
        "source_methods": sorted(name for name in dir(library) if "source" in name.lower()),
        "get_sources_doc": str(getattr(library, "get_live_link_sources", None).__doc__),
        "handle_doc": str(unreal.LiveLinkSourceHandle.__doc__),
        "native_connect_doc": str(
            unreal.BeastEvidenceCollectorLibrary.connect_live_link_face_source.__doc__
        ),
    }
    unreal.log("BEAST_LIVELINK_FACE_API=" + json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
