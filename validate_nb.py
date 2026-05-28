import json, ast, re
from pathlib import Path

nb = json.loads(Path('C:/Users/leer4/GH05T3/kaggle_train.ipynb').read_text(encoding='utf-8'))
cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
print(f'Validating {len(cells)} code cells...\n')

all_ok = True
for i, cell in enumerate(cells):
    src = ''.join(cell.get('source', []))
    # Strip leading magic commands
    src_clean = re.sub(r'^%[^\n]+\n', '', src, flags=re.MULTILINE)
    try:
        ast.parse(src_clean)
        preview = src_clean[:60].replace('\n', ' ')
        print(f'  [OK]   Cell {i}: {preview}')
    except SyntaxError as e:
        all_ok = False
        print(f'  [FAIL] Cell {i} SYNTAX ERROR at line {e.lineno}: {e.msg}')
        # Show context
        lines = src_clean.splitlines()
        start = max(0, (e.lineno or 1) - 3)
        end   = min(len(lines), (e.lineno or 1) + 3)
        for ln, line in enumerate(lines[start:end], start=start+1):
            marker = '>>>' if ln == e.lineno else '   '
            print(f'     {marker} {ln:3d}: {line}')

print(f'\nResult: {"ALL OK" if all_ok else "SYNTAX ERRORS FOUND"}')
