# beast — Design Beast CLI. Add to PATH or alias:  Set-Alias beast <repo>\bin\beast.ps1
param([Parameter(Position = 0)][string]$Cmd = 'help', [Parameter(ValueFromRemainingArguments)]$Rest)

$Repo = Split-Path $PSScriptRoot -Parent

switch ($Cmd) {
    'doctor'  { python (Join-Path $Repo 'scripts\doctor.py') @Rest }
    'sync'    { & (Join-Path $Repo 'scripts\sync_repos.ps1') @Rest }
    'judge'   { python (Join-Path $Repo 'scripts\judge_image.py') @Rest }
    'replay'  { python (Join-Path $Repo 'scripts\replay_diff.py') @Rest }
    'ledger'  { python (Join-Path $Repo 'scripts\ledger_verify.py') @Rest }
    'validate' { python (Join-Path $Repo 'scripts\beast_core.py') validate @Rest }
    'status' { python (Join-Path $Repo 'scripts\beast_core.py') status @Rest }
    'resource-check' { python (Join-Path $Repo 'scripts\beast_core.py') resource-check @Rest }
    'checkpoint' { python (Join-Path $Repo 'scripts\write_recovery_checkpoint.py') @Rest }
    'recover' { python (Join-Path $Repo 'scripts\verify_recovery_checkpoint.py') @Rest }
    'watch-validate' { python (Join-Path $Repo 'scripts\validate_watch_procedure.py') @Rest }
    'watch'   { python (Join-Path $Repo 'scripts\watch_video.py') @Rest }
    'watch-index' { python (Join-Path $Repo 'scripts\watch_index.py') @Rest }
    'watch-seek' { python (Join-Path $Repo 'scripts\watch_seek.py') @Rest }
    'watch-perceive' { python (Join-Path $Repo 'scripts\watch_perception.py') @Rest }
    'watch-training' { python (Join-Path $Repo 'scripts\watch_training.py') @Rest; exit $LASTEXITCODE }
    'watch-narrate' { python (Join-Path $Repo 'scripts\narrate_watch_training.py') @Rest; exit $LASTEXITCODE }
    'watch-instruction-gate' { python (Join-Path $Repo 'scripts\gate_watch_instruction.py') @Rest; exit $LASTEXITCODE }
    'watch-rewind-eval' { python (Join-Path $Repo 'scripts\evaluate_watch_rewind.py') @Rest; exit $LASTEXITCODE }
    'watch-ui-regions' { python (Join-Path $Repo 'scripts\watch_ui_regions.py') @Rest }
    'watch-fuse' { python (Join-Path $Repo 'scripts\fuse_watch_state.py') @Rest }
    'watch-temporal' {
        $EncoderPython = Join-Path $Repo '.venv-watch-temporal\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $EncoderPython)) {
            throw 'Temporal environment missing; follow docs/WATCH-PIXEL-STATE.md setup.'
        }
        & $EncoderPython (Join-Path $Repo 'scripts\watch_temporal_encoder.py') @Rest
    }
    'recipes' {
        Get-ChildItem (Join-Path $Repo 'design-system\recipes') -Filter *.md | ForEach-Object {
            $head = (Get-Content $_.FullName -TotalCount 3) -join ' '
            "{0,-28} {1}" -f $_.BaseName, ($head -replace '#\s*Recipe\s*—\s*', '')
        }
    }
    default {
        @'
beast doctor    verify the whole stack (Blender bridge, UE, Higgsfield, ffmpeg, disk)
beast sync      clone/update all linked repos (repos.yml)
beast judge     score generated images vs a brief (local llava)  <imgs> --brief "..."
beast replay    name env drift vs a recorded run  <run-id> | --save-baseline | --check
beast ledger    verify the hash-chained provenance ledger (tamper-evident history)
beast validate  validate the Beast capability graph, packs, benchmark, and policy
beast status    show evidence levels and live GPU admission state
beast resource-check WORKLOAD   test a workload against live VRAM + protected reserve
beast checkpoint ...            write an atomic crash-recovery checkpoint
beast recover CHECKPOINT        verify Git state and evidence hashes before resuming
beast watch-validate PROCEDURE TIMELINE  prove visual-only and reinspection links
beast watch     video URL/file -> frames+transcript bundle an agent can "watch"
beast watch-index BUNDLE ["query"] -> build/search semantic visual memory
beast watch-seek BUNDLE --at TIME [--level 1|2|3] -> rewind/forward for missing evidence
beast watch-perceive --bundle BUNDLE --output NEW_DIR [--ocr-root RECEIPTS] -> CPU spatial/temporal measurements
beast watch-training prepare --source VIDEO_OR_URL --output NEW_DIR -> real-footage review workspace
beast watch-training render --review DIR --plan JSON --output NEW_DIR -> source-linked captioned draft
beast watch-instruction-gate --review DIR --units JSON --output NEW_DIR -> eligible private units or review request
beast watch-rewind-eval --review DIR --units JSON --output NEW_DIR -> bounded CPU reinspection comparison, no narration
beast watch-ui-regions --bundle BUNDLE --output NEW_DIR -> pinned OmniParser detector (CPU)
beast watch-fuse --pixels DIR --ui DIR --temporal DIR --output NEW_DIR -> frame-bound multimodal state
beast watch-temporal --bundle BUNDLE --output NEW_DIR -> admitted pinned V-JEPA 2 clip embeddings
beast recipes   list prompt recipe cards
'@
    }
}
