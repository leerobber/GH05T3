# GH05T3 - Native Windows Installer (v3)
# ----------------------------------------
# Run once in PowerShell as Administrator from inside the repo:
#   cd C:\Users\<you>\GH05T3\native\windows
#   .\install.ps1
#
# Installs: Python 3.11, MongoDB Community, Node.js 20, Yarn (via winget).
# Installs in-place - uses the cloned repo as the app folder (no copy needed).
# Binds backend/gateway to 0.0.0.0 so Android on same WiFi can reach the dashboard.

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
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$APP  = (Get-Item (Join-Path $here "..\.." )).FullName   # repo root
Write-Host "App folder (repo root): $APP" -ForegroundColor Cyan

# ---- Detect LAN IP (for Android access on same WiFi) ----
$LAN_IP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notmatch "^127\." -and $_.PrefixOrigin -ne "WellKnown" } |
    Sort-Object InterfaceIndex |
    Select-Object -First 1).IPAddress
if (-not $LAN_IP) { $LAN_IP = "localhost" }
Write-Host "Detected LAN IP: $LAN_IP" -ForegroundColor Cyan
# Save for run.bat to display the Android URL
$LAN_IP | Out-File "$APP\lan_ip.txt" -Encoding ascii -NoNewline

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

# ---- Windows Firewall — open GH05T3 ports for LAN access (Android) ----
Write-Host "Opening Windows Firewall for GH05T3 ports (3210, 8001, 8002)..." -ForegroundColor Cyan
foreach ($port in @(3210, 8001, 8002)) {
    $ruleName = "GH05T3-port-$port"
    netsh advfirewall firewall delete rule name="$ruleName" >$null 2>&1
    netsh advfirewall firewall add rule name="$ruleName" dir=in action=allow protocol=TCP localport=$port | Out-Null
    Write-Host "  Firewall: port $port open" -ForegroundColor Gray
}

# ---- Runtime data dirs ----
foreach ($d in @("$APP\mongo-data","$APP\backend\memory","$APP\backend\evolution")) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}

# ---- Backend .env (only create if missing — preserves existing keys) ----
$envPath = "$APP\backend\.env"
if (-not (Test-Path $envPath)) {
    Set-Content $envPath @"
# GH05T3 backend
# Paste your keys here OR use the LLM Config panel in the dashboard.

MONGO_URL=mongodb://localhost:27017
DB_NAME=gh05t3
CORS_ORIGINS=*

# --- LLM provider (anthropic | groq | google | ollama) ---
# Priority: Anthropic -> Groq -> Google -> Ollama (first available key wins).
# For fully free operation: leave ANTHROPIC_API_KEY blank, set GROQ_API_KEY.
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6

# Anthropic (paid) - best quality chat
ANTHROPIC_API_KEY=

# Groq (free tier) - llama-3.3-70b, fast, generous free quota
# Get key free at: https://console.groq.com
GROQ_API_KEY=

# Google AI (free tier) - gemini-2.0-flash
# Get key free at: https://aistudio.google.com/app/apikey
GOOGLE_AI_KEY=

# v3 gateway (port 8002, server.py keeps 8001)
GATEWAY_PORT=8002
GATEWAY_URL=http://${LAN_IP}:8002

GITHUB_PAT=
GITHUB_REPO=leerobber/GH05T3
GITHUB_BRANCH=main
GH05T3_REPO_PATH=$APP

VLLM_PRIMARY_URL=http://localhost:8010
LLAMA_VERIFIER_URL=http://localhost:8011
LLAMA_FALLBACK_URL=http://localhost:8012

# --- Ollama GPU protection + model selection ---
OLLAMA_MAX_CONCURRENT=1
OLLAMA_KEEP_ALIVE=0
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_PREDICT=512
# Set OLLAMA_VRAM_GB to your GPU's VRAM so GH05T3 auto-picks the right model quant.
# e.g. RTX 3060 12GB → 12, RTX 5050 24GB → 24, iGPU 4GB → 4
OLLAMA_VRAM_GB=0

# --- Training pipeline ---
# Set TRAIN_USE_ANTHROPIC=1 to use Claude for fast high-quality generation (uses credits).
# Leave 0 for fully free: Groq free tier → Google free → local Ollama.
TRAIN_USE_ANTHROPIC=0
# Budget cap for Anthropic (Haiku) calls during training (only when TRAIN_USE_ANTHROPIC=1)
# TRAIN_BUDGET_TARGET: soft warning threshold (keeps going, just logs)
# TRAIN_BUDGET_HARD:   hard stop — switches to free providers. Set < $8 to stay safe.
TRAIN_BUDGET_TARGET=5.00
TRAIN_BUDGET_HARD=7.50
# Per-dataset targets (reduce for quick test runs, e.g. 100 each)
TRAIN_TARGET_DEFENSE=5000
TRAIN_TARGET_REASONING=3000
TRAIN_TARGET_CVE=3000
TRAIN_TARGET_BOUNTY=5000

# --- LoRA fine-tuning ---
# Base model to fine-tune (must be available on HuggingFace)
FINETUNE_BASE_MODEL=unsloth/Qwen2.5-Coder-7B-Instruct
# Training steps (500 ≈ 2-3h on RTX 5050 with 16k examples)
FINETUNE_MAX_STEPS=500
FINETUNE_BATCH_SIZE=2
FINETUNE_LORA_RANK=16

# --- Weights & Biases (free at wandb.ai) ---
WANDB_API_KEY=
WANDB_PROJECT=gh05t3
# WANDB_DISABLED=1  # uncomment to silence W&B

# --- Telegram mobile alerts (@BotFather to create bot, @userinfobot for chat ID) ---
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# --- Slack webhook (optional, alternative to Telegram) ---
SLACK_WEBHOOK_URL=

# --- Qdrant vector memory (docker run -p 6333:6333 qdrant/qdrant) ---
QDRANT_URL=http://localhost:6333

# --- Jira auto-issues (optional) ---
JIRA_URL=
JIRA_EMAIL=
JIRA_API_TOKEN=
JIRA_PROJECT_KEY=KAN

# --- Resource / scheduling tuning ---
# How many KAIROS self-improvement cycles to run each night (default 10)
KAIROS_CYCLES_PER_NIGHT=10
# Hour (0-23) for each nightly job — default: Anthropic timezone (ET)
NIGHTLY_HOUR_KAIROS=3
NIGHTLY_HOUR_AMP=4
NIGHTLY_HOUR_DREAM=2
NIGHTLY_HOUR_SUMMARY=23
# Max Memory Palace shards before oldest are pruned (default 5000)
MEMORY_MAX_SHARDS=5000

KILLSWITCH_KEY_HASH=
GH05T3_SECRET=sovereign-ghost-mesh-key-2025

MEMORY_DB_PATH=$APP\backend\memory\palace.db
SAGE_ELITE_THRESHOLD=0.90

# --- Peer mesh (single instance for now, add PEER_URLS when adding more machines) ---
INSTANCE_LABEL=TatorTot
INSTANCE_ROLE=primary
INSTANCE_URL=http://${LAN_IP}:8001
PEER_URLS=
SYNC_INTERVAL=300
"@
    Write-Host "Created $envPath" -ForegroundColor Yellow
} else {
    Write-Host "Existing $envPath kept (your keys are safe)." -ForegroundColor Gray
}

