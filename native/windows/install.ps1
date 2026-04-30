# GH05T3 - Native Windows Installer (v3)
# ----------------------------------------
# Run once in PowerShell as Administrator from inside the repo:
#   cd C:\Users\<you>\GH05T3\native\windows
#   .\install.ps1
#
# Installs: Python 3.11, MongoDB Community, Node.js 20, Yarn (via winget).
# Installs in-place - uses the cloned repo as the app folder (no copy needed).

$ErrorActionPreference = "Stop"
Write-Host "==> GH05T3 native install starting (v3)" -ForegroundColor Yellow

# ---- Stop any running GH05T3 processes (frees lock on .venv\python.exe) ----
Write-Host "Stopping any running GH05T3 processes..." -ForegroundColor Cyan
foreach ($t in @("gh05t3-mongo","gh05t3-backend","gh05t3-gateway-v3","gh05t3-frontend","gh05t3-whisper")) {
    & taskkill /FI "WINDOWTITLE eq $t" /F 2>$null | Out-Null
}
Stop-Process -Name "mongod"  -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python"  -Force -ErrorAction SilentlyContinue
Stop-Process -Name "python3" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

function Have($cmd) {
    return (Get-Command $cmd -ErrorAction SilentlyContinue) -ne $null
}

if (-not (Have winget)) {
    Write-Host "winget not found. Install App Installer from the Microsoft Store first." -ForegroundColor Red
    exit 1
}

# ---- Derive paths ----
# install.ps1 lives at: <repo>\native\windows\install.ps1
# So the repo root is two levels up.
$here     = Split-Path -Parent $MyInvocation.MyCommand.Path
$APP      = (Get-Item (Join-Path $here "..\.." )).FullName   # repo root
Write-Host "App folder (repo root): $APP" -ForegroundColor Cyan

# ---- Python 3.11 ----
if (-not (Have python) -or -not ((python --version 2>&1) -match "3\.1[1-9]")) {
    Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
    winget install --id Python.Python.3.11 --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
}

