"""
TradesDB — Tabla de trades en bridge_outbox.db para analytics.

Mantiene una copia sincronizada de los trades del bot MT5 para
exponer KPIs, equity curve, breakdowns por canal/símbolo, etc.
"""

import sqlite3
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bridge.db")

TRADES_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket INTEGER UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    volume REAL NOT NULL,
    open_price REAL NOT NULL,
    close_price REAL,
    sl REAL,
    tp REAL,
    pnl REAL DEFAULT 0,
    commission REAL DEFAULT 0,
    swap REAL DEFAULT 0,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    channel_id INTEGER,
    channel_title TEXT,
    topic_id INTEGER,
    status TEXT NOT NULL DEFAULT 'OPEN',
    received_at TEXT NOT NULL
);
"""

# Migración idempotente: columnas e índices añadidos en versiones posteriores.
# SQLite <3.35 no tiene `IF NOT EXISTS ADD COLUMN`, así que ALTER TABLE se
# ejecuta con try/except. Los CREATE INDEX sí son idempotentes nativamente.
TRADES_MIGRATIONS = [
    "ALTER TABLE trades ADD COLUMN tenant_id TEXT DEFAULT 'default'",
    "ALTER TABLE trades ADD COLUMN source TEXT DEFAULT 'mt5-bot'",
    "CREATE INDEX IF NOT EXISTS idx_trades_tenant_id ON trades(tenant_id)",
]  # los índices status/channel/symbol/closed_at ya están en TRADES_SCHEMA


class TradesDB:
    """Acceso a tabla trades en bridge_outbox.db."""

    def __init__(self, db_path: str):
        self.db_path = db_path
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
            conn.executescript(TRADES_SCHEMA)
            for stmt in TRADES_MIGRATIONS:
                # Solo los ALTER TABLE pueden fallar por "duplicate column".
                if stmt.startswith("ALTER TABLE"):
                    try:
                        conn.execute(stmt)
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e):
                            raise
                else:
                    conn.execute(stmt)
        logger.info("TradesDB schema initialized (with migrations)")

    def upsert_trade(self, payload: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO trades
                    (ticket, symbol, action, volume, open_price, close_price,
                     sl, tp, pnl, commission, swap,
                     opened_at, closed_at,
                     channel_id, channel_title, topic_id,
                     status, received_at,
                     tenant_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticket) DO UPDATE SET
                    close_price=COALESCE(excluded.close_price, close_price),
                    pnl=COALESCE(excluded.pnl, pnl),
                    commission=COALESCE(excluded.commission, commission),
                    swap=COALESCE(excluded.swap, swap),
                    closed_at=COALESCE(excluded.closed_at, closed_at),
                    status=COALESCE(excluded.status, status),
                    tenant_id=COALESCE(excluded.tenant_id, tenant_id),
                    source=COALESCE(excluded.source, source)""",
                (
                    payload.get("ticket"),
                    payload.get("symbol"),
                    payload.get("action"),
                    payload.get("volume", 0),
                    payload.get("price") or payload.get("open_price", 0),
                    payload.get("close_price"),
                    payload.get("sl"),
                    payload.get("tp"),
                    payload.get("pnl") or 0,
                    payload.get("commission") or 0,
                    payload.get("swap") or 0,
                    payload.get("opened_at") or payload.get("received_at") or datetime.now(timezone.utc).isoformat(),
                    payload.get("closed_at"),
                    payload.get("channel_id"),
                    payload.get("channel_title"),
                    payload.get("topic_id"),
                    payload.get("status") or "OPEN",
                    payload.get("received_at") or datetime.now(timezone.utc).isoformat(),
                    payload.get("tenant_id") or "default",
                    payload.get("source") or "mt5-bot",
                ),
            )

    def fetch_all_trades(self, tenant_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if tenant_id:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE tenant_id=? ORDER BY id DESC",
                    (tenant_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades ORDER BY id DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def fetch_closed_trades(self, tenant_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if tenant_id:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status='CLOSED' AND tenant_id=? ORDER BY closed_at ASC",
                    (tenant_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status='CLOSED' ORDER BY closed_at ASC"
                ).fetchall()
        return [dict(r) for r in rows]

    def fetch_open_trades(self, tenant_id: Optional[str] = None) -> list[dict]:
        with self._connect() as conn:
            if tenant_id:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status='OPEN' AND tenant_id=? ORDER BY id DESC",
                    (tenant_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC"
                ).fetchall()
        return [dict(r) for r in rows]

