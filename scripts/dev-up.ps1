<#
.SYNOPSIS
    Bootstrap and run the SQL Reporting Dashboard locally.

.DESCRIPTION
    Creates a virtual environment (if needed), installs dependencies,
    starts the Docker database, seeds it, and launches the Streamlit app.

    Run from the repo root:
        .\scripts\dev-up.ps1

    Or from the scripts folder:
        .\dev-up.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Resolve repo root (works whether invoked from repo root or scripts/) ─────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Split-Path -Parent $ScriptDir
if (-not (Test-Path (Join-Path $RepoRoot "app.py"))) {
    # Maybe invoked directly from the repo root
    $RepoRoot = $ScriptDir
}
Push-Location $RepoRoot

function Write-Step { param([string]$Msg) Write-Host "`n:: $Msg" -ForegroundColor Cyan }

try {
    # ── 1. Virtual environment ───────────────────────────────────────────
    Write-Step "Checking virtual environment"
    if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
        Write-Host "  Creating .venv ..."
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment." }
    }
    & .venv\Scripts\Activate.ps1
    Write-Host "  .venv active: $(python --version)"

    # ── 2. Dependencies ──────────────────────────────────────────────────
    Write-Step "Installing dependencies"
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
    Write-Host "  Dependencies OK"

    # ── 3. .env ──────────────────────────────────────────────────────────
    Write-Step "Checking .env"
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Host "  Copied .env.example -> .env"
        } else {
            throw ".env and .env.example both missing. Create .env with DATABASE_URL."
        }
    } else {
        Write-Host "  .env exists"
    }

    # ── 4. Docker database ───────────────────────────────────────────────
    Write-Step "Starting Docker database"
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed. Is Docker running?" }

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

    # ── 5. Seed ──────────────────────────────────────────────────────────
    Write-Step "Seeding database"
    $seedFile = Join-Path $RepoRoot "seed\seed.sql"
    docker exec -i reporting_db psql -U postgres -d reporting -f - < $seedFile
    if ($LASTEXITCODE -ne 0) { throw "Database seeding failed." }
    Write-Host "  Seed applied"

    # ── 6. Launch ────────────────────────────────────────────────────────
    Write-Step "Launching Streamlit"
    Write-Host "  Open http://localhost:8501 in your browser."
    Write-Host ""
    python -m streamlit run app.py
}
finally {
    Pop-Location
}
