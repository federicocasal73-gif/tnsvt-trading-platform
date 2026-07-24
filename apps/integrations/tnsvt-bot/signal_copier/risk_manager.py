"""
Signal Copier - Gestor de Riesgo
"""
import MetaTrader5 as mt5
import datetime
import json
import os
import logging
from config import settings

logger = logging.getLogger("SignalCopier.RiskManager")

STATE_FILE = "signal_copier/risk_state.json"

# Pares correlacionados por defecto (grupos)
DEFAULT_CORRELATION_GROUPS = [
    ["EURUSD", "GBPUSD"],
    ["USDJPY", "USDCHF"],
    ["XAUUSD", "USDCAD"],
    ["GBPJPY", "EURJPY"],
    ["AUDUSD", "NZDUSD"],
    ["GBPJPY", "GBPUSD"],
]


class RiskManager:
    """Gestion de riesgo para el copiador de senales"""

    def __init__(self):
        self.state = self._load_state()
        self.reload_config()

    def reload_config(self):
        """Recarga la configuración desde .env + override con config.json del bot.

        Prioridad: config.json (UI del bot) > .env (defaults del sistema).
        Asi el usuario puede setear limites desde el panel Mt5Settings
        sin necesidad de editar el .env manualmente.
        """
        from config import settings
        from pathlib import Path
        import json

        self.config = {
            "daily_loss_limit": settings.RISK_DAILY_LOSS_LIMIT,
            "daily_profit_target": settings.RISK_DAILY_PROFIT_TARGET,
            "weekly_loss_limit": settings.RISK_WEEKLY_LOSS_LIMIT,
            "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
            "trailing_stop": settings.RISK_TRAILING_STOP,
            "trailing_step": settings.RISK_TRAILING_STEP,
            "trailing_start": settings.RISK_TRAILING_START,
            "max_trades_per_day": settings.RISK_MAX_TRADES_PER_DAY,
            "breakeven_enabled": settings.RISK_BREAKEVEN_ENABLED,
            "breakeven_pips": settings.RISK_BREAKEVEN_PIPS,
            "correlation_guard": settings.RISK_CORRELATION_GUARD_ENABLED,
            "correlation_groups": settings.RISK_CORRELATION_PAIRS or DEFAULT_CORRELATION_GROUPS,
            "max_hold_hours": settings.RISK_MAX_HOLD_HOURS,
            "close_on_friday": settings.RISK_CLOSE_ON_FRIDAY,
            "no_open_after": settings.RISK_NO_OPEN_AFTER,
            "scaleout_enabled": settings.SCALEOUT_ENABLED,
            "scaleout_levels": settings.SCALEOUT_LEVELS,
        }

        # Override con config.json del bot (path configurable via env BOT_DATA_DIR)
        bot_data_dir = os.getenv("BOT_DATA_DIR", r"D:\TradingBotMT5")
        cfg_path = Path(bot_data_dir) / "config.json"
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                risk = cfg.get("risk_management") or {}
                trailing = cfg.get("trailing_stop") or {}

                if "max_trades_per_day" in risk:
                    self.config["max_trades_per_day"] = int(risk["max_trades_per_day"])
                if "daily_loss_limit" in risk:
                    self.config["daily_loss_limit"] = float(risk["daily_loss_limit"])
                if "daily_profit_target" in risk:
                    self.config["daily_profit_target"] = float(risk["daily_profit_target"])
                if "weekly_loss_limit" in risk:
                    self.config["weekly_loss_limit"] = float(risk["weekly_loss_limit"])
                if "max_open_positions" in risk:
                    self.config["max_open_positions"] = int(risk["max_open_positions"])
                if "breakeven_enabled" in risk:
                    self.config["breakeven_enabled"] = bool(risk["breakeven_enabled"])
                if "breakeven_pips" in risk:
                    self.config["breakeven_pips"] = float(risk["breakeven_pips"])
                if "correlation_guard" in risk:
                    self.config["correlation_guard"] = bool(risk["correlation_guard"])
                if "max_hold_hours" in risk:
                    self.config["max_hold_hours"] = int(risk["max_hold_hours"])
                if "close_on_friday" in risk:
                    self.config["close_on_friday"] = bool(risk["close_on_friday"])

                scaleout = cfg.get("scale_out") or cfg.get("scaleout") or {}
                if "enabled" in scaleout:
                    self.config["scaleout_enabled"] = bool(scaleout["enabled"])
                if "levels" in scaleout and isinstance(scaleout["levels"], list):
                    valid = [
                        l for l in scaleout["levels"]
                        if isinstance(l, dict) and l.get("pips", 0) > 0 and l.get("percent", 0) > 0
                    ]
                    if valid:
                        self.config["scaleout_levels"] = valid

                if "enabled" in trailing:
                    self.config["trailing_stop"] = bool(trailing["enabled"])
                if "start_pips" in trailing:
                    self.config["trailing_start"] = float(trailing["start_pips"])
                if "step_pips" in trailing:
                    self.config["trailing_step"] = float(trailing["step_pips"])

                logger.debug(f"RiskManager: config.json aplicado ({cfg_path})")
            except Exception as e:
                logger.error(f"Error leyendo {cfg_path}: {e}")

        logger.info(
            f"RiskManager config recargada (max_trades_per_day="
            f"{self.config['max_trades_per_day']}, "
            f"breakeven={self.config['breakeven_enabled']}, "
            f"correlation={self.config['correlation_guard']}, "
            f"scaleout={self.config['scaleout_enabled']})"
        )

    def _load_state(self) -> dict:
        """Carga el estado del risk manager"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando estado: {e}")

        return {
            "daily_pnl": 0,
            "weekly_pnl": 0,
            "monthly_pnl": 0,
            "trades_today": 0,
            "last_reset_date": "",
            "last_week_reset": "",
            "last_month_reset": "",
            "total_trades": 0,
            "winning_trades": 0,
        }

    def _save_state(self):
        """Guarda el estado del risk manager (escritura atómica)"""
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            temp_file = STATE_FILE + ".tmp"
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=4)
            os.replace(temp_file, STATE_FILE)
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")

    def _reset_daily_if_needed(self):
        """Resetea contadores diarios, semanales (lunes) y mensuales (dia 1)."""
        today = datetime.date.today()
        today_iso = today.isoformat()

        if self.state.get("last_reset_date") != today_iso:
            logger.info(f"Reseteando contadores diarios para {today_iso}")
            self.state["daily_pnl"] = 0
            self.state["trades_today"] = 0
            self.state["last_reset_date"] = today_iso

            # Reset semanal si es lunes (weekday() == 0)
            if today.weekday() == 0:
                logger.info("Reseteando contadores semanales (lunes)")
                self.state["weekly_pnl"] = 0
                self.state["last_week_reset"] = today_iso

            # Reset mensual si es dia 1 del mes
            if today.day == 1:
                logger.info("Reseteando contadores mensuales (dia 1)")
                self.state["monthly_pnl"] = 0
                self.state["last_month_reset"] = today_iso

            self._save_state()

    def can_open_trade(self) -> tuple[bool, str]:
        """Verifica si se puede abrir una nueva operacion"""
        self._reset_daily_if_needed()

        # Verificar posiciones abiertas
        try:
            positions = mt5.positions_get()
            if positions and len(positions) >= self.config["max_open_positions"]:
                msg = f"Maximo de posiciones ({self.config['max_open_positions']}) alcanzado"
                logger.warning(msg)
                return False, msg
        except Exception as e:
            logger.error(f"Error verificando posiciones: {e}")

        # Verificar maximo de trades por dia (0 = ilimitado)
        max_n = int(self.config.get("max_trades_per_day", 0))
        if max_n > 0 and self.state.get("trades_today", 0) >= max_n:
            msg = (f"Limite diario de trades alcanzado "
                   f"({self.state['trades_today']}/{max_n})")
            logger.warning(msg)
            return False, msg

        # Verificar perdida diaria
        try:
            account = mt5.account_info()
            if account:
                balance = account.balance
                daily_loss_abs = (self.config["daily_loss_limit"] / 100) * balance

                float_pnl = self.state["daily_pnl"]

                open_positions = mt5.positions_get() or []
                open_risk = sum(abs(float(getattr(p, 'profit', 0) or 0)) for p in open_positions)
                total_risk = abs(float_pnl) + open_risk if float_pnl < 0 else open_risk

                if total_risk >= daily_loss_abs:
                    msg = (f"Limite de perdida diaria alcanzado "
                           f"({self.config['daily_loss_limit']}%) "
                           f"incluyendo riesgo abierto")
                    logger.warning(msg)
                    return False, msg

                if float_pnl <= -daily_loss_abs:
                    msg = f"Limite de perdida diaria alcanzado ({self.config['daily_loss_limit']}%)"
                    logger.warning(msg)
                    return False, msg

                # Verificar perdida semanal
                weekly_loss_abs = (self.config["weekly_loss_limit"] / 100) * balance
                if self.state["weekly_pnl"] <= -weekly_loss_abs:
                    msg = f"Limite de perdida semanal alcanzado ({self.config['weekly_loss_limit']}%)"
                    logger.warning(msg)
                    return False, msg

        except Exception as e:
            logger.error(f"Error verificando cuenta: {e}")

        return True, "OK"

    def increment_trades_today(self):
        """Incrementa el contador de trades del dia (al abrir, no al cerrar).

        Llamado desde main.py cuando una senal ejecuta OK.
        """
        self._reset_daily_if_needed()
        self.state["trades_today"] = self.state.get("trades_today", 0) + 1
        self.state["total_trades"] = self.state.get("total_trades", 0) + 1
        self._save_state()
        max_n = int(self.config.get("max_trades_per_day", 0))
        logger.info(
            f"Trades hoy: {self.state['trades_today']}"
            + (f"/{max_n}" if max_n > 0 else "")
        )

    def check_correlation(self, symbol: str, action: str) -> tuple[bool, str]:
        """Verifica que no haya posiciones abiertas correlacionadas en direccion opuesta.

        Grupos de pares correlacionados: si ya tenemos EURUSD BUY y llega GBPUSD SELL,
        se bloquea porque van en direccion opuesta y se cancelan entre si.

        Returns: (ok, reason)
        """
        if not self.config.get("correlation_guard"):
            return True, ""

        groups = self.config.get("correlation_groups", [])
        if not groups:
            return True, ""

        symbol_up = symbol.upper()
        my_group = None
        for group in groups:
            if any(symbol_up == p.upper() for p in group):
                my_group = group
                break

        if not my_group:
            return True, ""

        try:
            positions = mt5.positions_get(magic=20260706) or []
        except Exception:
            return True, ""

        for pos in positions:
            pos_sym = pos.symbol.upper()
            if pos_sym == symbol_up:
                continue
            if pos_sym not in my_group:
                continue

            pos_action = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
            if pos_action != action.upper():
                related = [p for p in my_group if p.upper() != symbol_up]
                return False, (
                    f"Correlacion opuesta: {symbol} {action} vs {pos_sym} {pos_action} "
                    f"en grupo {', '.join(my_group)}"
                )

        return True, ""

    def can_open_now(self) -> tuple[bool, str]:
        """Verifica si la hora actual permite abrir nuevas posiciones."""
        from signal_copier.time_exit import can_open_now as _can_open_now
        return _can_open_now(self.config)

    def check_daily_trade_limit(self) -> tuple[bool, str]:
        """Verifica si todavía se puede tradear hoy segun el limite diario."""
        self._reset_daily_if_needed()
        max_n = int(self.config.get("max_trades_per_day", 0))
        if max_n <= 0:
            return True, ""
        used = self.state.get("trades_today", 0)
        if used >= max_n:
            return False, f"limite diario {used}/{max_n}"
        return True, ""

    def update_pnl(self, pnl: float):
        """Actualiza el PnL al CERRAR un trade. NO incrementa trades_today
        (eso se hace en increment_trades_today al abrir el trade).
        """
        self._reset_daily_if_needed()

        self.state["daily_pnl"] += pnl
        self.state["weekly_pnl"] += pnl
        self.state["monthly_pnl"] = self.state.get("monthly_pnl", 0) + pnl
        self.state["total_trades"] += 1

        if pnl > 0:
            self.state["winning_trades"] += 1

        self._save_state()
        logger.info(
            f"PnL actualizado: {pnl:.2f} | Diario: {self.state['daily_pnl']:.2f}"
        )

    def get_status(self) -> dict:
        """Obtiene el estado actual del risk manager"""
        self._reset_daily_if_needed()

        account = mt5.account_info()
        balance = account.balance if account else 0

        return {
            "daily_pnl": round(self.state["daily_pnl"], 2),
            "weekly_pnl": round(self.state["weekly_pnl"], 2),
            "monthly_pnl": round(self.state.get("monthly_pnl", 0), 2),
            "trades_today": self.state["trades_today"],
            "total_trades": self.state["total_trades"],
            "winning_trades": self.state["winning_trades"],
            "win_rate": round(
                (self.state["winning_trades"] / self.state["total_trades"] * 100)
                if self.state["total_trades"] > 0
                else 0,
                2,
            ),
            "daily_limit_pct": self.config["daily_loss_limit"],
            "weekly_limit_pct": self.config["weekly_loss_limit"],
            "max_positions": self.config["max_open_positions"],
            "max_trades_per_day": self.config.get("max_trades_per_day", 0),
            "balance": balance,
            "daily_loss_remaining": round(
                (self.config["daily_loss_limit"] / 100 * balance)
                + self.state["daily_pnl"],
                2,
            ),
            "breakeven_enabled": self.config.get("breakeven_enabled", False),
            "breakeven_pips": self.config.get("breakeven_pips", 8.0),
            "correlation_guard": self.config.get("correlation_guard", False),
            "max_hold_hours": self.config.get("max_hold_hours", 48),
            "close_on_friday": self.config.get("close_on_friday", False),
            "no_open_after": self.config.get("no_open_after", ""),
        }

    def check_trailing_stop(self, symbol: str):
        """Verifica y actualiza trailing stop"""
        if not self.config["trailing_stop"]:
            return

        try:
            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                return

            for pos in positions:
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    continue

                current_price = (
                    tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
                )

                # Calcular ganancia en puntos
                if pos.type == mt5.ORDER_TYPE_BUY:
                    profit_points = current_price - pos.price_open
                else:
                    profit_points = pos.price_open - current_price

                # Activar trailing stop
                if profit_points >= self.config["trailing_start"]:
                    if pos.type == mt5.ORDER_TYPE_BUY:
                        new_sl = current_price - self.config["trailing_step"]
                    else:
                        new_sl = current_price + self.config["trailing_step"]

                    # Solo mover si el nuevo SL es mejor
                    if pos.sl == 0 or (
                        pos.type == mt5.ORDER_TYPE_BUY and new_sl > pos.sl
                    ) or (
                        pos.type == mt5.ORDER_TYPE_SELL and new_sl < pos.sl
                    ):
                        request = {
                            "action": mt5.TRADE_ACTION_SLTP,
                            "symbol": symbol,
                            "position": pos.ticket,
                            "sl": new_sl,
                            "tp": pos.tp,
                        }

                        result = mt5.order_send(request)
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(
                                f"Trailing stop actualizado: {symbol} SL {pos.sl:.5f} -> {new_sl:.5f}"
                            )

        except Exception as e:
            logger.error(f"Error en trailing stop: {e}")

    async def check_trailing_stop_async(self, symbol: str):
        """Wrapper async para trailing stop (no bloquear event loop)"""
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.check_trailing_stop, symbol)

    def reset_daily(self):
        """Resetea manualmente los contadores diarios"""
        self.state["daily_pnl"] = 0
        self.state["trades_today"] = 0
        self._save_state()
        logger.info("Contadores diarios reseteados manualmente")

    def reset_all(self):
        """Resetea todo el estado"""
        self.state = {
            "daily_pnl": 0,
            "weekly_pnl": 0,
            "monthly_pnl": 0,
            "trades_today": 0,
            "last_reset_date": "",
            "last_week_reset": "",
            "last_month_reset": "",
            "total_trades": 0,
            "winning_trades": 0,
        }
        self._save_state()
        logger.info("Estado del RiskManager reseteado completamente")
