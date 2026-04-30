#!/usr/bin/env bash
# GH05T3 Linux Installer — Cloud / Headless Server
# Run once as root or a sudo-capable user from inside the repo:
#   cd /opt/gh05t3/native/linux
#   bash install.sh
#
# Installs: Python 3.11, MongoDB 7, Node 20, Yarn
# Creates systemd services: gh05t3-mongo, gh05t3-backend, gh05t3-gateway, gh05t3-frontend
# Works on: Ubuntu 22.04+, Debian 12+, Rocky/Alma 9+

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$(cd "$HERE/../.." && pwd)"          # repo root
BACKEND="$APP/backend"
FRONTEND="$APP/frontend"
MONGO_DATA="$APP/mongo-data"

echo "============================================"
echo "  GH05T3 Linux Installer"
echo "  App root: $APP"
echo "============================================"

# ---- detect OS ---------------------------------------------------------------
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO="${ID:-unknown}"
else
    DISTRO="unknown"
fi

# ---- helper ------------------------------------------------------------------
need() { command -v "$1" &>/dev/null; }
apt_install() { sudo apt-get install -y --no-install-recommends "$@"; }
dnf_install() { sudo dnf install -y "$@"; }

# ---- Python 3.11 -------------------------------------------------------------
if ! need python3.11; then
    echo ">>> Installing Python 3.11..."
    case "$DISTRO" in
        ubuntu|debian|pop|linuxmint)
            sudo apt-get update -qq
            apt_install software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
            sudo apt-get update -qq
            apt_install python3.11 python3.11-venv python3.11-dev
            ;;
        rhel|centos|rocky|almalinux|fedora)
            dnf_install python3.11 python3.11-devel
            ;;
        *)
            echo "WARN: unknown distro '$DISTRO', assuming python3.11 available"
            ;;
    esac
fi
PYTHON="$(command -v python3.11)"
echo "Python: $PYTHON ($($PYTHON --version))"

# ---- Node 20 + Yarn ----------------------------------------------------------
if ! need node; then
    echo ">>> Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    apt_install nodejs 2>/dev/null || dnf_install nodejs 2>/dev/null || true
fi
if ! need yarn; then
    echo ">>> Installing Yarn..."
    sudo npm install -g yarn
fi

# ---- MongoDB 7 ---------------------------------------------------------------
if ! need mongod; then
    echo ">>> Installing MongoDB 7..."
    case "$DISTRO" in
        ubuntu|debian|pop|linuxmint)
            curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc \
              | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
            echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" \
              | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
            sudo apt-get update -qq
            apt_install mongodb-org
            ;;
        rhel|centos|rocky|almalinux|fedora)
            cat <<'MREPO' | sudo tee /etc/yum.repos.d/mongodb-org-7.0.repo
[mongodb-org-7.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-7.0.asc
MREPO
            dnf_install mongodb-org
            ;;
        *)
            echo "WARN: cannot auto-install MongoDB on '$DISTRO'. Install manually."
            ;;
    esac
fi

# ---- Runtime dirs ------------------------------------------------------------
mkdir -p "$MONGO_DATA" "$BACKEND/memory" "$BACKEND/evolution" "$APP/logs"

# ---- Backend .env (only create if missing) -----------------------------------
ENV_PATH="$BACKEND/.env"
if [ ! -f "$ENV_PATH" ]; then
    HOSTNAME_VAL="$(hostname -f 2>/dev/null || hostname)"
    cat > "$ENV_PATH" <<ENVEOF
# GH05T3 backend — Linux instance
# Edit the values below, then restart the services.

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

GITHUB_PAT=
GITHUB_REPO=leerobber/GH05T3
GITHUB_BRANCH=main
GH05T3_REPO_PATH=$APP

GATEWAY_PORT=8002
GATEWAY_URL=http://localhost:8002

VLLM_PRIMARY_URL=http://localhost:8010
LLAMA_VERIFIER_URL=http://localhost:8011
LLAMA_FALLBACK_URL=http://localhost:8012

# --- Ollama GPU protection ---
OLLAMA_MAX_CONCURRENT=1
OLLAMA_KEEP_ALIVE=0
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_PREDICT=512

