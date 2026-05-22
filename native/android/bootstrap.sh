#!/data/data/com.termux/files/usr/bin/bash
# GH05T3 Termux Bootstrap
# Paste this entire file into Termux, or run:
#   pkg install wget -y && wget http://100.94.227.81:8002/install/android -O setup.sh && bash setup.sh
#
# If TatorTot is not running, paste and run this file directly.

set -e
ARCH=$(uname -m)
[ "$ARCH" = "aarch64" ] || { echo "Need aarch64, got $ARCH"; exit 1; }

echo "=== GH05T3 Termux Bootstrap ==="

pkg update -y && pkg upgrade -y
pkg install -y nodejs git nano openssh ripgrep tmux wget

NODE_V=$(node --version | cut -dv -f2 | cut -d. -f1)
[ "$NODE_V" -eq 24 ] && echo "WARNING: Node v24 may hang — run: pkg upgrade nodejs"

npm install -g @anthropic-ai/claude-code@2.1.112

RG_DST="$(npm root -g)/@anthropic-ai/claude-code/vendor/ripgrep"
[ -f "$PREFIX/bin/rg" ] && [ ! -f "$RG_DST" ] && ln -s "$PREFIX/bin/rg" "$RG_DST" 2>/dev/null || true

sed -i '/# === GH05T3 Termux ===/,/# === END GH05T3 Termux ===/d' ~/.bashrc
cat >> ~/.bashrc << 'ENV'

# === GH05T3 Termux ===
export CLAUDE_CODE_TMPDIR="$TMPDIR"
export DISABLE_AUTOUPDATER=1
export DISABLE_UPDATES=1
alias claude='node $(npm root -g)/@anthropic-ai/claude-code/cli.js'
export TATORTOT_IP="100.94.227.81"
export TATORTOT_USER="leer4"
alias tator='ssh ${TATORTOT_USER}@${TATORTOT_IP}'
alias tator-claude='ssh ${TATORTOT_USER}@${TATORTOT_IP} -t "tmux attach -t claude-desktop || tmux new -s claude-desktop"'
alias tator-gh05t3='ssh ${TATORTOT_USER}@${TATORTOT_IP} -t "cd /home/user/GH05T3 && tmux attach -t gh05t3 || tmux new -s gh05t3"'
export GH05T3_GATEWAY="http://100.94.227.81:8002"
# === END GH05T3 Termux ===
ENV

mkdir -p ~/.claude ~/Projects/GH05T3

cat > ~/.claude/settings.json << 'S'
{
  "model": "claude-sonnet-4-6",
  "autoUpdater": {"disabled": true},
  "customInstructions": "Context: GH05T3/Avery startup. Mobile Termux node. Direct, technical, no fluff. Load ~/.claude/about-me.md.",
  "env": {"CLAUDE_CODE_TMPDIR": "$TMPDIR"}
}
S

cat > ~/.claude/about-me.md << 'B'
# GH05T3 / Avery — Mobile Node

## Identity
Rob Lee (tatortot / leer4) — building Avery (GH05T3 startup)

## Infrastructure
- TatorTot desktop: 100.94.227.81 (Tailscale), user: leer4
- GH05T3 gateway: http://100.94.227.81:8002
- GitHub: leerobber/GH05T3

## Agent team
Avery/GH05T3, Iris/ORACLE, Marcus/FORGE, Zoe/CODEX, Viktor/SENTINEL, Kai/NEXUS

## Style
Direct. Technical depth. Code > explanations. Production-ready.
B

mkdir -p ~/.termux
cat > ~/.termux/termux.properties << 'K'
extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','LEFT','DOWN','RIGHT','PGDN']]
K

termux-setup-storage 2>/dev/null || true
termux-reload-settings 2>/dev/null || true

node "$(npm root -g)/@anthropic-ai/claude-code/cli.js" --version

echo ""
echo "=== Done ==="
echo "Reload shell: source ~/.bashrc"
echo ""
echo "Commands:"
echo "  claude          — Claude Code"
echo "  tator           — SSH to TatorTot"
echo "  tator-gh05t3    — TatorTot GH05T3 tmux session"
echo ""
echo "Battery: Settings → Apps → Termux → Battery → Unrestricted"
