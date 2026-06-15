import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres", connect_timeout=5)
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='agent_economy'")
if not cur.fetchone():
    cur.execute("CREATE DATABASE agent_economy")
    print("Created database agent_economy")
else:
    print("Database agent_economy already exists")
conn.close()
print("Done")
