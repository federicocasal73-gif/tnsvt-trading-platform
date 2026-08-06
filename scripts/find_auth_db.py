import sqlite3, os

paths = [
    'apps/platform/auth-service/auth.db',
    'apps/platform/auth-service/data/auth.db',
    'apps/platform/auth-service/internal/data/auth.db',
    'data/auth.db',
    'auth.db',
]

for path in paths:
    if os.path.exists(path):
        print(f"Found: {path}")
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"  Tables: {tables}")
        if 'users' in tables:
            cur.execute('SELECT id, email, username, role, status FROM users')
            for row in cur.fetchall():
                print(f"  User: {row}")
        conn.close()
    else:
        print(f"Not found: {path}")
