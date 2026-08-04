# Media Provenance

**Purpose:** Chain-of-custody layer required BEFORE any extraction runs.
Produces the `source_manifest` every other skill depends on
(watch/evidence/schema/source_manifest.schema.json).

## Pipeline
```
input file
  → sha256 hash
  → ExifTool metadata extraction
  → C2PA manifest check (if present)
  → authorization_status assignment (human-set, not inferred)
  → source_manifest.json written
  → provenance_gate.py unlocks extraction
```

## Why this exists
Every extractor, enhancer, and OSINT clue module in this package requires
an authorized source_manifest to run. This was previously implicit;
council review flagged it as a missing first-class requirement.

## Tools wrapped
- ExifTool — metadata extraction across image/video/document formats
- C2PA viewer/manifest check — origin and edit-history verification where
  present (not all sources will have C2PA credentials — absence is not
  proof of tampering, just noted in the manifest)
