# GH05T3 — Native Windows Installer
# ----------------------------------
# Run once in PowerShell as Administrator:
#   .\install.ps1
#
# This installs: Python 3.11+, MongoDB Community, Node 20, Yarn (via winget).
# All open-source, all free, zero subscriptions.

$ErrorActionPreference = "Stop"
Write-Host "==> GH05T3 native install starting" -ForegroundColor Yellow

function Have($cmd) {
    return (Get-Command $cmd -ErrorAction SilentlyContinue) -ne $null
}

if (-not (Have winget)) {
    Write-Host "winget not found. Install App Installer from the Microsoft Store first." -ForegroundColor Red
    exit 1
}

# ---- Python 3.11 ----
if (-not (Have python) -or -not ((python --version) -match "3\.1[1-9]")) {
    Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
    winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
}

# ---- Node.js 20 ----
if (-not (Have node)) {
    Write-Host "Installing Node.js 20..." -ForegroundColor Cyan
    winget install --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
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
if (-not (Test-Path $APP)) {
    Write-Host "Creating app folder at $APP ..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Path $APP | Out-Null
}

# Copy backend & frontend source into $APP
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent (Split-Path -Parent $here)   # /app
Copy-Item -Recurse -Force "$repoRoot\backend"  "$APP\backend"
Copy-Item -Recurse -Force "$repoRoot\frontend" "$APP\frontend"
Copy-Item -Recurse -Force "$repoRoot\companion" "$APP\companion"

# ---- Backend venv ----
Write-Host "Creating Python venv..." -ForegroundColor Cyan
Push-Location "$APP\backend"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install pystray pillow pyttsx3 sounddevice numpy faster-whisper openwakeword edge-tts
Pop-Location

# ---- Frontend build ----
Write-Host "Building frontend (production bundle)..." -ForegroundColor Cyan
Push-Location "$APP\frontend"
yarn install
yarn build
Pop-Location

# ---- .env files ----
if (-not (Test-Path "$APP\backend\.env")) {
    Set-Content "$APP\backend\.env" @"
MONGO_URL=mongodb://localhost:27017
DB_NAME=gh05t3
CORS_ORIGINS=*
EMERGENT_LLM_KEY=
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5-20250929
"@
    Write-Host "`nNOTE: Edit $APP\backend\.env and paste your EMERGENT_LLM_KEY (or leave empty to use Google/Groq free tiers)." -ForegroundColor Yellow
}

# ---- Shortcut on Startup ----
$wsh = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
$lnk = $wsh.CreateShortcut("$startup\GH05T3.lnk")
$lnk.TargetPath = "$APP\run.bat"
$lnk.WorkingDirectory = $APP
$lnk.IconLocation = "$APP\frontend\public\favicon.ico,0"
$lnk.Save()

# ---- Drop run.bat ----
Copy-Item -Force "$here\run.bat" "$APP\run.bat"
Copy-Item -Force "$here\tray.py" "$APP\tray.py"
Copy-Item -Force "$here\voice.py" "$APP\voice.py"

Write-Host "`n==> Install complete. GH05T3 will auto-start on next login." -ForegroundColor Green
Write-Host "To start now: cd $APP && .\run.bat" -ForegroundColor Green
Write-Host "Dashboard will open at: http://localhost:3210" -ForegroundColor Green
