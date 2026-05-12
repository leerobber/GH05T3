#!/data/data/com.termux/files/usr/bin/bash
# GH05T3 / Avery — Termux Node Setup
# Installs Claude Code + TIA companion node on Android (aarch64)
# Run once from Termux: bash termux_setup.sh

set -e

echo "=== GH05T3 Termux Node Setup ==="

# Architecture check
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "ERROR: Requires aarch64 (64-bit ARM). Detected: $ARCH"
    exit 1
fi

# 1. Packages
echo "==> Updating packages..."
pkg update -y && pkg upgrade -y
pkg install -y nodejs git nano openssh ripgrep tmux

# Node.js version check (v24 hangs on Termux)
NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
echo "Node.js v$NODE_VERSION detected"
if [ "$NODE_VERSION" -eq 24 ]; then
    echo "WARNING: v24 may hang — run 'pkg upgrade nodejs' to get v25+"
fi

# 2. Claude Code (pinned — native binary incompatible with Bionic libc)
echo "==> Installing Claude Code v2.1.112..."
npm install -g @anthropic-ai/claude-code@2.1.112

# Symlink ripgrep so Claude Code can find it
RG_SRC="$PREFIX/bin/rg"
RG_DST="$(npm root -g)/@anthropic-ai/claude-code/vendor/ripgrep"
if [ -f "$RG_SRC" ] && [ ! -f "$RG_DST" ]; then
    ln -s "$RG_SRC" "$RG_DST" 2>/dev/null || true
fi

# 3. Environment
echo "==> Writing ~/.bashrc config..."
touch ~/.bashrc

# Remove any previous GH05T3 block to avoid duplication
sed -i '/# === GH05T3 Termux ===/,/# === END GH05T3 Termux ===/d' ~/.bashrc

cat >> ~/.bashrc << 'ENVEOF'

# === GH05T3 Termux ===
export CLAUDE_CODE_TMPDIR="$TMPDIR"
export DISABLE_AUTOUPDATER=1
export DISABLE_UPDATES=1
alias claude='node $(npm root -g)/@anthropic-ai/claude-code/cli.js'

# GH05T3 TatorTot connection
export TATORTOT_IP="100.94.227.81"
export TATORTOT_USER="leer4"
alias tator='ssh ${TATORTOT_USER}@${TATORTOT_IP}'
alias tator-claude='ssh ${TATORTOT_USER}@${TATORTOT_IP} -t "tmux attach -t claude-desktop || tmux new -s claude-desktop"'
alias tator-gh05t3='ssh ${TATORTOT_USER}@${TATORTOT_IP} -t "cd /home/user/GH05T3 && tmux attach -t gh05t3 || tmux new -s gh05t3"'

# GH05T3 gateway (set if running locally via companion agent)
export GH05T3_GATEWAY="http://localhost:8002"
# === END GH05T3 Termux ===
ENVEOF

source ~/.bashrc

# 4. Claude config directory + context files
echo "==> Setting up Claude context files..."
mkdir -p ~/.claude ~/claude-skills/personal-context ~/Projects/GH05T3

cat > ~/.claude/settings.json << 'SETTINGS'
{
  "model": "claude-sonnet-4-6",
  "autoUpdater": {
    "disabled": true
  },
  "customInstructions": "Load context from ~/.claude/about-me.md before responding. Be direct, no fluff, technical depth preferred. This is a mobile Termux node for the GH05T3 / Avery system.",
  "env": {
    "CLAUDE_CODE_TMPDIR": "$TMPDIR"
  }
}
SETTINGS

cat > ~/.claude/about-me.md << 'BRAIN'
# About Me — GH05T3 / Avery Mobile Node

## Identity
- Builder: Rob Lee (tatortot / leer4)
- Startup: Avery — autonomous AI workforce
- Engine: GH05T3 sovereign AI system

## Infrastructure
- Desktop (TatorTot): Lenovo LOQ 15, RTX 5050 dGPU, Ryzen 7, Radeon 780M
  - Tailscale: 100.94.227.81 (hostname: tail1457e2.ts.net)
  - SSH: leer4@100.94.227.81
  - GH05T3 gateway: http://localhost:8002 (when local)
- Mobile (TIA): Android Termux node, this device
  - Ollama models: cogito:latest, llama3.2:3b
  - OpenRouter: free-tier fallback

## Agent Team (Avery's crew)
- Avery — Founder & Chief Intelligence (GH05T3)
- Iris Chen / ORACLE — Chief Research Officer
- Marcus Reid / FORGE — CTO
- Zoe Nakamura / CODEX — VP Engineering
- Viktor Steele / SENTINEL — CSO
- Kai Okafor / NEXUS — COO

## Repo
- GitHub: leerobber/GH05T3
- Branch for active work: claude/fix-multi-gpu-training-2WHKH
- Jira: KAN project (cloudId: dc17bc11-27cc-4c0b-8172-fc36c3f6c08c)

## Communication Style
- Direct, no fluff
- Technical depth, assume expert level
- Code over explanations
- Production-ready over tutorials
BRAIN

cat > ~/.claude/my-strategy.md << 'STRATEGY'
# Current Strategy

## Active Work
- GH05T3 fine-tuning: v32 running on Kaggle (Qwen2.5-Coder-3B + LoRA)
- Inference server: gh05t3_inference.py wired into ghost_llm.py
- Stripe integration: live, /stripe/webhook endpoint active
- Avery persona + agent team: personas.py committed

## Mobile Workflow Priority
1. Heavy work → SSH to TatorTot: tator-gh05t3
2. Light edits → Claude Code local (pinned v2.1.112)
3. Offline inference → TIA + Ollama

## No-Go
- Tutorial code
- Manual git workflows
- Redundant explanations
STRATEGY

# 5. Keyboard (extra keys for terminal use)
mkdir -p ~/.termux
cat > ~/.termux/termux.properties << 'KEYS'
extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','LEFT','DOWN','RIGHT','PGDN']]
KEYS

# 6. Storage access
echo "==> Requesting storage access..."
termux-setup-storage 2>/dev/null || echo "(storage access dialog — grant if prompted)"

# 7. Smoke test
echo "==> Testing Claude Code..."
node "$(npm root -g)/@anthropic-ai/claude-code/cli.js" --version

# 8. Battery optimization reminder
echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT — prevent Android from killing Termux:"
echo "  Settings → Apps → Termux → Battery → Unrestricted"
echo ""
echo "Quick commands:"
echo "  claude              — Claude Code (Termux, pinned)"
echo "  tator               — SSH into TatorTot"
echo "  tator-claude        — TatorTot + Claude Code in tmux"
echo "  tator-gh05t3        — TatorTot + GH05T3 session in tmux"
echo ""
echo "Context files to edit:"
echo "  ~/.claude/about-me.md       — personal context"
echo "  ~/.claude/my-strategy.md    — current focus"
echo ""
echo "Reload shell: source ~/.bashrc"
