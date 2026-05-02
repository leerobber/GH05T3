#!/usr/bin/env python3
"""
GH05T3 Supervised Self-Training
Logs conversations and runs LoRA fine-tuning ONLY on Robert-approved exchanges.
Run: python tools/self_train.py --review     (approve/reject logged conversations)
     python tools/self_train.py --train       (fine-tune on approved data)
     python tools/self_train.py --status      (show training history)
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
CONV_LOG = REPO_ROOT / "history" / "sessions" / "conversations.jsonl"
APPROVED_DATA = REPO_ROOT / "history" / "sessions" / "approved_training_data.jsonl"
TRAIN_LOG = REPO_ROOT / "history" / "sessions" / "training_log.jsonl"
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
LORA_OUTPUT = REPO_ROOT / "models" / "ghost_lora"


def log_conversation(user_msg: str, assistant_msg: str):
    """Called by ghost_client.py after each successful exchange."""
    CONV_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "pending_review",
        "messages": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg},
        ],
    }
    with open(CONV_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_pending() -> list:
    if not CONV_LOG.exists():
        return []
    entries = []
    with open(CONV_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("status") == "pending_review":
                entries.append(entry)
    return entries


def review_conversations():
    pending = load_pending()
    if not pending:
        print("No conversations pending review.")
        return

    print(f"\n{'='*60}")
    print(f"GH05T3 TRAINING REVIEW — {len(pending)} conversation(s) pending")
    print("For each exchange: [a]pprove, [r]eject, [s]kip, [q]uit")
    print(f"{'='*60}\n")

    approved_count = 0
    rejected_count = 0
    updated_lines = []

    all_lines = []
    with open(CONV_LOG, encoding="utf-8") as f:
        all_lines = f.readlines()

    for i, entry in enumerate(pending):
        msgs = entry["messages"]
        user_msg = msgs[0]["content"]
        assistant_msg = msgs[1]["content"]

        print(f"─── Exchange {i+1}/{len(pending)} ───")
        print(f"Robert: {user_msg[:200]}{'...' if len(user_msg) > 200 else ''}")
        print(f"GH05T3: {assistant_msg[:200]}{'...' if len(assistant_msg) > 200 else ''}")
        print()

        choice = input("[a]pprove / [r]eject / [s]kip / [q]uit: ").strip().lower()
        if choice == "q":
            break
        elif choice == "a":
            entry["status"] = "approved"
            approved_count += 1
            with open(APPROVED_DATA, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            print("  ✅ Approved for training.\n")
        elif choice == "r":
            entry["status"] = "rejected"
            rejected_count += 1
            print("  ❌ Rejected.\n")
        else:
            print("  ⏭  Skipped.\n")

    # Rewrite conv log with updated statuses
    with open(CONV_LOG, "w", encoding="utf-8") as f:
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
            stored = json.loads(line)
            if stored.get("status") == "pending_review":
                for entry in pending:
                    if entry["timestamp"] == stored["timestamp"]:
                        stored = entry
                        break
            f.write(json.dumps(stored) + "\n")

    print(f"\nReview complete. Approved: {approved_count}, Rejected: {rejected_count}")
    if approved_count > 0:
        print(f"Run 'python tools/self_train.py --train' to fine-tune on approved data.")


def run_training():
    if not APPROVED_DATA.exists():
        print("No approved training data found. Run --review first.")
        sys.exit(1)

    approved = []
    with open(APPROVED_DATA, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                approved.append(json.loads(line))

    if not approved:
        print("Approved data file is empty.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"GH05T3 SELF-TRAINING")
    print(f"Training samples: {len(approved)}")
    print(f"Base model: {MODEL_NAME}")
    print(f"Output: {LORA_OUTPUT.relative_to(REPO_ROOT)}")
    print(f"{'='*60}")
    print("\nThis will fine-tune GH05T3 using LoRA.")
    confirm = input("Proceed? [yes/no]: ").strip().lower()
    if confirm != "yes":
        print("Training cancelled.")
        sys.exit(0)

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model, TaskType
        import torch
        from torch.utils.data import Dataset
    except ImportError:
        print("❌ Missing dependencies for training.")
        print("Run: pip install peft trl")
        sys.exit(1)

    class ConversationDataset(Dataset):
        def __init__(self, data, tokenizer, max_length=512):
            self.samples = []
            identity = (REPO_ROOT / "core" / "identity.txt").read_text(encoding="utf-8")
            for entry in data:
                msgs = [{"role": "system", "content": identity}] + entry["messages"]
                text = tokenizer.apply_chat_template(msgs, tokenize=False)
                enc = tokenizer(text, truncation=True, max_length=max_length, return_tensors="pt")
                self.samples.append({k: v.squeeze(0) for k, v in enc.items()})

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            item = self.samples[idx]
            item["labels"] = item["input_ids"].clone()
            return item

    print("\n📥 Loading base model...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.float32, device_map="cpu")

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    dataset = ConversationDataset(approved, tokenizer)

    training_args = TrainingArguments(
        output_dir=str(LORA_OUTPUT),
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        save_steps=50,
        logging_steps=10,
        learning_rate=2e-4,
        fp16=False,
        report_to="none",
    )

    trainer = Trainer(model=model, args=training_args, train_dataset=dataset)
    print("\n🏋️ Training started...")
    trainer.train()
    model.save_pretrained(str(LORA_OUTPUT))
    tokenizer.save_pretrained(str(LORA_OUTPUT))

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "samples_used": len(approved),
        "lora_output": str(LORA_OUTPUT.relative_to(REPO_ROOT)),
        "base_model": MODEL_NAME,
    }
    TRAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAIN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Clear approved data so it's not trained on twice
    APPROVED_DATA.write_text("")
    print(f"\n✅ Training complete. LoRA adapter saved to {LORA_OUTPUT.relative_to(REPO_ROOT)}")
    print("Restart ghost_client.py to load the updated model.")


def show_status():
    print(f"\n{'='*60}")
    print("GH05T3 TRAINING STATUS")
    print(f"{'='*60}")

    pending = load_pending()
    print(f"Conversations pending review: {len(pending)}")

    approved_count = 0
    if APPROVED_DATA.exists():
        with open(APPROVED_DATA, encoding="utf-8") as f:
            approved_count = sum(1 for line in f if line.strip())
    print(f"Approved conversations ready to train: {approved_count}")

    if TRAIN_LOG.exists():
        runs = []
        with open(TRAIN_LOG, encoding="utf-8") as f:
            runs = [json.loads(l) for l in f if l.strip()]
        print(f"Training runs completed: {len(runs)}")
        if runs:
            last = runs[-1]
            print(f"Last run: {last['timestamp']} — {last['samples_used']} samples")
    else:
        print("Training runs completed: 0")

    lora_exists = LORA_OUTPUT.exists() and any(LORA_OUTPUT.iterdir())
    print(f"LoRA adapter present: {'Yes' if lora_exists else 'No'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if "--review" in sys.argv:
        review_conversations()
    elif "--train" in sys.argv:
        run_training()
    elif "--status" in sys.argv:
        show_status()
    else:
        print("Usage:")
        print("  python tools/self_train.py --review    Review conversations for training")
        print("  python tools/self_train.py --train     Fine-tune on approved data")
        print("  python tools/self_train.py --status    Show training history")