# ---- Node.js 20 ----
if (-not (Have node)) {
    Write-Host "Installing Node.js 20..." -ForegroundColor Cyan
    winget install --id OpenJS.NodeJS.LTS --silent --accept-source-agreements --accept-package-agreements
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
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
# winget does not add MongoDB to the running session's PATH - do it manually
$mongoBase = "C:\Program Files\MongoDB\Server"
if (Test-Path $mongoBase) {
    $mongoBin = (Get-ChildItem $mongoBase -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName + "\bin"
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    if ($machinePath -notlike "*$mongoBin*") {
        [System.Environment]::SetEnvironmentVariable("PATH", "$machinePath;$mongoBin", "Machine")
    }
    $env:PATH = "$env:PATH;$mongoBin"
    Write-Host "MongoDB bin added to PATH: $mongoBin" -ForegroundColor Cyan
}

# ---- Runtime data dirs ----
foreach ($d in @("$APP\mongo-data","$APP\backend\memory","$APP\backend\evolution")) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

# ---- Backend .env ----
$envPath = "$APP\backend\.env"
if (-not (Test-Path $envPath)) {
    Set-Content $envPath @"
# GH05T3 backend
# Paste your keys here OR use the dashboard Keys tab on first boot.

MONGO_URL=mongodb://localhost:27017
DB_NAME=gh05t3
CORS_ORIGINS=*

# --- LLM provider (anthropic | groq | google | ollama) ---
# Priority: Anthropic → Groq → Google → Ollama (first key wins).
# For fully free operation: leave ANTHROPIC_API_KEY blank and set GROQ_API_KEY.
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6

# Anthropic (paid) — best quality
ANTHROPIC_API_KEY=

# Groq (free tier) — llama-3.3-70b, fast, generous free quota
GROQ_API_KEY=

# Google AI (free tier) — gemini-2.0-flash
GOOGLE_AI_KEY=

# v3 gateway (port 8002, server.py keeps 8001)
GATEWAY_PORT=8002
GATEWAY_URL=http://localhost:8002

GITHUB_PAT=
GITHUB_REPO=leerobber/GH05T3
GITHUB_BRANCH=main
GH05T3_REPO_PATH=$APP

VLLM_PRIMARY_URL=http://localhost:8010
LLAMA_VERIFIER_URL=http://localhost:8011
LLAMA_FALLBACK_URL=http://localhost:8012

# --- Ollama GPU protection (shared GPU with TatorTot) ---
# Max simultaneous GPU requests (1 = serialize all calls, prevents OOM)
OLLAMA_MAX_CONCURRENT=1
# Seconds to keep model in VRAM after last call (0 = unload immediately)
OLLAMA_KEEP_ALIVE=0
# Context window tokens — smaller = less VRAM per call (default 2048)
OLLAMA_NUM_CTX=2048
# Max output tokens per call (default 512)
OLLAMA_NUM_PREDICT=512

KILLSWITCH_KEY_HASH=
GH05T3_SECRET=sovereign-ghost-mesh-key-2025

MEMORY_DB_PATH=$APP\backend\memory\palace.db
SAGE_ELITE_THRESHOLD=0.90

# --- Multi-instance peer mesh ---
# Set INSTANCE_LABEL to a human name for this machine (TatorTot, Laptop, Cloud).
# Set INSTANCE_URL to the URL other peers use to reach THIS instance.
# Set PEER_URLS to comma-separated base URLs of other GH05T3 instances.
# Use Tailscale hostnames for cross-network connectivity.
INSTANCE_LABEL=TatorTot
INSTANCE_ROLE=primary
INSTANCE_URL=http://localhost:8001
PEER_URLS=
SYNC_INTERVAL=300
"@
    Write-Host "Created $envPath" -ForegroundColor Yellow
}

# ---- Frontend .env.local (baked into React build at build time) ----
Set-Content "$APP\frontend\.env.local" @"
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_GW3_URL=http://localhost:8002
"@

# ---- Backend venv (delete first so a locked/stale venv never blocks pip) ----
Write-Host "Creating Python venv..." -ForegroundColor Cyan
Push-Location "$APP\backend"
if (Test-Path ".venv") {
    Write-Host "Removing old venv..." -ForegroundColor Cyan
    # Remove-Item can fail if Windows Defender holds a .pyd file open.
    # Retry up to 3 times, falling back to cmd's rd which bypasses PS file locking.
    $removed = $false
    for ($i = 0; $i -lt 3; $i++) {
        try {
            Remove-Item -Recurse -Force ".venv" -ErrorAction Stop
            $removed = $true
            break
        } catch {
            Write-Host "  File still locked, waiting 5s (attempt $($i+1)/3)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            & cmd.exe /c "rd /s /q .venv" 2>$null
            if (-not (Test-Path ".venv")) { $removed = $true; break }
        }
    }
    if (-not $removed) {
        throw "Cannot delete .venv - a process still holds a file lock. Reboot and retry."
    }
}
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip --quiet
.\.venv\Scripts\pip install -r requirements.txt --quiet
.\.venv\Scripts\pip install pystray pillow pyttsx3 sounddevice numpy `
    faster-whisper openwakeword edge-tts --quiet
Pop-Location

# ---- Frontend build (REACT_APP_GW3_URL baked in) ----
Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location "$APP\frontend"
yarn install --silent
yarn build
Pop-Location

# ---- Copy tray / voice helpers into repo root for run.bat ----
foreach ($f in @("tray.py","voice.py","whisper_listener.py")) {
    Copy-Item -Force "$here\$f" "$APP\$f"
}

# ---- Drop run.bat into repo root ----
Copy-Item -Force "$here\run.bat" "$APP\run.bat"

# ---- Startup shortcut ----
$wsh     = New-Object -ComObject WScript.Shell
$startup = [Environment]::GetFolderPath('Startup')
$lnk     = $wsh.CreateShortcut("$startup\GH05T3.lnk")
$lnk.TargetPath       = "$APP\run.bat"
$lnk.WorkingDirectory = $APP
try { $lnk.IconLocation = "$APP\frontend\public\favicon.ico,0" } catch {}
$lnk.Save()

Write-Host ""
Write-Host "==> Install complete." -ForegroundColor Green
Write-Host ""
Write-Host "  Run now - paste each line separately into PowerShell:" -ForegroundColor Green
Write-Host "    cd `"$APP`"" -ForegroundColor White
Write-Host "    .\run.bat" -ForegroundColor White
Write-Host ""
Write-Host "  Dashboard: http://localhost:3210" -ForegroundColor Green
Write-Host "  Keys modal appears automatically on first open." -ForegroundColor Yellow
