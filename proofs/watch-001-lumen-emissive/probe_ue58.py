"""Record the real UE 5.8 reflection surface needed by proof 001."""
import json
from pathlib import Path

import unreal

OUT = Path(__file__).resolve().parent / "reflection-probe.json"


def probe(obj, names):
    result = {}
    for name in names:
        try:
            value = obj.get_editor_property(name)
            result[name] = {"available": True, "value": str(value),
                            "type": type(value).__name__}
        except Exception as exc:
            result[name] = {"available": False, "error": str(exc)}
    return result


settings = unreal.PostProcessSettings()
material = unreal.Material()
result = {
    "engine_version": unreal.SystemLibrary.get_engine_version(),
    "post_process": probe(settings, [
        "override_auto_exposure_method", "auto_exposure_method",
        "override_auto_exposure_bias", "auto_exposure_bias",
        "override_lumen_scene_detail", "lumen_scene_detail",
        "override_dynamic_global_illumination_method",
        "dynamic_global_illumination_method",
    ]),
    "material": probe(material, ["shading_model", "blend_mode", "material_domain"]),
}
OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
unreal.log(f"BEAST_PROOF reflection probe written: {OUT}")
