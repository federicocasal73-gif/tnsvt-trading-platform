#!/usr/bin/env python3
"""
TNSVT V2 - MT5 Bridge
Conecta con MetaTrader 5 via librería oficial y ejecuta operaciones.

Operaciones soportadas:
- initialize: inicializa MT5 y hace login
- shutdown: desconecta MT5
- account_info: retorna info de cuenta activa
- place_order: coloca una orden
- close_position: cierra una posición por ticket
- modify_position: modifica SL/TP de una posición
- positions_get: retorna posiciones abiertas
- symbol_info: info del símbolo

Uso:
  python mt5_bridge.py <op> --json '{"key": "value", ...}'

Output: JSON con formato {"success": bool, "error": str, "data": {...}}
"""

import sys
import json
import argparse
import logging
from datetime import datetime
from typing import Optional

# ─── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] MT5Bridge: %(message)s'
)
log = logging.getLogger("MT5Bridge")

# ─── Constants ─────────────────────────────────────────────────
TPS_IN_SECONDS = 60 * 60  # for time conversion

# ─── Output helper ─────────────────────────────────────────────
def output(success: bool, error: str = "", data: dict = None):
    """Print JSON result to stdout."""
    result = {
        "success": success,
        "error": error,
        "data": data or {},
    }
    print(json.dumps(result, default=str))
    sys.exit(0 if success else 1)


def import_mt5():
    """Lazy import de MetaTrader5 para fallar limpio si no está instalado."""
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        output(False, error="MetaTrader5 library not installed (pip install MetaTrader5)")


# ─── Operations ───────────────────────────────────────────────

def op_initialize(args: dict) -> bool:
    mt5 = import_mt5()

    path = args.get("path", "")
    login = args.get("login", 0)
    password = args.get("password", "")
    server = args.get("server", "")

    if not path:
        output(False, error="path is required")

    log.info(f"Initializing MT5 at {path}")

    # Initialize
    if not mt5.initialize(path=path):
        output(False, error=f"mt5.initialize failed: {mt5.last_error()}")

    # Login
    if login and password and server:
        authorized = mt5.login(login=int(login), password=password, server=server)
        if not authorized:
            output(False, error=f"mt5.login failed: {mt5.last_error()}")

    # Verify
    account_info = mt5.account_info()
    if account_info is None:
        output(False, error=f"mt5.account_info failed: {mt5.last_error()}")

    output(True, data={
        "login": account_info.login,
        "server": account_info.server,
        "name": account_info.name,
        "currency": account_info.currency,
        "balance": account_info.balance,
        "equity": account_info.equity,
        "leverage": account_info.leverage,
    })


def op_shutdown(args: dict) -> bool:
    mt5 = import_mt5()
    mt5.shutdown()
    output(True, data={"shutdown": True})


def op_account_info(args: dict) -> bool:
    mt5 = import_mt5()

    account_info = mt5.account_info()
    if account_info is None:
        output(False, error=f"mt5.account_info failed: {mt5.last_error()}")

    # Get open positions count
    positions = mt5.positions_get()
    open_count = len(positions) if positions else 0

    output(True, data={
        "login": account_info.login,
        "balance": account_info.balance,
        "equity": account_info.equity,
        "margin": account_info.margin,
        "free_margin": account_info.margin_free,
        "currency": account_info.currency,
        "leverage": account_info.leverage,
        "server": account_info.server,
        "name": account_info.name,
        "open_positions": open_count,
    })


def op_place_order(args: dict) -> bool:
    mt5 = import_mt5()

    symbol = args.get("symbol", "")
    side = args.get("side", "buy").lower()
    order_type = args.get("order_type", "market").lower()
    quantity = float(args.get("quantity", 0))
    price = args.get("price", 0)
    sl = args.get("sl", 0)
    tp = args.get("tp", 0)
    comment = args.get("comment", "TNSVT")
    magic = int(args.get("magic", 0))
    deviation = int(args.get("deviation", 20))

    if not symbol or quantity <= 0:
        output(False, error="symbol and quantity are required")

    # Validate symbol is visible
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        output(False, error=f"symbol {symbol} not found: {mt5.last_error()}")

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            output(False, error=f"failed to select symbol {symbol}")

    # Normalize volume (volume step)
    volume_step = symbol_info.volume_step
    quantity = round(quantity / volume_step) * volume_step

    # Min/max volume
    if quantity < symbol_info.volume_min:
        output(False, error=f"quantity {quantity} below min {symbol_info.volume_min}")
    if quantity > symbol_info.volume_max:
        output(False, error=f"quantity {quantity} above max {symbol_info.volume_max}")

    # Build order request
    order_type_mt5 = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": quantity,
        "type": order_type_mt5,
        "deviation": deviation,
        "magic": magic,
        "comment": comment[:31],  # MT5 max 31 chars
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,  # O cambiar a IOC si tu broker no soporta FOK
    }

    if sl > 0:
        request["sl"] = float(sl)
    if tp > 0:
        request["tp"] = float(tp)
    if order_type == "limit" and price > 0:
        request["type"] = mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else mt5.ORDER_TYPE_SELL_LIMIT
        request["price"] = float(price)

    log.info(f"Placing order: {side} {quantity} {symbol} @ market (magic={magic})")

    result = mt5.order_send(request)

    if result is None:
        output(False, error=f"order_send returned None: {mt5.last_error()}")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        output(False, error=f"order failed: retcode={result.retcode}, comment={result.comment}",
               data={
                   "retcode": result.retcode,
                   "comment": result.comment,
                   "request": request,
               })

    output(True, data={
        "order_id": str(result.order),
        "ticket": str(result.order),
        "filled_price": result.price,
        "filled_qty": result.volume,
        "commission": 0.0,  # Se obtiene después del deal
        "accepted": True,
    })