# ---- Frontend .env.local — bakes LAN IP so Android can reach backend ----
# Always rewritten so it stays in sync with the current LAN IP.
Set-Content "$APP\frontend\.env.local" @"
REACT_APP_BACKEND_URL=http://${LAN_IP}:8001
REACT_APP_GW3_URL=http://${LAN_IP}:8002
"@
Write-Host "Frontend will use backend at http://${LAN_IP}:8001" -ForegroundColor Cyan

# ---- Backend venv (delete first so a locked/stale venv never blocks pip) ----
Write-Host "Creating Python venv..." -ForegroundColor Cyan
Push-Location "$APP\backend"
if (Test-Path ".venv") {
    Write-Host "Removing old venv..." -ForegroundColor Cyan
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

# ---- LoRA fine-tuning deps (GPU — skip gracefully if CUDA not available) ----
Write-Host "Installing GPU training deps (unsloth + trl)..." -ForegroundColor Cyan
try {
    .\.venv\Scripts\pip install "unsloth[cu124]" trl datasets accelerate --quiet
    Write-Host "  GPU training deps installed." -ForegroundColor Green
} catch {
    Write-Host "  GPU training deps failed (no CUDA or wrong version) — fine-tuning disabled." -ForegroundColor Yellow
    Write-Host "  To enable: pip install 'unsloth[cu124]' trl datasets accelerate" -ForegroundColor Yellow
}

# ---- W&B + Qdrant (optional, both silently skipped if not installed) ----
try {
    .\.venv\Scripts\pip install wandb qdrant-client prometheus-client --quiet
    Write-Host "  W&B + Qdrant + Prometheus installed." -ForegroundColor Green
} catch {
    Write-Host "  Optional metrics deps skipped." -ForegroundColor Gray
}
Pop-Location

# ---- Frontend build (LAN IP baked into JS bundle) ----
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
Write-Host "  Start GH05T3:" -ForegroundColor Green
Write-Host "    cd `"$APP`"" -ForegroundColor White
Write-Host "    .\run.bat" -ForegroundColor White
Write-Host ""
Write-Host "  Dashboard (this PC):  http://localhost:3210" -ForegroundColor Green
Write-Host "  Dashboard (Android):  http://${LAN_IP}:3210" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Keys: open LLM Config panel in dashboard after first boot." -ForegroundColor Yellow
Write-Host "  Free keys:  https://console.groq.com  |  https://aistudio.google.com/app/apikey" -ForegroundColor Yellow
