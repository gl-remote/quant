"""先看数据库 schema"""
import sqlite3

DB = "/Users/gaolei/Documents/src/quant/project_data/quant.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
print("所有表:")
for t in tables:
    print(f"  {t[0]}")
    cur.execute(f"PRAGMA table_info({t[0]})")
    cols = cur.fetchall()
    for c in cols:
        print(f"    {c[1]:30s} {c[2]}")
conn.close()
