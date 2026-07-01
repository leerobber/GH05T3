# gh05t3_train/log_analyzer.py

import json
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("logs/gh05t3.log")

def load_logs():
    if not LOG_FILE.exists():
        print("No logs found.")
        return []

    events = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                # Extract JSON payload after the last '|'
                payload = line.split("|", 3)[-1].strip()
                data = json.loads(payload)
                events.append(data)
            except:
                pass
    return events

def summarize(events):
    summary = {
        "ingestion_runs": 0,
        "total_docs_seen": 0,
        "training_runs": 0,
        "epochs_completed": 0,
        "batches_logged": 0,
        "min_loss": float("inf"),
        "max_loss": float("-inf"),
        "chat_sessions": 0,
        "prompts": 0,
        "responses": 0,
    }

    for e in events:
        event = e.get("event", "")

        if event == "ingestion_complete":
            summary["ingestion_runs"] += 1
            summary["total_docs_seen"] += e["data"].get("usable_samples", 0)

        elif event == "train_start":
            summary["training_runs"] += 1

        elif event == "train_epoch_complete":
            summary["epochs_completed"] += 1

        elif event == "train_batch":
            summary["batches_logged"] += 1
            loss = e["data"].get("loss", None)
            if loss is not None:
                summary["min_loss"] = min(summary["min_loss"], loss)
                summary["max_loss"] = max(summary["max_loss"], loss)

        elif event == "chat_prompt":
            summary["prompts"] += 1

        elif event == "chat_response":
            summary["responses"] += 1

        elif event == "chat_exit":
            summary["chat_sessions"] += 1

    return summary

def print_summary(summary):
    print("\n=== GH05T3 LOG ANALYSIS REPORT ===\n")

    print(f"Ingestion Runs:       {summary['ingestion_runs']}")
    print(f"Total Docs Seen:      {summary['total_docs_seen']}")
    print(f"Training Runs:        {summary['training_runs']}")
    print(f"Epochs Completed:     {summary['epochs_completed']}")
    print(f"Batches Logged:       {summary['batches_logged']}")

    if summary["batches_logged"] > 0:
        print(f"Min Loss:             {summary['min_loss']:.4f}")
        print(f"Max Loss:             {summary['max_loss']:.4f}")

    print(f"Chat Sessions:        {summary['chat_sessions']}")
    print(f"Prompts Logged:       {summary['prompts']}")
    print(f"Responses Logged:     {summary['responses']}")

    print("\n=== END OF REPORT ===\n")

def main():
    events = load_logs()
    if not events:
        print("No events found.")
        return

    summary = summarize(events)
    print_summary(summary)

if __name__ == "__main__":
    main()
