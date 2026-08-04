---
name: media-evidence-intake
description: Admit local image/video evidence into Design Beast with exact hashes, explicit usage authorization, Watch v3 frame/transcript conversion, execution-linked procedure claims, dataset-training rights gates, and optional SafeSearch-first Google Cloud Vision Web Detection. Use when learning from media, compiling tutorial procedures, preparing training records, enhancing evidence, checking reverse-image references, or deciding whether media-derived claims can be promoted.
---

# Media Evidence Intake

Use the repository CLI. Do not hand-author proof booleans or copy the supplied
prototype package into Beast.

## Workflow

1. Run `python scripts/doctor.py`.
2. Admit the exact local bytes:

   ```powershell
   python scripts/evidence_intake.py admit <source> <manifest.json> `
     --status <owned|licensed|public_domain|fair_use_research|unverified> `
     --approved-by <principal> --basis <evidence> `
     --allow-use evidence_analysis --allow-use procedure_learning
   ```

   Never infer authorization. `unverified` accepts no uses. Fair-use research
   cannot authorize dataset training or redistribution.

3. For Watch material, require `beast.watch.timeline/v3`, then run:

   ```powershell
   python scripts/evidence_intake.py timeline-events manifest.json timeline.json events.json
   ```

   Stop on missing frames, changed hashes, escaped paths, or a mismatched source.

4. Create claims and execution receipts with the CLI. A claim is
   `verified_by_execution` only when its referenced receipt succeeded, every
   check passed, and retained artifacts still match their hashes. Compile with
   `evidence_intake.py compile`; treat its derived `promotion_allowed` value as
   authoritative.

5. Before training export, run `dataset-check`. Require explicit
   `dataset_training` authorization plus a reviewer, license, rights basis,
   label schema, and split. A procedure-learning authorization is not training
   permission.

## Cloud Vision

Use Google Cloud Vision only when the manifest permits `cloud_analysis`, the
user authorizes the cloud call, and `GOOGLE_CLOUD_VISION_API_KEY` is available.
SafeSearch runs first. Adult, violent, or racy results at the configured
threshold stop Web Detection unless sensitive review is separately authorized.

```powershell
python scripts/evidence_intake.py google-vision manifest.json parent-event.json image.png result.json --authorize-cloud-call
```

Do not fetch returned URLs automatically. Web entities, matching pages/images,
and visually similar images are hypothesis-only evidence; they cannot alone
verify identity, location, ownership, or wrongdoing.

## Derivatives and reporting

- Preserve original and derivative hashes plus the transformation.
- Treat deterministic crops/upscales as derivatives, not originals.
- Restrict generative enhancement to inferred/uncertain/rejected evidence; never
  present generated detail as recovered fact.
- Report separately: source admitted, evidence linked, execution verified,
  dataset export ready, and cloud extraction actually run.

Read [references/contracts.md](references/contracts.md) when authoring receipt
specs, dataset-rights files, or new extractor adapters.
