param(
    [string]$OutputZip = "",
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoName = Split-Path $repoRoot -Leaf
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if (-not $OutputZip) {
    $OutputZip = Join-Path (Split-Path $repoRoot -Parent) ("{0}_portable_{1}.zip" -f $repoName, $timestamp)
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("{0}_portable_{1}" -f $repoName, $timestamp)
$stagingRoot = Join-Path $tempRoot $repoName

if ((Test-Path $OutputZip) -and -not $Overwrite) {
    throw "Output zip already exists: $OutputZip"
}

if (Test-Path $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null

Get-ChildItem -LiteralPath $repoRoot -Force | ForEach-Object {
    if ($_.Name -in @(".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv", "ENV", "env", "ui_env", "ocr_env", "Incoming")) {
        return
    }
    elseif (-not $_.PSIsContainer -and $_.Name -eq ".env") {
        return
    }
    elseif ($_.PSIsContainer -and $_.Name -eq "shared") {
        Copy-Item -LiteralPath $_.FullName -Destination $stagingRoot -Recurse -Force
        $copiedSharedFiles = Join-Path $stagingRoot "shared\\files"
        if (Test-Path $copiedSharedFiles) {
            Remove-Item -LiteralPath $copiedSharedFiles -Recurse -Force
        }
    }
    else {
        Copy-Item -LiteralPath $_.FullName -Destination $stagingRoot -Recurse -Force
    }
}

$excludedNestedDirNames = @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
Get-ChildItem -LiteralPath $stagingRoot -Recurse -Directory | Where-Object { $_.Name -in $excludedNestedDirNames } | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Recurse -Force
}

Get-ChildItem -LiteralPath $stagingRoot -Recurse -File -Include "*.pyc" | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $stagingRoot "Incoming") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path (Join-Path $stagingRoot "shared") "files") | Out-Null

if ((Test-Path $OutputZip) -and $Overwrite) {
    Remove-Item -LiteralPath $OutputZip -Force
}

$archiveEntries = Get-ChildItem -LiteralPath $stagingRoot -Force | Select-Object -ExpandProperty FullName
Compress-Archive -LiteralPath $archiveEntries -DestinationPath $OutputZip -Force
Remove-Item -LiteralPath $tempRoot -Recurse -Force

Write-Host "Portable bundle created:"
Write-Host $OutputZip
