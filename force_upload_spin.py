"""Force-upload all current SPIN pairs to HuggingFace spin_business split."""
import json, os
from pathlib import Path

env_path = Path(__file__).parent / ".env"
hf_token = ""
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("HF_TOKEN="):
        hf_token = line.split("=", 1)[1].strip().strip("'\"")

if not hf_token:
    print("ERROR: HF_TOKEN not found in .env")
    raise SystemExit(1)

spin_file = Path(__file__).parent / "data" / "spin_dataset.jsonl"
rows = [json.loads(l) for l in spin_file.open(encoding="utf-8") if l.strip()]

examples = []
for row in rows:
    goal    = row.get("goal", "")
    chosen  = row.get("chosen", "")
    rejected = row.get("rejected", "")
    if not (goal and chosen):
        continue
    examples.append({
        "instruction": f"Business strategy goal: {goal}",
        "context":     f"Rejected approach: {rejected[:300]}" if rejected else "",
        "response":    chosen,
        "source":      "ghost_trainer_spin",
        "domain":      row.get("domain", "business"),
    })

print(f"Uploading {len(examples)} examples...")

from datasets import Dataset
ds = Dataset.from_list(examples)
ds.push_to_hub(
    "tastytator/sovereign-economy",
    split="spin_business",
    token=hf_token,
    private=False,
)

# Update state file
state_file = Path(__file__).parent / "data" / "continuous_state.json"
if state_file.exists():
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["last_upload_count"] = len(rows)
    state["spin_uploads"] = state.get("spin_uploads", 0) + 1
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"State updated: last_upload_count={len(rows)}, spin_uploads={state['spin_uploads']}")

print(f"Done! {len(examples)} rows live at tastytator/sovereign-economy (spin_business split).")
