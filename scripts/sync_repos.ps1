# Clone or update every repo listed in repos.yml (simple parser — name/url pairs only).
# Repos land as siblings of this hub: <parent>\<name>
param([string]$Root = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent))

$yml = Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) 'repos.yml') -Raw
$pairs = [regex]::Matches($yml, '-\s+name:\s*(\S+)\s*\r?\n\s*url:\s*(\S+)')

foreach ($m in $pairs) {
    $name = $m.Groups[1].Value
    $url  = $m.Groups[2].Value
    $dest = Join-Path $Root $name
    if (Test-Path (Join-Path $dest '.git')) {
        Write-Host "update  $name" -ForegroundColor Cyan
        git -C $dest pull --ff-only
    } else {
        Write-Host "clone   $name" -ForegroundColor Green
        git clone $url $dest
    }
}
