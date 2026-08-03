# Typed visual evidence

Beast Watch compiles visual state through an explicit target contract before a
procedure may execute it. A model may propose observations, but the deterministic
compiler owns normalization and refuses unresolved state.

## Contract

1. Declare the application and exact version.
2. Declare every executable field's type. Do not infer type from its contents.
3. Declare canonical enum values and give every UI-label alias a basis and an
   evidence reference. Aliases are application/version-specific.
4. Bind observations to both the target fingerprint and timeline fingerprint.
5. Cite an exact frame and pixel region. New v3 timelines retain the frame's
   ingestion-time SHA-256; compilation verifies it has not changed.
6. Preserve transient observations. A final value must occur after transient
   values and meet its declared confidence, confirmation-count, and time-span
   requirements.
7. OCR observations retain text, region, and OCR confidence. Model confidence
   cannot exceed OCR confidence, and normalized OCR text must equal the proposed
   value.
8. Unknown enums, missing units, malformed colors, conflicting final values,
   changed pixels, or inadequate evidence produce `insufficient_evidence`.

Run:

```powershell
python scripts/compile_visual_evidence.py `
  BUNDLE/typed-target.json BUNDLE/typed-observations.json `
  BUNDLE/timeline.json BUNDLE/typed-state.json
```

The command's zero exit code means only that all required typed fields compiled.
It does not mean the resulting procedure executed correctly; structural,
behavioral, and visual validation remain separate gates.

## Research basis

- JSON Schema 2020-12 constrains canonical values with `enum` and alternatives
  with applicators such as `oneOf`.
- The W3C Design Tokens Format Module requires explicit types and says tools must
  not infer a missing type from value contents.
- Tesseract exposes word confidence and bounding boxes; Beast retains equivalent
  confidence and region evidence rather than treating OCR text as ground truth.
- SVG 2 defines only `pad`, `reflect`, and `repeat` for `spreadMethod`; an editor's
  different UI label therefore needs an evidenced target-specific mapping.

Sources were verified 2026-08-03:

- https://json-schema.org/draft/2020-12/draft-bhutton-json-schema-00
- https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/
- https://tesseract-ocr.github.io/tessdoc/APIExample.html
- https://www.w3.org/TR/SVG2/pservers.html
