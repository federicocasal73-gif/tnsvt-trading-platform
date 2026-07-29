"""
Dead Letter Queue - Persistencia para señales que fallaron al ejecutarse.

Cuando una senal falla 3 veces en el executor (retry exhausto), se guarda
aqui para revision posterior. Permite:
- Auditoria de que senales se perdieron
- Retry manual desde el panel Mt5Settings
- Cleanup periodico de senales viejas (>7 dias)
"""
import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("SignalCopier.DeadLetter")

_DLQ_PATH = Path(
    __file__
).parent.parent / "signal_copier" / "dead_letter.db"

_DDL = """
CREATE TABLE IF NOT EXISTS failed_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    failed_at REAL NOT NULL,
    retried_count INTEGER DEFAULT 0,
    last_retry_at REAL,
    resolved INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_failed_at ON failed_signals(failed_at DESC);
CREATE INDEX IF NOT EXISTS idx_resolved ON failed_signals(resolved);
"""

_lock = threading.Lock()


@contextmanager
def _conn():
    conn = sqlite3.connect(str(_DLQ_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema() -> None:
    with _lock:
        _DLQ_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _conn() as c:
            for stmt in _DDL.strip().split(";"):
                s = stmt.strip()
                if s:
                    c.execute(s)


_ensure_schema()


def push(signal: dict, reason: str) -> int:
    """Guarda una senal fallida. Retorna el ID asignado."""
    try:
        sig_json = json.dumps(signal, default=str)
        with _conn() as c:
            cur = c.execute(
                "INSERT INTO failed_signals (signal_json, reason, failed_at) "
                "VALUES (?, ?, ?)",
                (sig_json, reason[:500], time.time()),
            )
            new_id = cur.lastrowid
        logger.warning(
            f"dead_letter.push: signal={signal.get('symbol')} {signal.get('action')} "
            f"reason={reason[:100]} id={new_id}"
        )
        return new_id or 0
    except Exception as e:
        logger.error(f"dead_letter.push error: {e}")
        return 0


def get_pending(limit: int = 50) -> list[dict]:
    """Obtiene senales no resueltas, ordenadas por fecha descendente."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT id, signal_json, reason, failed_at, retried_count "
                "FROM failed_signals WHERE resolved = 0 "
                "ORDER BY failed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "signal": json.loads(r["signal_json"]),
                "reason": r["reason"],
                "failed_at": r["failed_at"],
                "retried_count": r["retried_count"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"dead_letter.get_pending error: {e}")
        return []


def get_one(failed_id: int) -> dict | None:
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT * FROM failed_signals WHERE id = ?", (failed_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "signal": json.loads(row["signal_json"]),
            "reason": row["reason"],
            "failed_at": row["failed_at"],
            "retried_count": row["retried_count"],
            "resolved": bool(row["resolved"]),
        }
    except Exception as e:
        logger.error(f"dead_letter.get_one error: {e}")
        return None


def mark_retried(failed_id: int) -> None:
    """Incrementa el contador de reintentos."""
    try:
        with _conn() as c:
            c.execute(
                "UPDATE failed_signals SET retried_count = retried_count + 1, "
                "last_retry_at = ? WHERE id = ?",
                (time.time(), failed_id),
            )
        logger.info(f"dead_letter: id={failed_id} marcado como retried")
    except Exception as e:
        logger.error(f"dead_letter.mark_retried error: {e}")


def mark_resolved(failed_id: int) -> None:
    """Marca la senal como resuelta (ya procesada o descartada)."""
    try:
        with _conn() as c:
            c.execute(
                "UPDATE failed_signals SET resolved = 1 WHERE id = ?",
                (failed_id,),
            )
        logger.info(f"dead_letter: id={failed_id} marcado como resolved")
    except Exception as e:
        logger.error(f"dead_letter.mark_resolved error: {e}")


def cleanup_old(max_age_days: int = 7) -> int:
    """Elimina senales resueltas con mas de N dias. Retorna cantidad."""
    try:
        cutoff = time.time() - max_age_days * 86400
        with _conn() as c:
            cur = c.execute(
                "DELETE FROM failed_signals WHERE resolved = 1 AND failed_at < ?",
                (cutoff,),
            )
            deleted = cur.rowcount
        if deleted:
            logger.info(f"dead_letter.cleanup_old: borradas {deleted} senales")
        return deleted
    except Exception as e:
        logger.error(f"dead_letter.cleanup_old error: {e}")
        return 0


def stats() -> dict:
    try:
        with _conn() as c:
            total = c.execute(
                "SELECT COUNT(*) FROM failed_signals"
            ).fetchone()[0]
            pending = c.execute(
                "SELECT COUNT(*) FROM failed_signals WHERE resolved = 0"
            ).fetchone()[0]
            oldest = c.execute(
                "SELECT MIN(failed_at) FROM failed_signals WHERE resolved = 0"
            ).fetchone()[0]
        return {
            "total": total,
            "pending": pending,
            "oldest_failed_at": oldest,
        }
    except Exception as e:
        logger.error(f"dead_letter.stats error: {e}")
        return {"total": 0, "pending": 0, "oldest_failed_at": None}