# ============================================================
#  EmoCare — Environment Setup Script (PowerShell)
#  Run from project root: .\scripts\setup_env.ps1
# ============================================================

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  EmoCare Environment Setup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Create virtual environment ──────────────────────
$VenvPath = Join-Path $ProjectRoot "venv"
if (Test-Path $VenvPath) {
    Write-Host "[SKIP] venv already exists at $VenvPath" -ForegroundColor Yellow
} else {
    Write-Host "[1/5] Creating virtual environment at $VenvPath ..." -ForegroundColor Green
    python -m venv $VenvPath
    Write-Host "      Done." -ForegroundColor Gray
}

# ── Step 2: Activate venv ───────────────────────────────────
Write-Host "[2/5] Activating virtual environment ..." -ForegroundColor Green
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
& $ActivateScript

# ── Step 3: Upgrade pip ─────────────────────────────────────
Write-Host "[3/5] Upgrading pip ..." -ForegroundColor Green
python -m pip install --upgrade pip

# ── Step 4: Install requirements ────────────────────────────
$ReqFile = Join-Path $ProjectRoot "requirements.txt"
Write-Host "[4/5] Installing requirements from $ReqFile ..." -ForegroundColor Green
Write-Host "      (This may take several minutes on first run)" -ForegroundColor Gray
pip install -r $ReqFile

# ── Step 5: Register Jupyter kernel ─────────────────────────
Write-Host "[5/5] Registering Jupyter kernel as 'emocare-kernel' ..." -ForegroundColor Green
python -m ipykernel install --user --name emocare-kernel --display-name "EmoCare (Python 3.13)"

# ── Done ────────────────────────────────────────────────────
Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To activate the venv manually:" -ForegroundColor White
Write-Host "    .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To start JupyterLab:" -ForegroundColor White
Write-Host "    jupyter lab" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Select kernel: 'EmoCare (Python 3.13)'" -ForegroundColor White
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""
