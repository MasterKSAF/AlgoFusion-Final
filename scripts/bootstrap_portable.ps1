param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$incomingDir = Join-Path $repoRoot "Incoming"
$sharedFilesDir = Join-Path (Join-Path $repoRoot "shared") "files"
$envExample = Join-Path (Join-Path (Join-Path $repoRoot "shared") "config\\examples") ".env.example"
$envPath = Join-Path $repoRoot ".env"

New-Item -ItemType Directory -Force -Path $incomingDir | Out-Null
New-Item -ItemType Directory -Force -Path $sharedFilesDir | Out-Null

if (-not (Test-Path $envExample)) {
    throw "Env template not found: $envExample"
}

if ($Force -or -not (Test-Path $envPath)) {
    Copy-Item -LiteralPath $envExample -Destination $envPath -Force
    $envStatus = "written"
}
else {
    $envStatus = "kept"
}

Write-Host "Portable bootstrap complete."
Write-Host "Repo root      : $repoRoot"
Write-Host "Incoming       : $incomingDir"
Write-Host "Shared files   : $sharedFilesDir"
Write-Host ".env status    : $envStatus"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Review .env if you need custom paths."
Write-Host "2. Run: docker compose up --build"
