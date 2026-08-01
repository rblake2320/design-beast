# beast — Design Beast CLI. Add to PATH or alias:  Set-Alias beast <repo>\bin\beast.ps1
param([Parameter(Position = 0)][string]$Cmd = 'help', [Parameter(ValueFromRemainingArguments)]$Rest)

$Repo = Split-Path $PSScriptRoot -Parent

switch ($Cmd) {
    'doctor'  { python (Join-Path $Repo 'scripts\doctor.py') @Rest }
    'sync'    { & (Join-Path $Repo 'scripts\sync_repos.ps1') @Rest }
    'judge'   { python (Join-Path $Repo 'scripts\judge_image.py') @Rest }
    'replay'  { python (Join-Path $Repo 'scripts\replay_diff.py') @Rest }
    'ledger'  { python (Join-Path $Repo 'scripts\ledger_verify.py') @Rest }
    'watch'   { python (Join-Path $Repo 'scripts\watch_video.py') @Rest }
    'watch-index' { python (Join-Path $Repo 'scripts\watch_index.py') @Rest }
    'watch-seek' { python (Join-Path $Repo 'scripts\watch_seek.py') @Rest }
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
beast watch     video URL/file -> frames+transcript bundle an agent can "watch"
beast watch-index BUNDLE ["query"] -> build/search semantic visual memory
beast watch-seek BUNDLE --at TIME [--level 1|2|3] -> rewind/forward for missing evidence
beast recipes   list prompt recipe cards
'@
    }
}
