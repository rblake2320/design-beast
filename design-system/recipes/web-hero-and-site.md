# Recipe — Real websites (heroes, illustration slots, full pages)

**Use for:** landing pages, dashboards, product sites — actual shippable web.
**Tools:** `frontend-design` + `impeccable` skills build the page. `theme-factory` sets
palette/type. `dataviz` for any chart. magic MCP (21st.dev) for component inspiration.
Higgsfield fills IMAGE SLOTS only.

## The iron rule
Generated images are ingredients, never the layout. The page is real HTML/CSS with a
real type scale and spacing system; AI art goes into defined slots (hero, illustration,
avatar, texture) — cropped and graded to the site palette.

## Order of operations
1. `theme-factory` → lock palette + type scale FIRST
2. `frontend-design` → build the page structure (it avoids generic-AI aesthetics by design)
3. Generate slot art with the palette IN the prompt:
   "…dominant colors #0E1A2B and #F4B860, flat vector illustration, generous negative space"
4. Grade every image to the palette (ImageMagick) so slots feel native
5. `impeccable` pass → hierarchy, spacing, states, a11y, motion

## Hero image prompt skeleton
```
[SUBJECT matching the value prop], [STYLE: flat vector | 3D clay render | editorial photo],
composition weighted to the [left|right] with clean negative space for headline,
palette: [your 2-3 hex codes], soft even lighting, no text, no UI chrome
```

## Quality gates
- [ ] Headline text is HTML, never baked into the image
- [ ] Image palette sits inside the site palette (no rainbow heroes)
- [ ] Page passes impeccable review (hierarchy, contrast, responsive)
- [ ] Looks intentional at 375px and 1440px
