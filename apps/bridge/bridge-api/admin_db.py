"""
AdminDB — Gestión manual de suscriptores (tenants) para cobro por transferencia.

El panel Admin del frontend (AdminPage) muestra MRR/churn/plan breakdown.
Como las suscripciones se venden por transferencia (sin Stripe), el
operador da de alta manualmente a cada cliente que paga. Esta capa
persiste esos tenants en una tabla SQLite dedicada (admin.db), siguiendo
el mismo patrón de community_db.py (SQLite, WAL, threading.Lock, DDL
idempotente).

Planes comerciales (precios USD confirmados):
  - trimestral: $150 USD total  → MRR $50/mes   (3 meses)
  - semestral:  $375 USD total  → MRR $62,50/mes (6 meses)
  - anual:      $599.99 USD     → MRR $50/mes   (12 meses)

Tabla:
  - tenants → suscriptor manual con plan, estado, montos y vencimiento.
"""

import logging
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("bridge.admin")

# ─── Planes comerciales ────────────────────────────────────────────────

PLAN_DURATION_MONTHS = {
    "trimestral": 3,
    "semestral": 6,
    "anual": 12,
}

PLAN_PRICE_USD = {
    "trimestral": 150.0,
    "semestral": 375.0,
    "anual": 599.99,
}

PLAN_MRR_USD = {
    plan: round(price / months, 2)
    for plan, (months, price) in {
        plan: (PLAN_DURATION_MONTHS[plan], PLAN_PRICE_USD[plan])
        for plan in PLAN_DURATION_MONTHS
    }.items()
}

VALID_PLANS = set(PLAN_DURATION_MONTHS)
VALID_STATUSES = {"active", "trial", "suspended"}

ADMIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    email TEXT,
    plan TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'trial',
    price_usd REAL,
    price_ars TEXT,
    max_users INTEGER NOT NULL DEFAULT 1,
    max_signals_per_day INTEGER NOT NULL DEFAULT 20,
    started_at TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
