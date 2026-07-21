import sqlite3
import datetime
import json
import os

DB_NAME = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Tabla de Operaciones
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 date TEXT,
                 symbol TEXT,
                 action TEXT,
                 price REAL,
                 sl REAL,
                 tp TEXT,
                 result TEXT,
                 ticket INTEGER
                 )''')

    # Migración idempotente: agregar columnas nuevas si no existen
    _new_columns = [
        "pnl REAL DEFAULT 0",
        "close_price REAL",
        "closed_at TEXT",
        "channel_id INTEGER",
        "channel_title TEXT",
        "topic_id INTEGER",
        "commission REAL DEFAULT 0",
        "swap REAL DEFAULT 0",
        "status TEXT DEFAULT 'OPEN'",
    ]
    for col_def in _new_columns:
        try:
            c.execute(f"ALTER TABLE trades ADD COLUMN {col_def}")
        except sqlite3.OperationalError:
            pass  # columna ya existe

    # Tabla de cola para TNSVT Bridge (Bloque 2 - integración TNSVT)
    c.execute('''CREATE TABLE IF NOT EXISTS bridge_pending (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 payload TEXT NOT NULL,
                 source TEXT NOT NULL DEFAULT 'mt5-bot',
                 status TEXT NOT NULL DEFAULT 'PENDING',
                 attempts INTEGER NOT NULL DEFAULT 0,
                 last_error TEXT,
                 created_at TEXT NOT NULL,
                 updated_at TEXT NOT NULL,
                 delivered_at TEXT,
                 next_attempt_at TEXT NOT NULL
                 )''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_bridge_pending
                 ON bridge_pending(next_attempt_at) WHERE status = 'PENDING' ''')

    conn.commit()
    conn.close()

def log_trade(symbol, action, price, sl, tp, result_msg, ticket=0,
              channel_id=None, channel_title=None, topic_id=None):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tp_str = str(tp) if tp else ""

        c.execute("""INSERT INTO trades
            (date, symbol, action, price, sl, tp, result, ticket,
             channel_id, channel_title, topic_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')""",
            (date_str, symbol, action, price, sl, tp_str, result_msg, ticket,
             channel_id, channel_title, topic_id))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logueando en DB: {e}")

def get_trades(limit=50):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
    data = c.fetchall()
    conn.close()
    return data

# ─── Cola persistente hacia TNSVT Bridge ────────────────────────────────

def enqueue_bridge_event(payload: dict, source: str = "mt5-bot") -> int:
    """Inserta un evento en la cola local para publicar al bridge."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(DB_NAME, timeout=10)
    c = conn.cursor()
    c.execute(
        """INSERT INTO bridge_pending
               (payload, source, status, attempts, created_at,
                updated_at, next_attempt_at)
           VALUES (?, ?, 'PENDING', 0, ?, ?, ?)""",
        (json.dumps(payload), source, now, now, now),
    )
    event_id = c.lastrowid
    conn.commit()
    conn.close()
    return event_id

def fetch_pending_bridge(limit: int = 20) -> list:
    """Obtiene eventos listos para reintentar (worker del bot)."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    rows = c.execute(
        """SELECT id, payload, source, attempts, next_attempt_at
           FROM bridge_pending
           WHERE status = 'PENDING' AND next_attempt_at <= ?
           ORDER BY id ASC LIMIT ?""",
        (now, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_bridge_delivered(event_id: int) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """UPDATE bridge_pending
           SET status = 'DELIVERED', delivered_at = ?, updated_at = ?
           WHERE id = ?""",
        (now, now, event_id),
    )
    conn.commit()
    conn.close()

def mark_bridge_failed(event_id: int, error: str, attempt: int) -> None:
    """Marca fallo y programa próximo intento con backoff (5s, 10s, 20s, ..., máx 5min)."""
    import time
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    delay = min(5 * (2 ** min(attempt - 1, 6)), 300)
    next_at = datetime.datetime.fromtimestamp(
        time.time() + delay, tz=datetime.timezone.utc
    ).isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """UPDATE bridge_pending
           SET status = 'PENDING', attempts = ?, last_error = ?,
               updated_at = ?, next_attempt_at = ?
           WHERE id = ?""",
        (attempt, error[:500], now, next_at, event_id),
    )
    conn.commit()
    conn.close()

def bridge_stats() -> dict:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    rows = c.execute(
        "SELECT status, COUNT(*) FROM bridge_pending GROUP BY status"
    ).fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}