KILLSWITCH_KEY_HASH=
GH05T3_SECRET=sovereign-ghost-mesh-key-2025

MEMORY_DB_PATH=$BACKEND/memory/palace.db
SAGE_ELITE_THRESHOLD=0.90

# --- Multi-instance peer mesh ---
INSTANCE_LABEL=$HOSTNAME_VAL
INSTANCE_ROLE=peer
# Set INSTANCE_URL to the URL other nodes use to reach THIS machine:
INSTANCE_URL=http://$HOSTNAME_VAL:8001
# Comma-separated peer URLs (Tailscale hostnames recommended):
PEER_URLS=
SYNC_INTERVAL=300
ENVEOF
    echo ">>> Created $ENV_PATH — fill in API keys before starting."
fi

# ---- Frontend .env.local -----------------------------------------------------
cat > "$FRONTEND/.env.local" <<FEOF
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_GW3_URL=http://localhost:8002
FEOF

# ---- Python venv + deps ------------------------------------------------------
echo ">>> Setting up Python venv..."
cd "$BACKEND"
if [ -d ".venv" ]; then rm -rf .venv; fi
$PYTHON -m venv .venv
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

# ---- Frontend build ----------------------------------------------------------
echo ">>> Building frontend..."
cd "$FRONTEND"
yarn install --silent
yarn build

# ---- Systemd services --------------------------------------------------------
UNIT_DIR="/etc/systemd/system"
PYBIN="$BACKEND/.venv/bin"
USER="$(whoami)"

echo ">>> Installing systemd services..."

# MongoDB
cat <<SVC | sudo tee "$UNIT_DIR/gh05t3-mongo.service" > /dev/null
[Unit]
Description=GH05T3 MongoDB
After=network.target

[Service]
Type=forking
User=$USER
ExecStart=/usr/bin/mongod --dbpath $MONGO_DATA --bind_ip 127.0.0.1 --port 27017 --fork --logpath $APP/logs/mongod.log
ExecStop=/usr/bin/mongod --shutdown --dbpath $MONGO_DATA
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# Backend
cat <<SVC | sudo tee "$UNIT_DIR/gh05t3-backend.service" > /dev/null
[Unit]
Description=GH05T3 Backend (FastAPI :8001)
After=gh05t3-mongo.service
Requires=gh05t3-mongo.service

[Service]
User=$USER
WorkingDirectory=$BACKEND
Environment=PATH=$PYBIN:/usr/local/bin:/usr/bin:/bin
ExecStart=$PYBIN/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# Gateway v3
cat <<SVC | sudo tee "$UNIT_DIR/gh05t3-gateway.service" > /dev/null
[Unit]
Description=GH05T3 Gateway v3 (SwarmBus :8002)
After=gh05t3-mongo.service
Requires=gh05t3-mongo.service

[Service]
User=$USER
WorkingDirectory=$BACKEND
Environment=PATH=$PYBIN:/usr/local/bin:/usr/bin:/bin
ExecStart=$PYBIN/uvicorn gateway_v3:app --host 0.0.0.0 --port 8002
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# Frontend static server
cat <<SVC | sudo tee "$UNIT_DIR/gh05t3-frontend.service" > /dev/null
[Unit]
Description=GH05T3 Frontend (static :3210)
After=network.target

[Service]
User=$USER
ExecStart=$PYBIN/python -m http.server 3210 --directory $FRONTEND/build
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

sudo systemctl daemon-reload
sudo systemctl enable gh05t3-mongo gh05t3-backend gh05t3-gateway gh05t3-frontend

echo ""
echo "============================================"
echo "  Install complete."
echo ""
echo "  Edit: $ENV_PATH"
echo "  (Set ANTHROPIC_API_KEY, PEER_URLS, INSTANCE_URL)"
echo ""
echo "  Start:"
echo "    sudo systemctl start gh05t3-mongo gh05t3-backend gh05t3-gateway gh05t3-frontend"
echo ""
echo "  Or use start.sh for manual launch without systemd."
echo ""
echo "  Dashboard: http://localhost:3210"
echo "============================================"
