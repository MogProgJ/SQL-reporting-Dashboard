<#
.SYNOPSIS
    Run the test suite locally.

.DESCRIPTION
    Runs pytest against the tests/ directory.  By default runs unit tests
    only.  Pass -Integration to include integration tests (requires a
    running, seeded Postgres).

    Run from the repo root:
        .\scripts\dev-test.ps1                  # unit tests only
        .\scripts\dev-test.ps1 -Integration     # include integration tests
        .\scripts\dev-test.ps1 -All             # all tests
#>

[CmdletBinding()]
param(
    [switch]$Integration,
    [switch]$All
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $RepoRoot "app.py"))) { $RepoRoot = $ScriptDir }
Push-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { throw ".venv not found. Run dev-up.ps1 first." }

function Write-Step { param([string]$Msg) Write-Host "`n:: $Msg" -ForegroundColor Cyan }

try {
    if ($All) {
        Write-Step "Running ALL tests (unit + integration)"
        & $VenvPython -m pytest tests/ -v
    }
    elseif ($Integration) {
        Write-Step "Running integration tests"
        $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5434/reporting"
        & $VenvPython -m pytest tests/ -v -m integration
    }
    else {
        Write-Step "Running unit tests"
        & $VenvPython -m pytest tests/ -v -m "not integration"
    }

    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    Write-Host "`n  All tests passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
