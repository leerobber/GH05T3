#!/usr/bin/env bash
# GH05T3 DPO — Lightning AI Studio one-time setup
# Run once per new studio: bash backend/training/lightning_setup.sh
#
# Assumes:
#   - Lightning Studio with CUDA 12.x GPU (L4 or A10G recommended)
#   - Python 3.10+
#   - /teamspace/studios/this_studio exists (persistent storage)

set -euo pipefail

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  GH05T3 DPO — Lightning AI Studio Setup                 ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── GPU check ────────────────────────────────────────────────────────────────────────────
echo "── GPU ──"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || {
    echo "ERROR: nvidia-smi failed — no NVIDIA GPU detected."
    echo "In Lightning AI Studio: Compute > Change Instance > select L4 or A10G."
    exit 1
}
echo ""

# ── Python ─────────────────────────────────────────────────────────────────────────────
PYTHON="${PYTHON:-python3}"
PIP="$PYTHON -m pip"
echo "── Python: $($PYTHON --version 2>&1) ──"
echo ""

# ── PyTorch: detect or install ───────────────────────────────────────────────────────────
echo "── PyTorch check ──"
if $PYTHON -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" 2>/dev/null; then
    TORCH_VER=$($PYTHON -c "import torch; print(torch.__version__)")
    CUDA_VER=$($PYTHON  -c "import torch; print(torch.version.cuda)")
    echo "✓ PyTorch $TORCH_VER (CUDA $CUDA_VER) already installed — skipping"
else
    # Detect CUDA version from nvcc or nvidia-smi
    CUDA_TAG="cu121"
    if command -v nvcc &>/dev/null; then
        NVCC_VER=$(nvcc --version | grep -oP 'release \K[0-9]+\.[0-9]+' | head -1)
        MAJOR=$(echo "$NVCC_VER" | cut -d. -f1)
        MINOR=$(echo "$NVCC_VER" | cut -d. -f2)
        if   [[ "$MAJOR" == "12" && "$MINOR" -ge "4" ]]; then CUDA_TAG="cu124"
        elif [[ "$MAJOR" == "12" ]];                      then CUDA_TAG="cu121"
        elif [[ "$MAJOR" == "11" ]];                      then CUDA_TAG="cu118"
        fi
    fi
    echo "Installing PyTorch ($CUDA_TAG) ..."
    $PIP install --quiet torch torchvision \
        --index-url "https://download.pytorch.org/whl/${CUDA_TAG}"
    echo "✓ PyTorch installed ($CUDA_TAG)"
fi
echo ""

# ── DPO requirements ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="$SCRIPT_DIR/requirements-dpo.txt"

echo "── Installing DPO training deps ──"
if [[ -f "$REQ_FILE" ]]; then
    $PIP install --quiet -r "$REQ_FILE"
    echo "✓ requirements-dpo.txt installed"
else
    echo "requirements-dpo.txt not found at $REQ_FILE — installing inline ..."
    $PIP install --quiet \
        "transformers>=4.40.2" \
        "peft>=0.10.0" \
        "trl>=0.9.0" \
        "accelerate>=0.29.3" \
        "datasets>=2.19.0" \
        "huggingface_hub>=0.22.0" \
        "bitsandbytes>=0.43.0" \
        "safetensors>=0.4.0" \
        "sentencepiece>=0.1.99" \
        "einops>=0.6.1" \
        "scipy>=1.11.0" \
        "packaging>=23.0"
    echo "✓ inline deps installed"
fi
echo ""

# ── HuggingFace cache on persistent /teamspace storage ────────────────────────────
TEAMSPACE="/teamspace/studios/this_studio"
HF_CACHE="$TEAMSPACE/hf_cache"

echo "── HuggingFace cache ──"
if [[ -d "$TEAMSPACE" ]]; then
    mkdir -p "$HF_CACHE/datasets" "$HF_CACHE/transformers"
    export HF_HOME="$HF_CACHE"
    export HF_DATASETS_CACHE="$HF_CACHE/datasets"
    export TRANSFORMERS_CACHE="$HF_CACHE/transformers"
    PROFILE="$HOME/.bashrc"
    # Only write if not already present
    if ! grep -q "GH05T3_DPO_HF_CACHE" "$PROFILE" 2>/dev/null; then
        cat >> "$PROFILE" <<EOF

# GH05T3 DPO — HuggingFace cache on persistent Lightning storage
# Added by lightning_setup.sh
export HF_HOME="$HF_CACHE"
export HF_DATASETS_CACHE="$HF_CACHE/datasets"
export TRANSFORMERS_CACHE="$HF_CACHE/transformers"
# GH05T3_DPO_HF_CACHE (marker — do not remove this comment)
EOF
    fi
    echo "✓ HF cache → $HF_CACHE (persists across studio restarts)"
else
    echo "⚠  Not in Lightning Studio — using default HF cache (~/.cache/huggingface)"
fi
echo ""

# ── verify all imports ─────────────────────────────────────────────────────────────────────
echo "── Verifying imports ──"
$PYTHON - <<'PYEOF'
import sys

failed = []

def check(name, import_name=None):
    try:
        mod = __import__(import_name or name)
        ver = getattr(mod, "__version__", "?")
        print(f"  ✓ {name:<20} {ver}")
    except ImportError as e:
        print(f"  ✗ {name:<20} MISSING ({e})", file=sys.stderr)
        failed.append(name)

check("torch")
check("transformers")
check("peft")
check("trl")
check("datasets")
check("bitsandbytes")
check("accelerate")
check("safetensors")
check("sentencepiece")

import torch
print(f"  CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    p = torch.cuda.get_device_properties(0)
    print(f"  GPU:            {p.name} ({p.total_memory/1e9:.1f} GB, sm_{p.major}{p.minor})")
    if p.total_memory / 1e9 < 14:
        print("  WARNING: < 14 GB VRAM detected — DPO on 7B may OOM", file=sys.stderr)
        print("           Switch to L4 (24 GB) or A10G (24 GB)", file=sys.stderr)

if failed:
    print(f"\nFailed imports: {failed}", file=sys.stderr)
    sys.exit(1)
PYEOF
echo ""

# ── quick-start summary ─────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Setup complete! Commands:                              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  # 1. Smoke test — pipeline works end-to-end (< 5 min):"
echo "  python backend/training/ghost_trainer.py --smoke"
echo ""
echo "  # 2. Full DPO run (~2-3 h on L4, 300 steps):"
echo "  python backend/training/ghost_trainer.py"
echo ""
echo "  # 3. Custom run:"
echo "  python backend/training/ghost_trainer.py --steps 500 --beta 0.05 --lr 3e-6"
echo ""
echo "  # 4. Start from existing SFT adapter:"
echo "  python backend/training/ghost_trainer.py \\"
echo "    --adapter /teamspace/studios/this_studio/sft_adapter"
echo ""
echo "  # 5. Sync finished adapter to TatorTot (Tailscale):"
echo "  rsync -avz /teamspace/studios/this_studio/dpo_adapter/ \\"
echo "        leer4@100.94.227.81:~/gh05t3/backend/models/gh05t3_dpo_adapter/"
echo ""
echo "  # 6. Activate on TatorTot (backend/.env):"
echo "  LLM_PROVIDER=gh05t3"
echo "  GH05T3_ADAPTER_PATH=backend/models/gh05t3_dpo_adapter"
echo ""