CREATE INDEX IF NOT EXISTS idx_tenants_plan ON tenants(plan);
CREATE INDEX IF NOT EXISTS idx_tenants_expires ON tenants(expires_at);
"""


def _now() -> str:
    return _utc_iso(datetime.now(timezone.utc))


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _slugify(name: str) -> str:
    slug = (name or "").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:30]


def _add_months(start: datetime, months: int) -> datetime:
    """Suma meses manteniendo el día (clamping a fin de mes)."""
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, [31, 29 if year % 4 == 0 and year % 100 != 0 or year % 400 == 0 else 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return start.replace(year=year, month=month, day=day)


class AdminDB:
    """Acceso a tablas de suscriptores en admin.db."""

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
            conn.executescript(ADMIN_SCHEMA)
        logger.info("AdminDB schema initialized (%s)", self.db_path)

    # ─── Tenants ─────────────────────────────────────────────────────

    def create_tenant(self, name: str, plan: str,
                      email: str | None = None,
                      slug: str | None = None,
                      status: str = "trial",
                      price_usd: float | None = None,
                      price_ars: str | None = None,
                      started_at: str | None = None,
                      expires_at: str | None = None,
                      max_users: int = 1,
                      max_signals_per_day: int = 20) -> dict:
        """Crea un tenant. Vencimiento auto-calculado según el plan si no se pasa."""
        if plan not in VALID_PLANS:
            raise ValueError(f"plan inválido: {plan}")
        if status not in VALID_STATUSES:
            raise ValueError(f"status inválido: {status}")

        tenant_id = uuid.uuid4().hex
        now = _now()

        if started_at:
            start_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        else:
            start_dt = datetime.now(timezone.utc)

        months = PLAN_DURATION_MONTHS[plan]
        end_dt = _add_months(start_dt, months) if not expires_at else datetime.fromisoformat(
            str(expires_at).replace("Z", "+00:00")
        )

        if price_usd is None:
            price_usd = PLAN_PRICE_USD[plan]

        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO tenants
                   (id, name, slug, email, plan, status, price_usd, price_ars,
                    max_users, max_signals_per_day, started_at, expires_at,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tenant_id, name.strip(), slug or _slugify(name), email,
                 plan, status, price_usd, price_ars,
                 max_users, max_signals_per_day,
                 _utc_iso(start_dt), _utc_iso(end_dt), now, now),
            )
        return self.get_tenant(tenant_id)

    def list_tenants(self, limit: int = 50, offset: int = 0,
                     status: str | None = None) -> list[dict]:
        with self._connect() as conn:
            sql = "SELECT * FROM tenants WHERE 1=1"
            params: list = []
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params += [limit, offset]
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_tenant(self, tenant_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tenants WHERE id=?", (tenant_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_tenant(self, tenant_id: str, *,
                      name: str | None = None,
                      email: str | None = None,
                      plan: str | None = None,
                      status: str | None = None,
                      price_usd: float | None = None,
                      price_ars: str | None = None,
                      expires_at: str | None = None,
                      max_users: int | None = None,
                      max_signals_per_day: int | None = None) -> dict | None:
        """Actualiza campos parciales de un tenant."""
        existing = self.get_tenant(tenant_id)
        if not existing:
            return None

        if plan is not None and plan not in VALID_PLANS:
            raise ValueError(f"plan inválido: {plan}")
        if status is not None and status not in VALID_STATUSES:
            raise ValueError(f"status inválido: {status}")

        new_plan = plan if plan is not None else existing.get("plan")
        fields = {
            "name": name,
            "email": email,
            "plan": new_plan,
            "status": status,
            "price_usd": price_usd,
            "price_ars": price_ars,
            "expires_at": expires_at,
            "max_users": max_users,
            "max_signals_per_day": max_signals_per_day,
        }
        updates = {k: v for k, v in fields.items() if v is not None}

        # Si cambia el plan y no se toca el vencimiento, recalculamos.
        if plan is not None and plan != existing.get("plan"):
            if not expires_at:
                try:
                    start_dt = datetime.fromisoformat(
                        str(existing.get("started_at") or _now()).replace("Z", "+00:00")
                    )
                    updates["expires_at"] = _utc_iso(_add_months(
                        start_dt, PLAN_DURATION_MONTHS[plan]
                    ))
                except Exception:
                    pass
            if "price_usd" not in updates:
                updates["price_usd"] = PLAN_PRICE_USD[plan]

        if not updates:
            return existing

        sets = ", ".join(f"{k}=?" for k in updates)
        params = list(updates.values())
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE tenants SET {sets}, updated_at=? WHERE id=?",
                         params + [_now(), tenant_id])
        return self.get_tenant(tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM tenants WHERE id=?", (tenant_id,))
        return cur.rowcount > 0

    # ─── Stats ───────────────────────────────────────────────────────

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) AS c FROM tenants WHERE status='active'"
            ).fetchone()["c"]
            suspended = conn.execute(
                "SELECT COUNT(*) AS c FROM tenants WHERE status='suspended'"
            ).fetchone()["c"]
            by_plan_rows = conn.execute(
                "SELECT plan, COUNT(*) AS c FROM tenants GROUP BY plan"
            ).fetchall()

        by_plan = [{"plan": r["plan"], "count": r["c"]} for r in by_plan_rows]

        # MRR = suma del MRR de cada tenant activo.
        mrr_usd = 0.0
        with self._connect() as conn:
            active_rows = conn.execute(
                "SELECT plan FROM tenants WHERE status='active'"
            ).fetchall()
        for r in active_rows:
            mrr_usd += PLAN_MRR_USD.get(r["plan"], 0.0)
        mrr_usd = round(mrr_usd, 2)

        # Churn simple (sin webhook): bajas sobre el total de pagantes.
        churn_pct = round((suspended / total) * 100, 1) if total else 0.0

        return {
            "total_tenants": total,
            "active_subscriptions": active,
            "mrr_usd": mrr_usd,
            "churn_pct": churn_pct,
            "by_plan": by_plan,
            "pricing_per_plan_usd": dict(PLAN_MRR_USD),
        }
