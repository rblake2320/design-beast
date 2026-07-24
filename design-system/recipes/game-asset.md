# Recipe — Game assets (sprites, 3D props, levels)

**Use for:** anything ending up inside an engine.
**Tool:** `skills/game-content-pipeline/SKILL.md` is the authority — run its doctor first.

## Routing (short version)
| Asset | Path |
|---|---|
| Sprite / flipbook | Higgsfield → rembg → `sprite_slice.py` → Paper2D → PaperZD |
| 3D prop from an image | image-to-3D (Tripo API / Hunyuan3D local) → Blender cleanup → FBX/GLB → UE |
| Hard-surface / precise 3D | Blender MCP directly (geo nodes, modifiers) — skip image-to-3D |
| Character + rig | Blender Rigify → FBX → UE IK Retargeter |
| Level / world | UE MCP (:8000/mcp) + VibeUE toolsets, splines + PCG |

## Quality gates for AI-generated game art
- [ ] Sprite sheets: consistent pivot + silhouette reads at gameplay zoom
- [ ] 3D from image: quad-dominant after cleanup, sane scale (UE Unit Scale 0.01 from Blender)
- [ ] Textures: tileable where needed, consistent texel density
- [ ] Style bible: pick 3 anchor images before generating ANY asset; judge every asset
      against them (this is what keeps a game from looking like an asset-flip)
