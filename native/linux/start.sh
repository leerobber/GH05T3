#!/usr/bin/env bash
# GH05T3 manual launcher (no systemd).
# Run from repo root: bash native/linux/start.sh
set -euo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND="$APP/backend"
FRONTEND="$APP/frontend"
MONGO_DATA="$APP/mongo-data"
LOGS="$APP/logs"
PYBIN="$BACKEND/.venv/bin"

mkdir -p "$MONGO_DATA" "$LOGS" "$BACKEND/memory" "$BACKEND/evolution"

cleanup() {
    echo "Stopping GH05T3..."
    kill "$MONGO_PID" "$BACKEND_PID" "$GATEWAY_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting MongoDB..."
mongod \
  --dbpath "$MONGO_DATA" \
  --bind_ip 127.0.0.1 \
  --port 27017 \
  --logpath "$LOGS/mongod.log" \
  --fork
MONGO_PID=$!

# Wait for mongod to be ready
for i in $(seq 1 10); do
    mongosh --quiet --eval "db.runCommand({ping:1})" mongodb://127.0.0.1:27017 &>/dev/null && break
    echo "  waiting for MongoDB ($i/10)..."
    sleep 2
done

echo "Starting backend :8001..."
cd "$BACKEND"
"$PYBIN/uvicorn" server:app --host 0.0.0.0 --port 8001 \
    >> "$LOGS/backend.log" 2>&1 &
BACKEND_PID=$!

echo "Starting gateway :8002..."
"$PYBIN/uvicorn" gateway_v3:app --host 0.0.0.0 --port 8002 \
    >> "$LOGS/gateway.log" 2>&1 &
GATEWAY_PID=$!

echo "Starting frontend :3210..."
"$PYBIN/python" -m http.server 3210 --directory "$FRONTEND/build" \
    >> "$LOGS/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "GH05T3 running:"
echo "  Backend:  http://0.0.0.0:8001"
echo "  Gateway:  http://0.0.0.0:8002"
echo "  Frontend: http://0.0.0.0:3210"
echo ""
echo "Logs: $LOGS/"
echo "Ctrl+C to stop."
wait
