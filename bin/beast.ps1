# beast — Design Beast CLI. Add to PATH or alias:  Set-Alias beast <repo>\bin\beast.ps1
param([Parameter(Position = 0)][string]$Cmd = 'help', [Parameter(ValueFromRemainingArguments)]$Rest)

$Repo = Split-Path $PSScriptRoot -Parent
$ErrorActionPreference = 'Stop'

function Invoke-BeastPython {
    param([string]$Script, [string[]]$CommandArguments = @())
    & python (Join-Path $Repo $Script) @CommandArguments @Rest
    exit $LASTEXITCODE
}

switch ($Cmd) {
    'doctor'  { Invoke-BeastPython 'scripts\doctor.py' }
    'sync'    { & (Join-Path $Repo 'scripts\sync_repos.ps1') @Rest }
    'judge'   { Invoke-BeastPython 'scripts\judge_image.py' }
    'replay'  { Invoke-BeastPython 'scripts\replay_diff.py' }
    'ledger'  { Invoke-BeastPython 'scripts\ledger_verify.py' }
    'validate' { Invoke-BeastPython 'scripts\beast_core.py' -CommandArguments @('validate') }
    'status' { Invoke-BeastPython 'scripts\beast_core.py' -CommandArguments @('status') }
    'resource-check' { Invoke-BeastPython 'scripts\beast_core.py' -CommandArguments @('resource-check') }
    'checkpoint' { Invoke-BeastPython 'scripts\write_recovery_checkpoint.py' }
    'recover' { Invoke-BeastPython 'scripts\verify_recovery_checkpoint.py' }
    'watch-validate' { Invoke-BeastPython 'scripts\validate_watch_procedure.py' }
    'watch'   { Invoke-BeastPython 'scripts\watch_video.py' }
    'watch-index' { Invoke-BeastPython 'scripts\watch_index.py' }
    'watch-seek' { Invoke-BeastPython 'scripts\watch_seek.py' }
    'watch-perceive' { Invoke-BeastPython 'scripts\watch_perception.py' }
    'watch-training' { Invoke-BeastPython 'scripts\watch_training.py' }
    'watch-narrate' { Invoke-BeastPython 'scripts\narrate_watch_training.py' }
    'watch-instruction-gate' { Invoke-BeastPython 'scripts\gate_watch_instruction.py' }
    'watch-rewind-eval' { Invoke-BeastPython 'scripts\evaluate_watch_rewind.py' }
    'watch-ui-regions' { Invoke-BeastPython 'scripts\watch_ui_regions.py' }
    'watch-fuse' { Invoke-BeastPython 'scripts\fuse_watch_state.py' }
    'watch-temporal' {
        $EncoderPython = Join-Path $Repo '.venv-watch-temporal\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $EncoderPython)) {
            throw 'Temporal environment missing; follow docs/WATCH-PIXEL-STATE.md setup.'
        }
        & $EncoderPython (Join-Path $Repo 'scripts\watch_temporal_encoder.py') @Rest
        exit $LASTEXITCODE
    }
    'recipes' {
        Get-ChildItem (Join-Path $Repo 'design-system\recipes') -Filter *.md | ForEach-Object {
            $head = (Get-Content $_.FullName -TotalCount 3) -join ' '
            "{0,-28} {1}" -f $_.BaseName, ($head -replace '#\s*Recipe\s*—\s*', '')
        }
    }
    'help' {
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
    default {
        [Console]::Error.WriteLine("unknown beast command: $Cmd; run beast help")
        exit 2
    }
}
