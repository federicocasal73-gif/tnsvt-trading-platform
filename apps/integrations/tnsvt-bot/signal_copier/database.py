"""
Signal Copier - Base de Datos SQLite
"""
import sqlite3
import datetime
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger("SignalCopier.Database")

DB_DIR = Path(__file__).parent
DB_NAME = DB_DIR / "trades.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_NAME)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Inicializa la base de datos"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                """CREATE TABLE IF NOT EXISTS trades (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         date TEXT,
                         symbol TEXT,
                         action TEXT,
                         price REAL,
                         sl REAL,
                         tp TEXT,
                         result TEXT,
                         ticket INTEGER,
                         channel TEXT,
                         pnl REAL DEFAULT 0
                         )"""
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticket ON trades(ticket)")
            conn.commit()
        logger.info("Base de datos inicializada")

    except Exception as e:
        logger.error(f"Error inicializando DB: {e}")


def log_trade(
    symbol: str,
    action: str,
    price: float,
    sl: float,
    tp,
    result_msg: str,
    ticket: int = 0,
    channel: str = "",
    pnl: float = 0,
):
    """Registra una operacion en la base de datos"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tp_str = str(tp) if tp else ""

            c.execute(
                """INSERT INTO trades 
                   (date, symbol, action, price, sl, tp, result, ticket, channel, pnl) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date_str, symbol, action, price, sl, tp_str, result_msg, ticket, channel, pnl),
            )

            conn.commit()
        logger.debug(f"Trade registrado: {symbol} {action} @ {price}")

    except Exception as e:
        logger.error(f"Error logueando en DB: {e}")


def update_trade_pnl(ticket: int, pnl: float, result: str = None):
    """Actualiza PnL y resultado de un trade cerrado"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            if result:
                c.execute("UPDATE trades SET pnl=?, result=? WHERE ticket=?", (pnl, result, ticket))
            else:
                c.execute("UPDATE trades SET pnl=? WHERE ticket=?", (pnl, ticket))
            conn.commit()
    except Exception as e:
        logger.error(f"Error actualizando PnL en DB: {e}")


def update_last_trade(symbol: str, action: str, result: str, ticket: int = 0, pnl: float = 0):
    """Actualiza el ultimo trade con mismo symbol+action que esté en estado SEÑAL DETECTADA"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE trades SET result=?, ticket=?, pnl=? "
                "WHERE symbol=? AND action=? AND result='SENAL DETECTADA' "
                "ORDER BY id DESC LIMIT 1",
                (result, ticket, pnl, symbol, action),
            )
            if c.rowcount == 0:
                logger.debug(f"No se encontro trade pendiente para {symbol} {action}")
            conn.commit()
    except Exception as e:
        logger.error(f"Error actualizando trade: {e}")


