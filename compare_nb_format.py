import json
from pathlib import Path

# Compare our notebook metadata vs the working one
our_nb  = json.loads(Path('C:/Users/leer4/GH05T3/kaggle_train.ipynb').read_text(encoding='utf-8'))
good_nb = json.loads(Path('C:/Users/leer4/GH05T3/kaggle_pull_tmp2/sovereign-agent-training.ipynb').read_text(encoding='utf-8'))

print("=== OUR notebook top-level keys ===")
for k, v in our_nb.items():
    if k != 'cells':
        print(f"  {k}: {v}")

print("\n=== WORKING notebook top-level keys ===")
for k, v in good_nb.items():
    if k != 'cells':
        print(f"  {k}: {v}")

print("\n=== OUR cell[0] keys ===")
print(f"  {list(our_nb['cells'][0].keys())}")

print("\n=== WORKING cell[0] keys ===")
print(f"  {list(good_nb['cells'][0].keys())}")

print("\n=== Cell count ===")
print(f"  Ours   : {len(our_nb['cells'])} cells")
print(f"  Working: {len(good_nb['cells'])} cells")

# Check if our cells have id fields (required by nbformat 4.5+)
our_has_id = all('id' in c for c in our_nb['cells'])
good_has_id = all('id' in c for c in good_nb['cells'])
print(f"\n=== Cell IDs present ===")
print(f"  Ours   : {our_has_id}")
print(f"  Working: {good_has_id}")
