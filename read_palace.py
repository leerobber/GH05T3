import sqlite3
db = sqlite3.connect(r'C:\Users\leer4\GH05T3\backend\memory\palace.db')
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"\n  [{t}]  {count} rows")
    if count > 0:
        cur.execute(f"SELECT * FROM {t} LIMIT 5")
        cols = [d[0] for d in cur.description]
        print(f"  Cols: {cols}")
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            text = str(d.get('text') or d.get('content') or d.get('body') or d)
            print(f"    [{d.get('room','?')}] {text[:120]}")
db.close()
