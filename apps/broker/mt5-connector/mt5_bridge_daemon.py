#!/usr/bin/env python3
"""
TNSVT V2 - MT5 Bridge Daemon
Persistent process that keeps MT5 connection alive across multiple operations.
Avoids subprocess spawn overhead and MT5 connection conflicts.

Usage:
    python mt5_bridge_daemon.py --serve --port 8008
    python mt5_bridge_daemon.py --initialize --path "C:\\..." --login X --password X --server "X"
    python mt5_bridge_daemon.py --shutdown
"""

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] MT5Daemon: %(message)s"
)
log = logging.getLogger("MT5Daemon")


def import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        log.critical("MetaTrader5 library not installed (pip install MetaTrader5)")
        sys.exit(1)


DAEMON_STATE = {
    "mt5": None,
    "connected": False,
    "initialized": False,
    "login": 0,
    "server": "",
    "path": "",
    "password": "",
    "shutdown_requested": False,
}


def ensure_mt5():
    mt5 = import_mt5()
    if DAEMON_STATE["mt5"] is None:
        DAEMON_STATE["mt5"] = mt5
    return mt5


def is_connected():
    mt5 = ensure_mt5()
    return DAEMON_STATE["initialized"] and mt5.terminal_info() is not None


class MT5Handler(BaseHTTPRequestHandler):
    daemon_run = True

    def log_message(self, format, *args):
        log.info("%s - %s", self.client_address[0], format % args)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    def _json_response(self, status_code, success, data=None, error=""):
        body = json.dumps({"success": success, "data": data or {}, "error": error})
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._handle_health()
        elif path == "/health/ready":
            self._handle_health_ready()
        elif path.startswith("/mt5/account_info"):
            self._handle_account_info()
        elif path.startswith("/mt5/positions"):
            self._handle_positions()
        elif path.startswith("/mt5/rates"):
            self._handle_rates()
        elif path.startswith("/mt5/symbol_info"):
            self._handle_symbol_info()
        else:
            self._json_response(404, False, error="endpoint not found")

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        if path == "/mt5/initialize":
            self._handle_initialize(body)
        elif path == "/mt5/place_order":
            self._handle_place_order(body)
        elif path == "/mt5/close_position":
            self._handle_close_position(body)
        elif path == "/mt5/modify_position":
            self._handle_modify_position(body)
        elif path == "/mt5/shutdown":
            self._handle_shutdown()
        else:
            self._json_response(404, False, error="endpoint not found")

    def _handle_health(self):
        mt5 = ensure_mt5()
        connected = is_connected()
        status = "ok" if connected else "degraded"
        info = {
            "mt5": "connected" if connected else "disconnected",
            "service": "mt5-bridge-daemon",
            "status": status,
            "initialized": DAEMON_STATE["initialized"],
        }
        code = 200 if connected else 503
        self._json_response(code, connected, data=info)

    def _handle_health_ready(self):
        mt5 = ensure_mt5()
        connected = is_connected()
        code = 200 if connected else 503
        self._json_response(code, connected, data={"ready": connected})

    def _handle_initialize(self, body):
        if DAEMON_STATE["initialized"]:
            self._json_response(200, True, data={"message": "already initialized", "reinitialized": True})
            return

        path = body.get("path", "")
        login = body.get("login", 0)
        password = body.get("password", "")
        server = body.get("server", "")

        if not path:
            self._json_response(400, False, error="path is required")
            return

        mt5 = ensure_mt5()
        DAEMON_STATE["path"] = path
        DAEMON_STATE["login"] = login
        DAEMON_STATE["password"] = password
        DAEMON_STATE["server"] = server

        if not mt5.initialize(path=path):
            DAEMON_STATE["last_error"] = mt5.last_error()
            self._json_response(503, False, error=f"mt5.initialize failed: {DAEMON_STATE['last_error']}")
            return

        if login and password and server:
            if not mt5.login(login=int(login), password=password, server=server):
                DAEMON_STATE["last_error"] = mt5.last_error()
                mt5.shutdown()
                self._json_response(401, False, error=f"mt5.login failed: {DAEMON_STATE['last_error']}")
                return

        account_info = mt5.account_info()
        if account_info is None:
            DAEMON_STATE["last_error"] = mt5.last_error()
            mt5.shutdown()
            self._json_response(503, False, error=f"mt5.account_info failed: {DAEMON_STATE['last_error']}")
            return

        DAEMON_STATE["initialized"] = True
        DAEMON_STATE["connected"] = True
        log.info("MT5 daemon initialized — login=%d server=%s", account_info.login, account_info.server)

        self._json_response(200, True, data={
            "login": account_info.login,
            "server": account_info.server,
            "name": account_info.name,
            "currency": account_info.currency,
            "balance": account_info.balance,
            "equity": account_info.equity,
            "leverage": account_info.leverage,
        })

    def _handle_place_order(self, body):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected — call /mt5/initialize first")
            return

        mt5 = ensure_mt5()
        symbol = body.get("symbol", "")
        side = body.get("side", "buy").lower()
        order_type = body.get("order_type", "market").lower()
        quantity = float(body.get("quantity", 0))
        price = body.get("price", 0)
        sl = body.get("sl", 0)
        tp = body.get("tp", 0)
        comment = body.get("comment", "TNSVT")
        magic = int(body.get("magic", 123456))
        deviation = int(body.get("deviation", 20))

        if not symbol or quantity <= 0:
            self._json_response(400, False, error="symbol and quantity are required")
            return

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self._json_response(404, False, error=f"symbol {symbol} not found")
            return

        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                self._json_response(503, False, error=f"failed to select symbol {symbol}")
                return

        volume_step = symbol_info.volume_step
        quantity = round(quantity / volume_step) * volume_step

        if quantity < symbol_info.volume_min or quantity > symbol_info.volume_max:
            self._json_response(400, False, error=f"quantity {quantity} outside valid range")
            return

        order_type_mt5 = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": quantity,
            "type": order_type_mt5,
            "deviation": deviation,
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }

        if order_type == "limit" and price > 0:
            request["type"] = mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else mt5.ORDER_TYPE_SELL_LIMIT
            request["price"] = float(price)

        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)

        log.info("Daemon placing order: %s %s %s", side, quantity, symbol)
        result = mt5.order_send(request)

        if result is None:
            self._json_response(503, False, error=f"order_send returned None: {mt5.last_error()}")
            return

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self._json_response(400, False,
                error=f"order failed: retcode={result.retcode}, comment={result.comment}",
                data={"retcode": result.retcode, "comment": result.comment})
            return

        self._json_response(200, True, data={
            "order_id": str(result.order),
            "ticket": str(result.order),
            "filled_price": result.price,
            "filled_qty": result.volume,
            "commission": 0.0,
            "accepted": True,
        })

    def _handle_close_position(self, body):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected")
            return

        mt5 = ensure_mt5()
        ticket = body.get("ticket", "")
        if not ticket:
            self._json_response(400, False, error="ticket required")
            return

        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            self._json_response(404, False, error=f"position {ticket} not found")
            return

        position = positions[0]
        if position.type == mt5.ORDER_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(position.symbol)
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(position.symbol)
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": order_type,
            "position": int(ticket),
            "deviation": 20,
            "magic": position.magic,
            "comment": "TNSVT close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
            "price": price,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else mt5.last_error()
            self._json_response(400, False, error=f"close failed: {error_msg}")
            return

        pnl = 0.0
        if position.type == mt5.ORDER_TYPE_BUY:
            pnl = (result.price - position.price_open) * position.volume
        else:
            pnl = (position.price_open - result.price) * position.volume

        self._json_response(200, True, data={
            "ticket": str(result.order),
            "closed": True,
            "exit_price": result.price,
            "pnl": pnl,
        })

    def _handle_modify_position(self, body):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected")
            return

        mt5 = ensure_mt5()
        ticket = body.get("ticket", "")
        sl = body.get("sl", 0)
        tp = body.get("tp", 0)

        if not ticket:
            self._json_response(400, False, error="ticket required")
            return

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
        }
        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = result.comment if result else mt5.last_error()
            self._json_response(400, False, error=f"modify failed: {error_msg}")
            return

        self._json_response(200, True, data={"modified": True, "ticket": ticket})

    def _handle_positions(self):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected")
            return

        mt5 = ensure_mt5()
        magic = int(urlparse(self.path).query.split("magic=")[1].split("&")[0]) if "magic=" in self.path else 0

        positions = mt5.positions_get() if not magic else [p for p in mt5.positions_get() if p.magic == magic]

        pos_list = []
        for p in (positions or []):
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
                "opened_at": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                "magic": p.magic,
                "comment": p.comment,
            })

        self._json_response(200, True, data={"positions": pos_list, "count": len(pos_list)})

    def _handle_rates(self):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected")
            return

        mt5 = ensure_mt5()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        symbol = params.get("symbol", [None])[0]
        timeframe_str = params.get("timeframe", ["M1"])[0]
        count = int(params.get("count", ["20"])[0])

        if not symbol:
            self._json_response(400, False, error="symbol required")
            return

        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1,
        }
        tf = timeframe_map.get(timeframe_str)
        if tf is None:
            self._json_response(400, False, error=f"unsupported timeframe: {timeframe_str}")
            return

        if not mt5.symbol_select(symbol, True):
            self._json_response(503, False, error=f"failed to select symbol {symbol}")
            return

        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None:
            self._json_response(503, False, error=f"copy_rates_from_pos failed: {mt5.last_error()}")
            return

        rate_list = []
        for r in rates:
            vol = float(r["real_volume"]) if r["real_volume"] > 0 else float(r["tick_volume"])
            rate_list.append({
                "symbol": symbol,
                "timeframe": timeframe_str,
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": vol,
                "tick_volume": float(r["tick_volume"]),
                "spread": int(r["spread"]),
            })

        self._json_response(200, True, data={"rates": rate_list, "count": len(rate_list)})

    def _handle_symbol_info(self):
        if not is_connected():
            self._json_response(503, False, error="MT5 not connected")
            return

        mt5 = ensure_mt5()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        symbol = params.get("symbol", [None])[0]

        if not symbol:
            self._json_response(400, False, error="symbol required")
            return

        info = mt5.symbol_info(symbol)
        if info is None:
            self._json_response(404, False, error=f"symbol {symbol} not found")
            return

        self._json_response(200, True, data={
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

    def _handle_shutdown(self):
        mt5 = ensure_mt5()
        mt5.shutdown()
        DAEMON_STATE["initialized"] = False
        DAEMON_STATE["connected"] = False
        DAEMON_STATE["shutdown_requested"] = True
        log.info("MT5 daemon shutdown requested")
        self._json_response(200, True, data={"shutdown": True})

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port=8008):
    server = HTTPServer(("0.0.0.0", port), MT5Handler)
    log.info("MT5 Bridge Daemon starting on port %d", port)

    def shutdown_handler(signum, frame):
        log.info("Shutdown signal received")
        DAEMON_STATE["shutdown_requested"] = True
        mt5 = ensure_mt5()
        if DAEMON_STATE["initialized"]:
            mt5.shutdown()
        server.shutdown()

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if DAEMON_STATE["initialized"]:
            ensure_mt5().shutdown()
        log.info("MT5 Bridge Daemon stopped")


def run_initialize(args):
    body = {
        "path": args.path,
        "login": args.login,
        "password": args.password,
        "server": args.server,
    }
    # We'll just initialize directly here
    mt5 = import_mt5()
    if not mt5.initialize(path=args.path):
        log.critical("mt5.initialize failed: %s", mt5.last_error())
        sys.exit(1)
    if args.login and args.password and args.server:
        if not mt5.login(login=args.login, password=args.password, server=args.server):
            log.critical("mt5.login failed: %s", mt5.last_error())
            mt5.shutdown()
            sys.exit(1)
    info = mt5.account_info()
    log.info("MT5 initialized — login=%d server=%s balance=%.2f", info.login, info.server, info.balance)


def main():
    parser = argparse.ArgumentParser(description="TNSVT V2 MT5 Bridge Daemon")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    serve_parser = subparsers.add_parser("serve", help="Run as persistent daemon")
    serve_parser.add_argument("--port", type=int, default=8008)

    init_parser = subparsers.add_parser("initialize", help="One-time initialize MT5")
    init_parser.add_argument("--path", required=True)
    init_parser.add_argument("--login", type=int, default=0)
    init_parser.add_argument("--password", default="")
    init_parser.add_argument("--server", default="")

    subparsers.add_parser("shutdown", help="Shutdown the daemon")

    args = parser.parse_args()

    if args.command == "serve":
        run_server(args.port)
    elif args.command == "initialize":
        run_initialize(args)
    elif args.command == "shutdown":
        log.info("Send SIGTERM to daemon process to shutdown")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
