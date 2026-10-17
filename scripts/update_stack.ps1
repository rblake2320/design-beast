# beast update - owner-triggered upgrade of the version-drifting tools, then proof.
# Never scheduled: updates happen only when the owner runs this. Without -Apply it
# only previews (safe default - a lost flag must never mean "upgrade").
# Flags are read from $args, not param(), because beast.ps1 forwards them as
# strings and a [switch] would silently stay off.
$unknown = $args | Where-Object { $_ -ne '-Apply' }
if ($unknown) { [Console]::Error.WriteLine("beast update: unknown argument(s): $unknown"); exit 2 }
$Apply = $args -contains '-Apply'

$Repo = Split-Path $PSScriptRoot -Parent
$failed = @()

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "== $Name"
    if (-not $Apply) { Write-Host "   (preview) $Action"; return }
    & $Action
    if ($LASTEXITCODE -ne 0) { $script:failed += $Name; Write-Host "   FAILED (exit $LASTEXITCODE)" }
}

# -1978335189 = winget "no applicable update" (already current) - not a failure.
Step 'ffmpeg (winget)' { winget upgrade --id Gyan.FFmpeg --exact --silent --accept-source-agreements --accept-package-agreements; if ($LASTEXITCODE -eq -1978335189) { $global:LASTEXITCODE = 0 } }
Step 'hyperframes CLI (npm)' { npm i -g hyperframes@latest }
Step 'hyperframes skills' { hyperframes skills update }

if (-not $Apply) { Write-Host "preview only - run 'beast update -Apply' to upgrade"; exit 0 }
Write-Host "== doctor (proof)"
& python (Join-Path $Repo 'scripts\doctor.py')
$doctor = $LASTEXITCODE
if ($failed) { Write-Host "update steps failed: $($failed -join ', ')" }
exit ([int]($failed.Count -gt 0) + $doctor)
