<#
.SYNOPSIS
    Reseed the local Postgres database.

.DESCRIPTION
    Drops and re-creates all tables by running seed/seed.sql against the
    Docker Postgres container.

    Run from the repo root:
        .\scripts\dev-reseed.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $RepoRoot "app.py"))) { $RepoRoot = $ScriptDir }
Push-Location $RepoRoot

function Write-Step { param([string]$Msg) Write-Host "`n:: $Msg" -ForegroundColor Cyan }

try {
    $SeedFile = Join-Path $RepoRoot "seed\seed.sql"
    if (-not (Test-Path $SeedFile)) { throw "seed/seed.sql not found." }

    Write-Step "Seeding database"
    docker exec -i reporting_db psql -U postgres -d reporting -f - < $SeedFile
    if ($LASTEXITCODE -ne 0) { throw "Seed failed." }
    Write-Host "  Database seeded successfully." -ForegroundColor Green
}
finally {
    Pop-Location
}
