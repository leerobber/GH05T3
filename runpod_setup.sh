#!/bin/bash
# Run this in the RunPod terminal to start avery training
# Usage: bash runpod_setup.sh <YOUR_HF_TOKEN>

HF_TOKEN=${1:-$HF_TOKEN}

if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: Pass your HF token: bash runpod_setup.sh hf_xxxx"
    exit 1
fi

# Copy training script if not already present
if [ ! -f runpod_train.py ]; then
    echo "Downloading training script..."
    pip install -q huggingface_hub
    python -c "
from huggingface_hub import hf_hub_download
# Script is embedded below — paste it directly
"
fi

# Run training
python runpod_train.py \
    --hf_token "$HF_TOKEN" \
    --base_model "Qwen/Qwen2.5-3B-Instruct" \
    --hf_dataset "tastytator/sovereign-economy" \
    --hf_repo_out "tastytator/avery-sovereign-lora" \
    --output_dir "/workspace/sovereign-lora" \
    --epochs 1 \
    --max_seq 2048 \
    --batch_size 2 \
    --grad_acc 4

echo "Training complete. LoRA pushed to HuggingFace."
