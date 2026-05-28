import json, re
from pathlib import Path

nb = json.loads(Path('C:/Users/leer4/GH05T3/kaggle_debug/sovereign-avery-3b-training.ipynb').read_text(encoding='utf-8'))
cells = nb.get('cells', [])

has_output = [c for c in cells if c.get('outputs')]
print(f'Total cells: {len(cells)}  |  Cells with output: {len(has_output)}')

for i, cell in enumerate(cells):
    outputs = cell.get('outputs', [])
    if not outputs:
        continue
    print(f'\n=== Cell {i} ===')
    for out in outputs:
        parts = out.get('text') or out.get('traceback') or [out.get('evalue', '')]
        if isinstance(parts, list):
            text = ''.join(parts)
        else:
            text = str(parts)
        text = re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', text)
        print(text[:3000])
