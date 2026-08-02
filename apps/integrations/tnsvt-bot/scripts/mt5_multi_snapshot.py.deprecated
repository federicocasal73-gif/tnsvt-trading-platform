"""
mt5_multi_snapshot.py — Snapshot writer multi-cuenta MT5 (VERSION REEMPLAZO).

Funciona con varias instancias de MT5 abiertas (cada terminal64 con su
propia cuenta). Para cada cuenta en `D:\\TradingBotMT5\\accounts.json`,
escribe a archivos separados:
  - account_snapshot_<login>.json
  - positions_snapshot_<login>.json

Tambien mantiene el archivo "legacy" account_snapshot.json / positions_snapshot.json
de la cuenta principal para compatibilidad con codigo existente.

Frecuencia: cada 3 segundos.

Para agregar cuentas nuevas: editar `accounts.json` y reiniciar este script.

NOTA: Cada cuenta tiene su propia instancia de terminal64.exe abierta.
Desde Python solo conectamos a esa sesion via mt5.initialize() + mt5.login().
Si la cuenta es MetaQuotes-Demo no se necesita password en la mayoria de los
casos; para cuentas reales hay que poner el investor password.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

# Logging basico
LOG_PATH = Path(r"D:\TradingBotMT5\mt5_multi_snapshot.log")
logging.basicConfig(
    filename=str(LOG_PATH),
    filemode="a",
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("mt5-multi")

# Tambien emitimos a stdout (cuando se corre en foreground)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_handler)

BASE_DIR = Path(r"D:\TradingBotMT5")
ACCOUNTS_FILE = BASE_DIR / "accounts.json"
LEGACY_ACC = BASE_DIR / "account_snapshot.json"
LEGACY_POS = BASE_DIR / "positions_snapshot.json"
POLL_INTERVAL = 3.0

TYPE_MAP = {mt5.ORDER_TYPE_BUY: "BUY", mt5.ORDER_TYPE_SELL: "SELL"}
POSITION_FIELDS = [
    "ticket", "symbol", "type", "volume", "price_open",
    "sl", "tp", "price_current", "profit", "swap", "commission",
    "magic", "comment", "time",
]


def _load_accounts() -> list:
    if not ACCOUNTS_FILE.exists():
        log.warning(f"accounts.json no existe en {ACCOUNTS_FILE}")
        return []
    try:
        data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [a for a in data if a.get("login")]
    except Exception as e:
        log.error(f"Error leyendo accounts.json: {e}")
    return []


def _snap_path(login: int) -> Path:
    return BASE_DIR / f"account_snapshot_{login}.json"


def _pos_path(login: int) -> Path:
    return BASE_DIR / f"positions_snapshot_{login}.json"


def _serialize_position(pos) -> dict:
    d = {"type": TYPE_MAP.get(pos.type, "UNKNOWN")}
    for field in POSITION_FIELDS:
        if field == "type":
            continue
        val = getattr(pos, field, None)
        if isinstance(val, (int, float)):
            d[field] = val
        elif val is not None:
            d[field] = str(val)
    return d


def _write_atomically(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        log.warning(f"No pude escribir {path}: {e}")


def snapshot_for_account(account: dict) -> bool:
    """Conecta a MT5 para la cuenta, escribe snapshots.

    Devuelve True si conecto. Devuelve False si MT5 esta apagado o el login fallo
    (en cuyo caso probablemente hay que abrir el terminal64.exe y hacer login manual).
    """
    login = int(account["login"])
    password = account.get("password", "") or ""
    server = account.get("server", "")
    alias = account.get("alias", f"acc_{login}")

    try:
        if not mt5.initialize():
            log.warning(f"[{alias}] MT5 terminal no inicializado — abrí MT5 y hace login")
            return False

        # Hacer login si fue provisto
        if password and server:
            authorized = mt5.login(login=login, password=password, server=server)
            if not authorized:
                log.warning(f"[{alias}] login({login}) falló — revisar password en accounts.json")
                # Continuar — el account_info puede funcionar si ya hay sesión
        elif login:
            # Solo login entero (sin password) — funciona si el terminal ya tiene sesión
            try:
                mt5.login(login=login)
            except Exception as e:
                log.debug(f"[{alias}] login sin password falló (esperado si MT5 ya está logueado): {e}")

        info = mt5.account_info()
        if not info:
            log.warning(f"[{alias}] account_info() retornó None")
            return False

        snap = {
            "login": info.login,
            "balance": round(info.balance, 2),
            "equity": round(info.equity, 2),
            "margin": round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "margin_level": round(info.margin_level, 2) if info.margin_level else None,
            "profit": round(info.profit, 2),
            "leverage": info.leverage,
            "currency": info.currency,
            "server": info.server,
            "name": info.name,
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alias": alias,
        }
        _write_atomically(_snap_path(login), snap)

        positions = mt5.positions_get() or []
        rows = [_serialize_position(p) for p in positions]
        _write_atomically(_pos_path(login), rows)
        snap["open_positions"] = len(rows)
        _write_atomically(_snap_path(login), snap)

        log.info(f"[{alias}] login={login} bal=${snap['balance']:.2f} equity=${snap['equity']:.2f} open={len(rows)}")

        # Mantener archivo legacy apuntando a la primera cuenta (la "principal")
        # Solo si es la cuenta marcada como alias=demo_main
        if alias == "demo_main" or login == 10011629660:
            _write_atomically(LEGACY_ACC, snap)
            _write_atomically(LEGACY_POS, rows)

        return True
    except Exception as e:
        log.warning(f"[{alias}] snap error: {e}")
        return False


def disconnect_mt5():
    try:
        mt5.shutdown()
    except Exception:
        pass


def main():
    log.info("=" * 50)
    log.info("mt5_multi_snapshot iniciado (single-MT5-session mode)")
    log.info("=" * 50)

    while True:
        accounts = _load_accounts()
        if not accounts:
            log.warning("Sin cuentas en accounts.json — esperando…")
            time.sleep(10)
            continue

        # Una sola sesion de MT5 en este proceso. Iteramos las cuentas
        # cambiando de login() entre cada una. El signal_copier usa OTRO
        # proceso por lo tanto no hay conflicto.
        for acc in accounts:
            try:
                snapshot_for_account(acc)
            except Exception as e:
                log.warning(f"Error en cuenta {acc.get('login')}: {e}")
            time.sleep(0.2)

        # NO cerramos mt5 — el siguiente ciclo reutiliza la sesion.
        # Si otro proceso intenta mt5.initialize() al mismo tiempo, MT5
        # mostrara error y lo capturamos arriba.
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Interrumpido por usuario")
    except Exception as e:
        log.exception(f"Fatal: {e}")
        sys.exit(1)
    finally:
        disconnect_mt5()
