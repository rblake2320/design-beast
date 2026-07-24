# Recipe — Consistent character / face across many images

**Use for:** avatars, mascots, brand characters, presenter videos, game characters.
**Tools:** `higgsfield-soul-id` (real person) · Nano Banana 2/Pro ref edits (any character)
· proven end-to-end on Mood Buddy (same face, many expressions).

## Two paths

**Real person / your face:** train Soul once (`higgsfield-soul-id` → reference_id), then
every generation uses `--soul-id <id>` with `text2image_soul_v2` / `soul_cinema_studio`.

**Invented character:** generate ONE canonical sheet you love (front, 3/4, profile — GPT
Image 2). That sheet is now law. Every subsequent image = Nano Banana reference edit FROM
the sheet, changing only pose/expression/outfit. Never re-describe the character in text
— text re-description is why characters drift.

## Quality gates
- [ ] Same face geometry across the set (eyes/nose/jaw — flip through quickly, drift jumps out)
- [ ] Same rendering style (don't mix photo + illustration passes)
- [ ] Expression changes read in the eyes and brows, not just the mouth

## To video / 3D
- Video: winner still → Seedance image-to-video (motion prompt only, identity stays in the image)
- 3D: canonical front+profile → image-to-3D (Tripo/Hunyuan3D) → Blender cleanup →
  `skills/game-content-pipeline` takes it from there (rig, UE import)
