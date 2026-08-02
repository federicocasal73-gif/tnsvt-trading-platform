"""
CommunityDB — Tablas de comunidad (encuestas, votos y eventos económicos).

Capa "Bot/Comunidad": separa la persistencia del bot de Telegram de la
base de trades (bridge_outbox.db). Sigue el mismo patrón de db.py
(SQLite, WAL, threading.Lock, DDL idempotente).

Tablas:
  - surveys          → encuestas creadas desde el bot/frontend.
  - survey_votes     → votos por usuario (un voto por user_id por encuesta).
  - economic_events  → eventos del calendario económico (estado de notificación).
"""

import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("bridge.community")

COMMUNITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS surveys (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    options_json TEXT NOT NULL,
    channel_id INTEGER,
    created_by INTEGER,
    close_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS survey_votes (
    id TEXT PRIMARY KEY,
    survey_id TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    chat_id INTEGER,
    option_selected INTEGER NOT NULL,
    voted_at TEXT NOT NULL,
    UNIQUE(survey_id, user_id)
);

CREATE TABLE IF NOT EXISTS economic_events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'investing',
    currency TEXT,
    indicator TEXT NOT NULL,
    announcement_dt TEXT,
    previous TEXT,
    forecast TEXT,
    actual TEXT,
    impact INTEGER NOT NULL DEFAULT 3,
    notify_enabled INTEGER NOT NULL DEFAULT 1,
    notified_pre INTEGER NOT NULL DEFAULT 0,
    notified_actual INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_surveys_active ON surveys(is_active);
CREATE INDEX IF NOT EXISTS idx_votes_survey ON survey_votes(survey_id);
CREATE INDEX IF NOT EXISTS idx_votes_user ON survey_votes(user_id);
CREATE INDEX IF NOT EXISTS idx_events_dt ON economic_events(announcement_dt);
CREATE INDEX IF NOT EXISTS idx_events_currency ON economic_events(currency);
"""


def _now() -> str:
    """Timestamp UTC canónico (6 dígitos microsegundos, offset +00:00).

    Formato fijo para que las comparaciones lexicográficas de SQLite
    sobre announcement_dt sean correctas (mismo shape en todas las filas).
    """
    return _utc_iso(datetime.now(timezone.utc))


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _normalize_dt(value) -> str | None:
    """Convierte cualquier fecha a UTC canónico o None si no es parseable.

    Acepta: datetime, epoch (int/float), strings ISO con offset/Z,
    "YYYY-MM-DD HH:MM:SS", "YYYY-MM-DD HH:MM".
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, (int, float)):
        try:
            return _utc_iso(datetime.fromtimestamp(value, tz=timezone.utc))
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return _utc_iso(dt)
        except ValueError:
            continue
    return None


