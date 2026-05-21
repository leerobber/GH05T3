#!/bin/bash
# HF_TOKEN must be set in environment or backend/.env before running
if [ -z "$HF_TOKEN" ] && [ -f "$(dirname "$0")/backend/.env" ]; then
    export HF_TOKEN=$(grep '^HF_TOKEN=' "$(dirname "$0")/backend/.env" | cut -d= -f2-)
fi
if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: HF_TOKEN not set. Add HF_TOKEN=hf_... to backend/.env or export it first."
    exit 1
fi
pkill -f train_sovereign_sft.py 2>/dev/null
sleep 2
cd /workspace
nohup python train_sovereign_sft.py --mode sft --agent avery > train.log 2>&1 &
echo "Training started PID: $!"
tail -5 train.log
