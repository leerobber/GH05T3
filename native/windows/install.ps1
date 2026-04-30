# GH05T3 — Native Windows Installer (v3)
# ----------------------------------------
# Run once in PowerShell as Administrator:
#   .\install.ps1
#
# Installs: Python 3.11, MongoDB Community, Node.js 20, Yarn (via winget).
# All open-source, all free, zero subscriptions.

$ErrorActionPreference = "Stop"
Write-Host "==> GH05T3 native install starting (v3)" -ForegroundColor Yellow

function Have($cmd) {
    return (Get-Command $cmd -ErrorAction SilentlyContinue) -ne $null
}

if (-not (Have winget)) {
    Write-Host "winget not found. Install App Installer from the Microsoft Store first." -ForegroundColor Red
    exit 1
}

# ---- Python 3.11 ----
if (-not (Have python) -or -not ((python --version 2>&1) -match "3\.1[1-9]")) {
    Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
    winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
}

# ---- Node.js 20 ----
if (-not (Have node)) {
    Write-Host "Installing Node.js 20..." -ForegroundColor Cyan
    winget install --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
}

# ---- Yarn ----
if (-not (Have yarn)) {
    Write-Host "Installing Yarn..." -ForegroundColor Cyan
    npm install -g yarn
}

# ---- MongoDB Community Edition ----
if (-not (Have mongod)) {
    Write-Host "Installing MongoDB Community..." -ForegroundColor Cyan
    winget install --id MongoDB.Server --silent --accept-source-agreements --accept-package-agreements
}

# ---- App folder ----
$APP = "$env:USERPROFILE\gh05t3"
Write-Host "App folder: $APP" -ForegroundColor Cyan
if (-not (Test-Path $APP)) {
    New-Item -ItemType Directory -Path $APP | Out-Null
}

# ---- Copy source ----
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $here)
Write-Host "Copying source from $repoRoot ..." -ForegroundColor Cyan
Copy-Item -Recurse -Force "$repoRoot\backend"   "$APP\backend"
Copy-Item -Recurse -Force "$repoRoot\frontend"  "$APP\frontend"
Copy-Item -Recurse -Force "$repoRoot\companion" "$APP\companion"
Copy-Item -Force          "$here\tray.py"             "$APP\tray.py"
Copy-Item -Force          "$here\voice.py"            "$APP\voice.py"
Copy-Item -Force          "$here\whisper_listener.py" "$APP\whisper_listener.py"

# ---- Backend .env ----
$envPath = "$APP\backend\.env"
if (-not (Test-Path $envPath)) {
    Set-Content $envPath @"
# GH05T3 backend — edit ANTHROPIC_API_KEY and GITHUB_PAT here,
# or paste them in the dashboard Keys tab after first boot.

MONGO_URL=mongodb://localhost:27017
DB_NAME=gh05t3
CORS_ORIGINS=*
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5-20250929
EMERGENT_LLM_KEY=

# v3 gateway (runs on 8002 alongside server.py on 8001)
GATEWAY_PORT=8002
GATEWAY_URL=http://localhost:8002

# Paste your keys here OR use the dashboard Keys tab on first boot
ANTHROPIC_API_KEY=
GITHUB_PAT=
GITHUB_REPO=leerobber/GH05T3
GITHUB_BRANCH=main
GH05T3_REPO_PATH=$APP

# Inference backends (fill when vLLM / llama.cpp are running)
VLLM_PRIMARY_URL=http://localhost:8010
LLAMA_VERIFIER_URL=http://localhost:8011
LLAMA_FALLBACK_URL=http://localhost:8012

# Security
KILLSWITCH_KEY_HASH=
GH05T3_SECRET=sovereign-ghost-mesh-key-2025

# Memory
MEMORY_DB_PATH=$APP\backend\memory\palace.db
SAGE_ELITE_THRESHOLD=0.90
"@
    Write-Host ""
    Write-Host "NOTE: $envPath created." -ForegroundColor Yellow
    Write-Host "      Paste your Anthropic + GitHub keys in the dashboard on first boot." -ForegroundColor Yellow
}

# ---- Frontend .env.local (baked into the React build) ----
Set-Content "$APP\frontend\.env.local" @"
REACT_APP_GW3_URL=http://localhost:8002
"@

# ---- Backend venv ----
Write-Host "Creating Python venv..." -ForegroundColor Cyan
Push-Location "$APP\backend"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip --quiet
.\.venv\Scripts\pip install -r requirements.txt --quiet
.\.venv\Scripts\pip install pystray pillow pyttsx3 sounddevice numpy `
    faster-whisper openwakeword edge-tts --quiet
Pop-Location

# ---- Frontend build ----
Write-Host "Building frontend (REACT_APP_GW3_URL baked in)..." -ForegroundColor Cyan
Push-Location "$APP\frontend"
yarn install --silent
yarn build
Pop-Location

# ---- Drop run.bat ----
Copy-Item -Force "$here\run.bat" "$APP\run.bat"

# ---- Startup shortcut ----
$wsh     = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
$lnk     = $wsh.CreateShortcut("$startup\GH05T3.lnk")
$lnk.TargetPath      = "$APP\run.bat"
$lnk.WorkingDirectory = $APP
$lnk.IconLocation    = "$APP\frontend\public\favicon.ico,0"
$lnk.Save()

Write-Host ""
Write-Host "==> Install complete." -ForegroundColor Green
Write-Host "    Run now:     cd $APP && .\run.bat" -ForegroundColor Green
Write-Host "    Dashboard:   http://localhost:3210" -ForegroundColor Green
Write-Host "    Gateway v3:  http://localhost:8002" -ForegroundColor Green
Write-Host ""
Write-Host "    On first open the dashboard will ask for your" -ForegroundColor Yellow
Write-Host "    Anthropic API key and GitHub token." -ForegroundColor Yellow
