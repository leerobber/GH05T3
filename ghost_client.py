#!/usr/bin/env python3
"""
GH05T3 Client — Offline inference with Memory Palace
Run: python ghost_client.py
"""

import sys
import json
import subprocess
from pathlib import Path

# Add tools/ to path so self_train can be imported
sys.path.insert(0, str(Path(__file__).parent / "tools"))

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
IDENTITY_PATH = Path("core/identity.txt")
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
LORA_PATH = Path("models/ghost_lora")

# Queries that must NEVER be answered with generated fiction.
# These require real data or a refusal.
GROUNDED_TRIGGERS = [
    "complete", "percent", "%", "eta", "timeline", "weeks", "days",
    "progress", "status of", "how far", "when will", "finish",
    "evolver", "analyst", "monitor", "sub-agent", "vector", "hcm",
    "elite language", "elite coding",
]


def load_snapshot():
    if SNAPSHOT_PATH.exists():
        with open(SNAPSHOT_PATH) as f:
            return json.load(f)
    return {}


def load_identity():
    if IDENTITY_PATH.exists():
        return IDENTITY_PATH.read_text(encoding="utf-8").strip()
    return ""


def get_real_project_state():
    """Return only facts that can be verified right now."""
    facts = []

    # Git commit count
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            facts.append(f"Git commits: {result.stdout.strip()}")
    except Exception:
        pass

    # File count
    py_files = list(Path(".").rglob("*.py"))
    facts.append(f"Python files in repo: {len(py_files)}")

    # Snapshot data (raw numbers only — not interpreted as progress)
    snap = load_snapshot()
    if snap:
        vectors = snap.get("hcm_vectors", [0])[0]
        memories = sum(snap.get("memory_palace", {}).values())
        facts.append(f"HCM vector count in snapshot: {vectors} (a stored number, not a live measurement)")
        facts.append(f"Memory palace entries in snapshot: {memories}")

    return "\n".join(facts) if facts else "No verifiable state available."


def is_fabrication_risk(query: str) -> bool:
    q = query.lower()
    return any(trigger in q for trigger in GROUNDED_TRIGGERS)


def download_model():
    print("👻 Loading base model (Qwen2.5-1.5B)...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float32,
        device_map="cpu"
    )

    # Load LoRA adapter if a training run has been approved and applied
    if LORA_PATH.exists() and any(LORA_PATH.iterdir()):
        try:
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, str(LORA_PATH))
            print("👻 LoRA adapter loaded ✓ (model has been self-trained)")
        except Exception as e:
            print(f"⚠️  LoRA load failed, using base model: {e}")
    else:
        print("👻 Base model loaded ✓ (no training runs yet)")

    return model, tokenizer


def run_inference(model, tokenizer, system_prompt: str, query: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt")
    outputs = model.generate(
        **inputs,
        max_new_tokens=200,
        temperature=0.7,
        do_sample=True,
    )
    full = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Strip the prompt portion — return only the model's reply
    if "assistant" in full.lower():
        return full.split("assistant")[-1].strip()
    return full[len(text):].strip()


def main():
    snapshot = load_snapshot()
    palace = snapshot.get("memory_palace", {})
    vectors = snapshot.get("hcm_vectors", [0])[0]
    goals = snapshot.get("active_goals", 0)

    identity = load_identity()
    if not identity:
        print("⚠️  Warning: identity.txt not found — running without system prompt.")

    print("\n" + "=" * 60)
    print("👻 GH05T3 Client")
    print("=" * 60)

    if palace:
        total_memories = sum(palace.values())
        print(f"\nLoaded: {total_memories} memories, {vectors} HCM vectors")
    print("Mode: Local (offline inference)")
    print("\nCommands: status, goals, recall <term>, state, help, exit")
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
                print("Commands: status, goals, recall <term>, state, exit")
                print("  state  — show only verified, real project data")

            elif query.lower() == "status":
                print(f"Mode: Local (offline)\nModel: Qwen2.5-1.5B\n"
                      f"Memories: {sum(palace.values()) if palace else 0}\n"
                      f"HCM Vectors (snapshot): {vectors}")

            elif query.lower() == "state":
                print("\n--- VERIFIED PROJECT STATE ---")
                print(get_real_project_state())
                print("--- END ---\n")

            elif query.lower() == "goals":
                print(f"Active Goals stored in snapshot: {goals}")
                print("(These are stored labels — not live agent activity.)")

            elif query.lower().startswith("recall "):
                term = query[7:]
                print(f"Searching Memory Palace for: '{term}'")
                print(f"  [Identity: {palace.get('Identity', 0)} entries]")
                print(f"  [Knowledge: {palace.get('Knowledge', 0)} entries]")
                print("  (Full vector search available when HCM is wired in)")

            else:
                # Hard block on fabrication-risk queries
                if is_fabrication_risk(query):
                    print(
                        "\n⛔ BLOCKED: That query asks for project status, progress, or ETA.\n"
                        "I am not allowed to generate that — I have no real data and I will not invent it.\n"
                        "Run 'state' to see verified facts, or ask Claude Code.\n"
                    )
                    continue

                print("👻 Thinking...")
                response = run_inference(model, tokenizer, identity, query)
                print(response)

                # Log for supervised training review
                try:
                    from self_train import log_conversation
                    log_conversation(query, response)
                except Exception:
                    pass

        except KeyboardInterrupt:
            print("\n👻 Ghost offline.")
            break


if __name__ == "__main__":
    main()
