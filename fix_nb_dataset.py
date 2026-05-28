"""
Rewrites Cell 6 (dataset loading) with a clean, bulletproof version
for avery + economy data. Replaces the injected version that may have
had concatenation column mismatch issues.
"""
import json
from pathlib import Path

nb_path = Path('C:/Users/leer4/GH05T3/kaggle_train.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))

# Find cell 6 (dataset cell — has try_load and assert)
target_idx = None
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'try_load' in src and 'assert ds is not None' in src:
        target_idx = i
        break

assert target_idx is not None, "Could not find dataset cell"
print(f"Found dataset cell at index {target_idx}")

NEW_DATASET_CELL = r"""# ── 5. Load dataset ───────────────────────────────────────────────────────────

from datasets import load_dataset

def try_load(split, config=None):
    kwargs = {'split': split, 'token': HF_TOKEN}
    if config:
        kwargs['name'] = config
    try:
        ds = load_dataset(HF_DATASET, **kwargs)
        print(f'  Loaded {config}/{split}: {len(ds)} rows  cols={ds.column_names}')
        return ds
    except Exception as e:
        print(f'  {config}/{split} not available: {type(e).__name__}: {e}')
        return None

ds = None
final_mode = MODE

# ── Specialist agents (not avery) ────────────────────────────────────────────
if AGENT not in ('avery', 'all'):
    ds = try_load('train', config='agents')
    if ds is not None:
        agent_filter = cfg.get('agent_filter', AGENT)
        ds = ds.filter(lambda row: row.get('agent', '') == agent_filter)
        print(f'  Filtered to agent={agent_filter}: {len(ds)} rows')
        if len(ds) < 5:
            print(f'  WARNING: Only {len(ds)} rows — run agents_bootstrap.py first!')
            ds = None

elif AGENT == 'all':
    ds = try_load('train', config='agents')

# ── Avery: load economy simulation data (108K records) ───────────────────────
if AGENT == 'avery':
    print('\n  Loading economy simulation data for Avery...')
    eco_raw = try_load('train', config='economy')
    if eco_raw is not None:
        # Normalize messages format -> instruction/response
        def _eco_normalize(row):
            msgs = row.get('messages', [])
            users = [m['content'] for m in msgs if m.get('role') == 'user']
            astts = [m['content'] for m in msgs if m.get('role') == 'assistant']
            inst = users[0].strip() if users else ''
            resp = astts[-1].strip() if astts else ''
            return {'instruction': inst, 'response': resp}

        eco_ds = eco_raw.map(_eco_normalize, remove_columns=eco_raw.column_names)
        eco_ds = eco_ds.filter(lambda r: len(r['instruction']) > 20 and len(r['response']) > 20)
        print(f'  Economy records after filter: {len(eco_ds):,}')
        ds = eco_ds
        final_mode = 'sft'
    else:
        print('  WARNING: Economy dataset unavailable — falling back to SFT')

# ── Avery fallback: DPO splits ───────────────────────────────────────────────
if ds is None and MODE in ('orpo', 'dpo'):
    for split in cfg.get('hf_splits', ['bootstrap_dpo']):
        ds = try_load(split, config=cfg.get('hf_config', 'dpo'))
        if ds is not None and 'chosen' in ds.column_names:
            break
        ds = None

# ── Final SFT fallback ───────────────────────────────────────────────────────
if ds is None:
    print('  Trying SFT fallback split...')
    final_mode = 'sft'
    ds = try_load(cfg.get('sft_split', 'train'), config=cfg.get('sft_config', 'sft'))

assert ds is not None, 'No dataset found! Economy data unavailable and no fallback.'
MODE = final_mode
print(f'\nUsing mode={MODE}  agent={AGENT}  rows={len(ds)}')
"""

# Convert to list of lines (Jupyter format)
lines = NEW_DATASET_CELL.splitlines(keepends=True)
nb['cells'][target_idx]['source'] = lines

nb_path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding='utf-8')
print(f"Cell {target_idx} rewritten. Notebook saved.")

# Quick syntax check
import ast
try:
    ast.parse(NEW_DATASET_CELL)
    print("Syntax check: PASS")
except SyntaxError as e:
    print(f"Syntax check: FAIL - {e}")
