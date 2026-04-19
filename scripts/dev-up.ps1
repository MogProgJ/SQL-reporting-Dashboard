<#
.SYNOPSIS
    Bootstrap and run the SQL Reporting Dashboard locally.

.DESCRIPTION
    Creates a virtual environment (if needed), installs dependencies,
    starts the Docker database, seeds it, and launches the Streamlit app.

    Run from the repo root:
        .\scripts\dev-up.ps1

    Or with flags:
        .\scripts\dev-up.ps1 -Reseed          # Force reseed even if tables exist
        .\scripts\dev-up.ps1 -SkipDocker       # Skip Docker start (DB already running)
        .\scripts\dev-up.ps1 -SkipInstall      # Skip pip install (deps already installed)
#>

[CmdletBinding()]
param(
  [switch]$Reseed,
  [switch]$SkipDocker,
  [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Resolve repo root (works whether invoked from repo root or scripts/) ─────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $RepoRoot "app.py"))) {
  # Maybe invoked directly from the repo root
  $RepoRoot = $ScriptDir
}
Push-Location $RepoRoot

# Prefer direct venv python to avoid activation issues
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function Write-Step { param([string]$Msg) Write-Host "`n:: $Msg" -ForegroundColor Cyan }

try {
  # ── 1. Virtual environment ───────────────────────────────────────────
  Write-Step "Checking virtual environment"
  if (-not (Test-Path $VenvPython)) {
    Write-Host "  Creating .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
  }
  Write-Host "  .venv python: $(&$VenvPython --version)"

  # ── 2. Dependencies ──────────────────────────────────────────────────
  if (-not $SkipInstall) {
    Write-Step "Installing dependencies"
    & $VenvPython -m pip install --quiet --upgrade pip
    & $VenvPython -m pip install --quiet -r requirements.txt -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    Write-Host "  Dependencies OK"
  }
  else {
    Write-Step "Skipping dependency install (-SkipInstall)"
  }

  # ── 3. .env ──────────────────────────────────────────────────────────
  Write-Step "Checking .env"
  if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
      Copy-Item ".env.example" ".env"
      Write-Host "  Copied .env.example -> .env"
    }
    else {
      throw ".env and .env.example both missing. Create .env with DATABASE_URL."
    }
  }
  else {
    Write-Host "  .env exists"
  }

  # ── 4. Docker database ───────────────────────────────────────────────
  if (-not $SkipDocker) {
    Write-Step "Starting Docker database"

    # Check Docker reachability
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
      throw "Docker is not running. Start Docker Desktop and try again."
    }

    docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed." }

    # Wait for healthy
    Write-Host "  Waiting for Postgres to be ready ..."
    $timeout = 60
    $elapsed = 0
    while ($elapsed -lt $timeout) {
      $health = docker inspect --format "{{.State.Health.Status}}" reporting_db 2>$null
      if ($health -eq "healthy") { break }
      Start-Sleep -Seconds 2
      $elapsed += 2
    }
    if ($elapsed -ge $timeout) { throw "Database did not become healthy within ${timeout}s." }
    Write-Host "  Postgres is healthy"
  }
  else {
    Write-Step "Skipping Docker start (-SkipDocker)"
  }

  # ── 5. Seed ──────────────────────────────────────────────────────────
  Write-Step "Seeding database"
  $seedFile = Join-Path $RepoRoot "seed\seed.sql"
  if (-not (Test-Path $seedFile)) {
    throw "Seed file not found: $seedFile"
  }
  Get-Content $seedFile -Raw | docker exec -i reporting_db psql --set ON_ERROR_STOP=1 -U postgres -d reporting
  if ($LASTEXITCODE -ne 0) { throw "Database seeding failed. Check seed/seed.sql for errors." }
  Write-Host "  Seed applied (all tables created + demo data loaded)"

  # ── 6. Launch ────────────────────────────────────────────────────────
  Write-Step "Launching Streamlit"
  Write-Host "  Open http://localhost:8501 in your browser."
  Write-Host ""
  & $VenvPython -m streamlit run app.py
}
finally {
  Pop-Location
}
