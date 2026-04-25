#!/usr/bin/env python3
"""
GH05T3 Client — Offline inference with Memory Palace
Run: python ghost_client.py
"""

import sys
import json
from pathlib import Path

try:
    import requests
    import numpy as np
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    import accelerate  # Required for device_map="cpu"
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

SNAPSHOT_PATH = Path("snapshot/metadata.json")
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"


def load_snapshot():
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    return {}


def download_model():
    print("👻 Downloading local model (Qwen2.5-1.5B, ~1.5GB)...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float32,
        device_map="cpu"
    )
    print("👻 Model loaded ✓")
    return model, tokenizer


def run_inference(model, tokenizer, query):
    prompt = f"Robert: {query}\nGH05T3:"
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=150, temperature=0.7, do_sample=True)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return response.split("GH05T3:")[-1].strip()


def main():
    snapshot = load_snapshot()
    palace = snapshot.get("memory_palace", {})
    vectors = snapshot.get("hcm_vectors", [0])[0]
    goals = snapshot.get("active_goals", 0)

    print("\n" + "=" * 60)
    print("👻 GH05T3 Client")
    print("=" * 60)

    if palace:
        total_memories = sum(palace.values())
        print(f"\nLoaded: {total_memories} memories, {vectors} HCM vectors")
    print("Mode: Local (offline inference)")
    print("\nCommands: status, goals, recall <term>, help, exit")
    print("Type your query and press Enter.\n")

    model, tokenizer = download_model()

    while True:
        try:
            query = input("> ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit"]:
                print("👻 Ghost offline.")
                break
            elif query.lower() == "help":
                print("Commands: status, goals, recall <term>, exit")
            elif query.lower() == "status":
                print(f"Mode: Local (offline)\nModel: Qwen2.5-1.5B\nMemories: {sum(palace.values()) if palace else 0}\nHCM Vectors: {vectors}")
            elif query.lower() == "goals":
                print(f"Active Goals: {goals} (Autotelic Engine)")
                print("  - Achieve 95% win rate in KAIROS simulations")
                print("  - Expand HCM to 200 vectors")
                print("  - Deploy GhostVeil timing randomization")
                print(f"  ... ({max(0, goals - 3)} more)")
            elif query.lower().startswith("recall "):
                term = query[7:]
                print(f"Searching Memory Palace for: '{term}'")
                print(f"  [Identity: {palace.get('Identity', 0)} entries]")
                print(f"  [Knowledge: {palace.get('Knowledge', 0)} entries]")
                print("  (Full vector search available when HCM is wired in)")
            else:
                print("👻 Thinking...")
                response = run_inference(model, tokenizer, query)
                print(response)
        except KeyboardInterrupt:
            print("\n👻 Ghost offline.")
            break


if __name__ == "__main__":
    main()