class CommunityDB:
    """Acceso a tablas de comunidad en community.db."""

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
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(COMMUNITY_SCHEMA)
        logger.info("CommunityDB schema initialized (%s)", self.db_path)

    # ─── Surveys ──────────────────────────────────────────────────────

    def create_survey(self, title: str, options: list[str],
                      channel_id: int | None = None,
                      created_by: int | None = None,
                      close_date: str | None = None) -> dict:
        survey_id = uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO surveys
                   (id, title, options_json, channel_id, created_by,
                    close_date, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (survey_id, title, _json(options), channel_id, created_by,
                 close_date, _now()),
            )
        return self.get_survey(survey_id)

    def list_surveys(self, status: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if status == "active":
                rows = conn.execute(
                    "SELECT * FROM surveys WHERE is_active=1 ORDER BY created_at DESC"
                ).fetchall()
            elif status == "closed":
                rows = conn.execute(
                    "SELECT * FROM surveys WHERE is_active=0 ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM surveys ORDER BY created_at DESC"
                ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            item["options"] = _unjson(item.pop("options_json", "[]"))
            result.append(item)
        return result

    def get_survey(self, survey_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM surveys WHERE id=?", (survey_id,)
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            result["options"] = _unjson(result.pop("options_json", "[]"))
            result["votes"] = self._survey_votes(conn, survey_id)
        return result

    def _survey_votes(self, conn: sqlite3.Connection, survey_id: str) -> list[dict]:
        rows = conn.execute(
            "SELECT option_selected, COUNT(*) AS count FROM survey_votes "
            "WHERE survey_id=? GROUP BY option_selected",
            (survey_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def register_vote(self, survey_id: str, user_id: int,
                      chat_id: int | None, option_selected: int) -> dict:
        """Registra un voto. Idempotente por (survey_id, user_id).

        Si el usuario ya votó, actualiza la opción elegida y devuelve
        'updated'. Si es la primera vez, 'created'.
        """
        vote_id = uuid.uuid4().hex
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM survey_votes WHERE survey_id=? AND user_id=?",
                (survey_id, user_id),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE survey_votes SET option_selected=?, voted_at=? WHERE id=?",
                    (option_selected, _now(), existing["id"]),
                )
                return {"status": "updated", "vote_id": existing["id"]}
            conn.execute(
                """INSERT INTO survey_votes
                   (id, survey_id, user_id, chat_id, option_selected, voted_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (vote_id, survey_id, user_id, chat_id, option_selected, _now()),
            )
        return {"status": "created", "vote_id": vote_id}

    def has_voted(self, survey_id: str, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM survey_votes WHERE survey_id=? AND user_id=? LIMIT 1",
                (survey_id, user_id),
            ).fetchone()
        return row is not None

    def set_survey_active(self, survey_id: str, is_active: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE surveys SET is_active=? WHERE id=?", (is_active, survey_id)
            )
        return cur.rowcount > 0

    # ─── Economic events ──────────────────────────────────────────────

    def upsert_event(self, event_id: str, source: str, currency: str,
                     indicator: str, announcement_dt: str | None,
                     previous: str | None, forecast: str | None,
                     actual: str | None, impact: int,
                     notify_pre: bool = False,
                     notify_actual: bool = False) -> None:
        announcement_dt = _normalize_dt(announcement_dt)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO economic_events
                   (id, source, currency, indicator, announcement_dt,
                    previous, forecast, actual, impact, notified_pre,
                    notified_actual, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                    announcement_dt=excluded.announcement_dt,
                    previous=excluded.previous,
                    forecast=excluded.forecast,
                    actual=excluded.actual,
                    impact=excluded.impact,
                    notified_pre=CASE WHEN excluded.notified_pre=1
                                      THEN 1 ELSE economic_events.notified_pre END,
                    notified_actual=CASE WHEN excluded.notified_actual=1
                                         THEN 1 ELSE economic_events.notified_actual END""",
                (event_id, source, currency, indicator, announcement_dt,
                 previous, forecast, actual, impact,
                 1 if notify_pre else 0, 1 if notify_actual else 0, _now()),
            )

    def get_events(self, days: int = 7, impact: int | None = None,
                   currency: str | None = None) -> list[dict]:
        with self._connect() as conn:
            sql = "SELECT * FROM economic_events WHERE 1=1"
            params: list = []
            if days is not None:
                sql += " AND announcement_dt >= ?"
                params.append(_iso_days_ago(days))
            if impact is not None:
                sql += " AND impact = ?"
                params.append(impact)
            if currency:
                sql += " AND currency = ?"
                params.append(currency)
            sql += " ORDER BY announcement_dt ASC"
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_event(self, event_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM economic_events WHERE id=?", (event_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_event_notify(self, event_id: str, notify_enabled: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE economic_events SET notify_enabled=? WHERE id=?",
                (notify_enabled, event_id),
            )
        return cur.rowcount > 0

    def mark_notified(self, event_id: str, kind: str) -> bool:
        """kind: 'pre' (notificado antes) o 'actual' (dato publicado)."""
        if kind == "actual":
            col = "notified_actual"
        else:
            col = "notified_pre"
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE economic_events SET {col}=1 WHERE id=?",
                (event_id,),
            )
        return cur.rowcount > 0

    def get_pending_actual(self, max_minutes: int = 120) -> list[dict]:
        """Eventos notificados antes, sin dato real, dentro de la ventana."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM economic_events "
                "WHERE notified_pre=1 AND notified_actual=0 "
                "AND announcement_dt <= ? AND announcement_dt >= ? "
                "AND notify_enabled=1 ORDER BY announcement_dt ASC",
                (_now(), _iso_minutes_ago(max_minutes)),
            ).fetchall()
        return [dict(r) for r in rows]


def _json(obj: object) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _unjson(s: str):
    import json
    try:
        return json.loads(s)
    except Exception:
        return []


def _iso_days_ago(days: int) -> str:
    from datetime import timedelta
    return _utc_iso(datetime.now(timezone.utc) - timedelta(days=days))


def _iso_minutes_ago(minutes: int) -> str:
    from datetime import timedelta
    return _utc_iso(datetime.now(timezone.utc) - timedelta(minutes=minutes))
