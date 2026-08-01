# Recovery playbook

## Expired authorization code

This failure was observed on 2026-08-01: Epic displayed “the code you are using is invalid or expired.” A fresh autorig request generated a new authorization flow; the user completed it, Unreal logged `EOS_Success`, and autorig completed.

Recovery:

1. Discard the expired page/code.
2. Trigger one fresh request; do not loop requests.
3. Pause for the user to authenticate and accept or decline consent.
4. Resume only after Unreal logs authentication success.
5. Preserve the expired event and new success timestamps in the receipt.

This does not authorize an agent to enter codes or accept consent.

## Optional content missing

If Unreal reports limited MetaHuman features or a missing optional-content folder, stop. Repair the UE 5.8 installation through Epic Games Launcher and add MetaHuman Creator Core Data. Verify the optional content exists after installation and restart the editor before retrying.

## Rigged but cannot build

Check `has_high_resolution_textures`. In the reproduced run, Full Rig succeeded before texture sources existed, so `can_build_meta_human` correctly remained false until all eight 2K texture sources downloaded.

## Generated path differs

Snapshot the run-scoped asset root before and after assembly. Select the unique new Blueprint associated with the character name. Never repair this by hardcoding a path copied from another run.

## Python property spelling fails

Inspect the generated actor and components. In UE 5.8 the successful reflected actor fields were `LiveLinkSubject` (`LiveLinkSubjectName`) and `UseLiveLink` (`bool`), even though guessed snake_case access failed.

## Missing convenience method

UE 5.8's Python Actor wrapper did not expose `rerun_construction_scripts`, and the attempted viewport-focus helper was absent. Treat convenience-method absence as a narrow tooling gap. Validate binding through direct readback instead of declaring the underlying operation failed.

## Nanite/SM6 restart pending

Do not use a level screenshot as deformation evidence while Shader Model 6 is disabled or a settings restart is pending. Save assets, restart into a clean SM6 session, reconnect the phone, and then run the two-pose gate.
