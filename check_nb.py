import json, re
from pathlib import Path

nb = json.loads(Path('C:/Users/leer4/GH05T3/kaggle_train.ipynb').read_text(encoding='utf-8'))
cells = nb.get('cells', [])
print(f'Total cells: {len(cells)}')
problems = []
for i, cell in enumerate(cells):
    src = cell.get('source', '')
    src_type = type(src).__name__
    if isinstance(src, str):
        preview = src[:80].replace('\n', ' ')
        print(f'  Cell {i} BAD (string not list): {preview}')
        problems.append(i)
    else:
        joined = ''.join(src)
        preview = joined[:80].replace('\n', ' ')
        print(f'  Cell {i} OK  (list, {len(src)} items): {preview}')

print(f'\nProblematic cells: {problems}')
