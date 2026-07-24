# The Quality Loop — why your output doesn't look like the posted stuff (and the fix)

The images people post from Higgsfield/Midjourney/etc. are not first attempts. They are
survivors of a pipeline. When AI "uses your tools" and produces mid results, it is
skipping steps 2–6 below. Every agent working in this repo runs the full loop.

## The loop

```
BRIEF → RECIPE → GENERATE ×N → JUDGE → REFINE → UPSCALE/GRADE → SHIP
              └──────────── iterate until judge passes ───────────┘
```

### 1. Brief (30 seconds, mandatory)
One sentence each: subject · purpose (where will this live?) · mood · hard constraints
(aspect ratio, brand colors, text that must render). No brief → garbage in.

### 2. Recipe, not freehand
Pick the closest card in `recipes/`. Cards encode prompt anatomy that flat prompts miss:

```
[SUBJECT with 2-3 specific details] · [COMPOSITION: framing, angle, rule]
[LIGHTING: source, direction, quality] · [LENS: focal length, aperture, DoF]
[MOOD/GRADE: palette, era, film stock] · [STYLE ANCHORS: 1-2 references]
[NEGATIVE: what to exclude]
```

"A cool cyberpunk city" loses to "rain-slicked neon alley in Kowloon, low-angle 24mm,
single sodium-vapor key light camera-left, teal-orange grade, Blade Runner 2049 palette,
shallow puddle reflections, no people, no text" **every time**.

For product/brand/marketplace work do NOT freehand at all — route to the purpose-built
skills (`higgsfield-product-photoshoot`, `higgsfield-marketplace-cards`): their backends
assemble prompts from compliance-tested templates.

### 3. Generate ×N (minimum 4)
One generation is a lottery ticket. Vary ONE axis across candidates (angle, lighting, or
seed) — not everything, or you learn nothing from the comparison.

### 4. Judge — with eyes, not vibes
Score each candidate against the recipe's quality gates. Two ways:
- `python scripts/judge_image.py <img> --brief "..."` — local llava vision model scores
  composition/lighting/artifacts, free, no cloud.
- Claude reads the image directly (Read tool takes PNGs) and scores against the gates.

Kill anything with: melted hands/text, physics-impossible lighting, mushy focal point,
"AI sheen" (over-smooth plastic skin, hyper-saturated everything).

### 5. Refine the winner
The winner is a draft. Nano Banana 2/Pro reference-edit pass for: fixing the weak region,
locking character/product identity across shots, changing expression/angle while keeping
the face (this is the Mood Buddy trick — proven on this machine).

### 6. Upscale + grade
Native gen resolution is not ship resolution. Upscale, then grade — ImageMagick for
stills (`magick input.png -modulate 100,108 -level 2%,98% out.png` as a starting point),
ffmpeg LUTs for video. The grade is 30% of "looks professional."

## Consistency across a set (the other tell)

Posted portfolios look coherent; naive AI output looks like 10 different artists.
- Same character/face → Soul ID (train once, `--soul-id` everywhere) or Nano Banana ref edits
- Same product → product-photoshoot restyle mode from ONE hero shot
- Same style across a site → extract a palette + type scale FIRST (theme-factory skill),
  then constrain every generation to it

## Web/UI images specifically

If the deliverable is a **site**, generated images are ingredients, never the design.
Layout, type, spacing come from `frontend-design` + `impeccable` skills; generated art
fills hero/illustration slots, cropped and graded to the site's palette. A screenshot of
a generated "landing page image" is how you get uncanny sites.
