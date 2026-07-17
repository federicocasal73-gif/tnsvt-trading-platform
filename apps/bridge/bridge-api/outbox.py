"""
Bridge API - Outbox persistente SQLite.

Garantiza que ninguna orden ejecutada por el bot MT5 se pierda, incluso si:
- El bridge :8502 está caído
- El gateway TNSVT :8000 está caído
- La red se interrumpe

Cada orden se persiste localmente ANTES de intentar publicarla. Un worker
en background procesa la cola con backoff exponencial.
"""

import sqlite3
import json
import threading
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bridge.outbox")

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    delivered_at TEXT,
    next_attempt_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON outbox(next_attempt_at) WHERE status = 'PENDING';

CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
"""


class Outbox:
    """Cola persistente SQLite con retry automático."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def enqueue(self, payload: dict, source: str = "mt5-bot") -> int:
        """Inserta un evento en la cola. Devuelve el ID."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO outbox
                       (payload, source, status, attempts, created_at,
                        updated_at, next_attempt_at)
                   VALUES (?, ?, 'PENDING', 0, ?, ?, ?)""",
                (json.dumps(payload), source, now, now, now),
            )
            return cur.lastrowid

    def fetch_pending(self, limit: int = 20) -> list[dict]:
        """Obtiene eventos listos para reintentar."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT id, payload, source, attempts, next_attempt_at
                   FROM outbox
                   WHERE status = 'PENDING' AND next_attempt_at <= ?
                   ORDER BY id ASC
                   LIMIT ?""",
                (now, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_delivered(self, event_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE outbox
                   SET status = 'DELIVERED', delivered_at = ?,
                       updated_at = ?
                   WHERE id = ?""",
                (now, now, event_id),
            )

    def mark_failed(self, event_id: int, error: str, attempt: int) -> None:
        """Marca fallo y programa próximo intento con backoff."""
        now = datetime.now(timezone.utc).isoformat()
        # Backoff exponencial: 5s, 10s, 20s, 40s, 80s, 160s, máx 5min
        delay_seconds = min(5 * (2 ** min(attempt - 1, 6)), 300)
        next_at = datetime.fromtimestamp(
            time.time() + delay_seconds, tz=timezone.utc
        ).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """UPDATE outbox
                   SET status = 'PENDING', attempts = ?, last_error = ?,
                       updated_at = ?, next_attempt_at = ?
                   WHERE id = ?""",
                (attempt, error[:500], now, next_at, event_id),
            )

    def stats(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT status, COUNT(*) AS n FROM outbox GROUP BY status"""
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}
