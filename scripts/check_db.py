import psycopg2

conn = psycopg2.connect(host='localhost', dbname='tnsvt', user='postgres', password='postgres')
cur = conn.cursor()

# List all schemas
cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'public')")
schemas = cur.fetchall()
print("=== SCHEMAS ===")
for s in schemas:
    print(s[0])

# List tables in public
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
print("\n=== PUBLIC TABLES ===")
for t in cur.fetchall():
    print(t[0])

# Check users in public schema if exists
try:
    cur.execute('SELECT id, email, username, role, status FROM users')
    print("\n=== USERS ===")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"Users table query failed: {e}")

conn.close()
