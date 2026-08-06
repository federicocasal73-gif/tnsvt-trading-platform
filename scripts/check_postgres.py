import sys

# Check available DB drivers
drivers = []
try:
    import psycopg2
    drivers.append('psycopg2')
except ImportError:
    print("psycopg2: NOT AVAILABLE")

try:
    import pg8000
    drivers.append('pg8000')
except ImportError:
    print("pg8000: NOT AVAILABLE")

try:
    import sqlite3
    drivers.append('sqlite3')
    print("sqlite3: AVAILABLE")
except ImportError:
    print("sqlite3: NOT AVAILABLE")

print(f"Available drivers: {drivers}")

# If psycopg2 available, connect to PostgreSQL
if 'psycopg2' in drivers:
    import psycopg2
    conn = psycopg2.connect(host='localhost', dbname='tnsvt', user='postgres', password='postgres')
    cur = conn.cursor()
    cur.execute("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')")
    schemas = {}
    for row in cur.fetchall():
        schemas.setdefault(row[0], []).append(row[1])
    for schema, tables in schemas.items():
        print(f"\n=== Schema: {schema} ===")
        for t in tables:
            print(f"  {t}")

    # Check platform.users
    cur.execute("SELECT id::text, email, username, role, status FROM platform.users")
    print("\n=== platform.users ===")
    for row in cur.fetchall():
        print(f"  id={row[0]}, email={row[1]}, username={row[2]}, role={row[3]}, status={row[4]}")

    cur.execute("SELECT id::text, name, slug, status FROM platform.tenants")
    print("\n=== platform.tenants ===")
    for row in cur.fetchall():
        print(f"  id={row[0]}, name={row[1]}, slug={row[2]}, status={row[3]}")

    conn.close()
