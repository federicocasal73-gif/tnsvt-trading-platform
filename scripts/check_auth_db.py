import sqlite3, os

auth_db = 'apps/platform/auth-service/data/auth.db'
if not os.path.exists(auth_db):
    print(f"Auth DB not found at {auth_db}")
    exit(1)

conn = sqlite3.connect(auth_db)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

if 'users' in tables:
    cur.execute('SELECT id, email, username, role, status FROM users')
    print("\n=== USERS ===")
    for row in cur.fetchall():
        print(row)

if 'tenants' in tables:
    cur.execute('SELECT id, name, slug, status FROM tenants')
    print("\n=== TENANTS ===")
    for row in cur.fetchall():
        print(row)

conn.close()
