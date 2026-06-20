#!/usr/bin/env bash
# Detect active GH05T3 runtime and export GH05T3_RUNTIME for sovereign-core mesh probes.
# Usage: source scripts/mesh/select_runtime.sh   OR   eval "$(bash scripts/mesh/select_runtime.sh --export)"
set -euo pipefail

EXPORT=0
[[ "${1:-}" == "--export" ]] && EXPORT=1

WIN_HOST="${GH05T3_WINDOWS_HOST:-$(ip route 2>/dev/null | awk '/default/{print $3; exit}')}"
WIN_HOST="${WIN_HOST:-127.0.0.1}"

_port_up() {
  local host="$1" port="$2"
  timeout 1 bash -c "echo > /dev/tcp/${host}/${port}" 2>/dev/null
}

wsl_gw=0
wsl_sup=0
win_gw=0
win_sup=0

_port_up localhost 8002 && wsl_gw=1
_port_up localhost 8090 && wsl_sup=1
_port_up "$WIN_HOST" 8002 && win_gw=1
_port_up "$WIN_HOST" 8090 && win_sup=1

runtime=""
conflict=0

if [[ $wsl_gw -eq 1 && $win_gw -eq 1 ]]; then
  conflict=1
  runtime="wsl"
elif [[ $wsl_gw -eq 1 ]]; then
  runtime="wsl"
elif [[ $win_gw -eq 1 ]]; then
  runtime="windows"
else
  runtime="${GH05T3_RUNTIME:-wsl}"
fi

if [[ $EXPORT -eq 1 ]]; then
  echo "export GH05T3_RUNTIME=${runtime}"
  echo "export GH05T3_WINDOWS_HOST=${WIN_HOST}"
  [[ $conflict -eq 1 ]] && echo "export GH05T3_RUNTIME_CONFLICT=1"
  exit 0
fi

echo "GH05T3 runtime: ${runtime}"
echo "  WSL gateway :8002     $([[ $wsl_gw -eq 1 ]] && echo UP || echo down)"
echo "  WSL supervisor :8090  $([[ $wsl_sup -eq 1 ]] && echo UP || echo down)"
echo "  Windows gateway :8002 $([[ $win_gw -eq 1 ]] && echo UP @ $WIN_HOST || echo down)"
echo "  Windows supervisor    $([[ $win_sup -eq 1 ]] && echo UP @ $WIN_HOST || echo down)"

if [[ $conflict -eq 1 ]]; then
  echo ""
  echo "CONFLICT: both WSL and Windows hold port 8002. Stop one stack:"
  echo "  WSL:     bash scripts/wsl_stop.sh"
  echo "  Windows: python scripts/runtime/supervisor.py --stop"
  exit 1
fi

export GH05T3_RUNTIME="$runtime"
export GH05T3_WINDOWS_HOST="$WIN_HOST"