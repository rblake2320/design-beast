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
    'update'  { & (Join-Path $Repo 'scripts\update_stack.ps1') @Rest; exit $LASTEXITCODE }
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
    'recipes' {
        Get-ChildItem (Join-Path $Repo 'design-system\recipes') -Filter *.md | ForEach-Object {
            $head = (Get-Content $_.FullName -TotalCount 3) -join ' '
            "{0,-28} {1}" -f $_.BaseName, ($head -replace '#\s*Recipe\s*—\s*', '')
        }
    }
    'help' {
        @'
beast doctor    verify the whole stack (Blender bridge, UE, Higgsfield, ffmpeg, disk)
beast update    owner-run only: upgrade ffmpeg + HyperFrames (+skills), then re-run doctor; previews unless -Apply
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
beast recipes   list prompt recipe cards
'@
    }
    default {
        [Console]::Error.WriteLine("unknown beast command: $Cmd; run beast help")
        exit 2
    }
}