def get_trades(limit: int = 50) -> list:
    """Obtiene las ultimas N operaciones"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
            return c.fetchall()
    except Exception as e:
        logger.error(f"Error obteniendo trades: {e}")
        return []


def get_trades_today() -> list:
    """Obtiene las operaciones de hoy"""
    try:
        with get_db() as conn:
            c = conn.cursor()
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            c.execute("SELECT * FROM trades WHERE date LIKE ?", (f"{today}%",))
            return c.fetchall()
    except Exception as e:
        logger.error(f"Error obteniendo trades de hoy: {e}")
        return []


def get_stats() -> dict:
    """Obtiene estadisticas generales"""
    try:
        with get_db() as conn:
            c = conn.cursor()

            c.execute("SELECT COUNT(*) FROM trades")
            total = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM trades WHERE REPLACE(LOWER(result), 'é', 'e') LIKE '%exito%' OR result LIKE '%DONE%' OR result = 'OK'"
            )
            wins = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM trades WHERE result LIKE '%BLOQUEADO%' OR result LIKE '%SEÑAL DETECTADA%'"
            )
            blocked = c.fetchone()[0]

            c.execute("SELECT SUM(pnl) FROM trades WHERE result NOT LIKE '%BLOQUEADO%' AND result != 'SEÑAL DETECTADA'")
            total_pnl = c.fetchone()[0] or 0

        executed = total - blocked
        losses = executed - wins
        if losses < 0:
            losses = 0

        win_rate = (wins / executed * 100) if executed > 0 else 0

        return {
            "total": total,
            "executed": executed,
            "blocked": blocked,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
        }
    except Exception as e:
        logger.error(f"Error obteniendo stats: {e}")
        return {"total": 0, "executed": 0, "blocked": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0}


def get_stats_today() -> dict:
    """Estadisticas solo de hoy.

    Replica la misma logica de get_stats() pero filtrando `date LIKE '%YYYY-MM-DD%'`.
    """
    try:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        with get_db() as conn:
            c = conn.cursor()

            c.execute(
                "SELECT COUNT(*) FROM trades WHERE date LIKE ?",
                (f"{today}%",),
            )
            total = c.fetchone()[0]

            c.execute(
                """SELECT COUNT(*) FROM trades WHERE date LIKE ? AND (
                    REPLACE(LOWER(result), 'é', 'e') LIKE '%exito%' OR result LIKE '%DONE%' OR result = 'OK'
                )""",
                (f"{today}%",),
            )
            wins = c.fetchone()[0]

            c.execute(
                """SELECT COUNT(*) FROM trades WHERE date LIKE ? AND (
                    result LIKE '%BLOQUEADO%' OR result LIKE '%SEÑAL DETECTADA%'
                )""",
                (f"{today}%",),
            )
            blocked = c.fetchone()[0]

            c.execute(
                """SELECT SUM(pnl) FROM trades WHERE date LIKE ? AND
                    result NOT LIKE '%BLOQUEADO%' AND result != 'SEÑAL DETECTADA'""",
                (f"{today}%",),
            )
            total_pnl = c.fetchone()[0] or 0

        executed = total - blocked
        losses = executed - wins
        if losses < 0:
            losses = 0

        win_rate = (wins / executed * 100) if executed > 0 else 0

        return {
            "total": total,
            "executed": executed,
            "blocked": blocked,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
        }
    except Exception as e:
        logger.error(f"Error obteniendo stats de hoy: {e}")
        return {"total": 0, "executed": 0, "blocked": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0}


def get_trades_since(days: int = 7) -> list:
    """Obtiene trades de los ultimos N dias"""
    try:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        with get_db() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT date, symbol, action, price, sl, tp, result, ticket, channel, pnl "
                "FROM trades WHERE date >= ? ORDER BY id DESC",
                (since,),
            )
            return c.fetchall()
    except Exception as e:
        logger.error(f"Error obteniendo trades recientes: {e}")
        return []


def get_stats_since(days: int = 7) -> dict:
    """Estadisticas de los ultimos N dias"""
    try:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        with get_db() as conn:
            c = conn.cursor()

            c.execute("SELECT COUNT(*) FROM trades WHERE date >= ?", (since,))
            total = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM trades WHERE date >= ? AND "
                "(REPLACE(LOWER(result), 'e', 'e') LIKE '%exito%' OR result LIKE '%DONE%' OR result = 'WIN')",
                (since,),
            )
            wins = c.fetchone()[0]

            c.execute(
                "SELECT COUNT(*) FROM trades WHERE date >= ? AND "
                "(result LIKE '%BLOQUEADO%' OR result LIKE '%SENAL DETECTADA%')",
                (since,),
            )
            blocked = c.fetchone()[0]

            c.execute(
                "SELECT SUM(pnl) FROM trades WHERE date >= ? AND "
                "result NOT LIKE '%BLOQUEADO%' AND result != 'SENAL DETECTADA'",
                (since,),
            )
            total_pnl = c.fetchone()[0] or 0

            c.execute(
                "SELECT SUM(pnl) FROM trades WHERE date >= ? AND result = 'WIN'",
                (since,),
            )
            pnl_wins = c.fetchone()[0] or 0

            c.execute(
                "SELECT SUM(pnl) FROM trades WHERE date >= ? AND result = 'LOSS'",
                (since,),
            )
            pnl_losses = c.fetchone()[0] or 0

        executed = total - blocked
        losses = executed - wins
        if losses < 0:
            losses = 0
        win_rate = (wins / executed * 100) if executed > 0 else 0

        return {
            "days": days,
            "total": total,
            "executed": executed,
            "blocked": blocked,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "pnl_wins": round(pnl_wins, 2),
            "pnl_losses": round(pnl_losses, 2),
        }
    except Exception as e:
        logger.error(f"Error obteniendo stats por periodo: {e}")
        return {"days": days, "total": 0, "executed": 0, "blocked": 0, "wins": 0, "losses": 0, "win_rate": 0, "total_pnl": 0, "pnl_wins": 0, "pnl_losses": 0}