def op_close_position(args: dict) -> bool:
    mt5 = import_mt5()

    ticket = args.get("ticket", "")
    if not ticket:
        output(False, error="ticket is required")

    ticket_int = int(ticket)

    # Get position info
    positions = mt5.positions_get(ticket=ticket_int)
    if not positions:
        output(False, error=f"position {ticket} not found")

    position = positions[0]

    # Determine close direction (opposite of open)
    if position.type == mt5.ORDER_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = mt5.symbol_info_tick(position.symbol).bid
    else:
        order_type = mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(position.symbol).ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "position": ticket_int,
        "deviation": 20,
        "magic": position.magic,
        "comment": "TNSVT close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    log.info(f"Closing position {ticket}: {position.symbol} {position.volume}")

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        error_msg = result.comment if result else mt5.last_error()
        output(False, error=f"close failed: {error_msg}")

    # Calculate PnL
    if position.type == mt5.ORDER_TYPE_BUY:
        pnl = (result.price - position.price_open) * position.volume * position.volume
    else:
        pnl = (position.price_open - result.price) * position.volume * position.volume

    output(True, data={
        "ticket": str(result.order),
        "closed": True,
        "exit_price": result.price,
        "pnl": pnl,
    })


def op_modify_position(args: dict) -> bool:
    mt5 = import_mt5()

    ticket = args.get("ticket", "")
    sl = args.get("sl", 0)
    tp = args.get("tp", 0)

    if not ticket:
        output(False, error="ticket is required")

    ticket_int = int(ticket)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket_int,
    }
    if sl > 0:
        request["sl"] = float(sl)
    if tp > 0:
        request["tp"] = float(tp)

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        error_msg = result.comment if result else mt5.last_error()
        output(False, error=f"modify failed: {error_msg}")

    output(True, data={"modified": True, "ticket": ticket})


def op_positions_get(args: dict) -> bool:
    mt5 = import_mt5()

    magic = args.get("magic", 0)

    if magic > 0:
        positions = mt5.positions_get()
        # Filtrar por magic number
        if positions:
            positions = [p for p in positions if p.magic == magic]
    else:
        positions = mt5.positions_get()

    pos_list = []
    if positions:
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            current_price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask

            pos_list.append({
                "ticket": str(p.ticket),
                "symbol": p.symbol,
                "side": "buy" if p.type == mt5.ORDER_TYPE_BUY else "sell",
                "quantity": p.volume,
                "open_price": p.price_open,
                "current_price": current_price,
                "stop_loss": p.sl,
                "take_profit": p.tp,
                "pnl": p.profit,
                "swap": p.swap,
                "commission": p.commission,
                "opened_at": datetime.fromtimestamp(p.time).isoformat(),
                "magic": p.magic,
                "comment": p.comment,
            })

    output(True, data={"positions": pos_list, "count": len(pos_list)})


def op_symbol_info(args: dict) -> bool:
    mt5 = import_mt5()

    symbol = args.get("symbol", "")
    if not symbol:
        output(False, error="symbol is required")

    info = mt5.symbol_info(symbol)
    if info is None:
        output(False, error=f"symbol {symbol} not found: {mt5.last_error()}")

    output(True, data={
        "symbol": info.name,
        "digits": info.digits,
        "point": info.point,
        "trade_contract_size": info.trade_contract_size,
        "volume_min": info.volume_min,
        "volume_max": info.volume_max,
        "volume_step": info.volume_step,
        "spread": info.spread,
        "visible": info.visible,
        "trade_mode": info.trade_mode,
    })


# ─── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MT5 Bridge for TNSVT V2")
    parser.add_argument("operation", help="Operation: initialize, shutdown, place_order, etc.")
    parser.add_argument("--json", default="{}", help="JSON arguments")

    args = parser.parse_args()

    try:
        op_args = json.loads(args.json)
    except json.JSONDecodeError as e:
        output(False, error=f"invalid JSON: {e}")

    # Dispatch
    ops = {
        "initialize": op_initialize,
        "shutdown": op_shutdown,
        "account_info": op_account_info,
        "place_order": op_place_order,
        "close_position": op_close_position,
        "modify_position": op_modify_position,
        "positions_get": op_positions_get,
        "symbol_info": op_symbol_info,
    }

    handler = ops.get(args.operation)
    if not handler:
        output(False, error=f"unknown operation: {args.operation}")

    try:
        handler(op_args)
    except Exception as e:
        log.exception("Operation failed")
        output(False, error=f"exception: {str(e)}")


if __name__ == "__main__":
    main()