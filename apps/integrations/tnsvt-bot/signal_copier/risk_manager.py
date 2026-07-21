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


class RiskManager:
    """Gestion de riesgo para el copiador de senales"""

    def __init__(self):
        self.config = {
            "daily_loss_limit": settings.RISK_DAILY_LOSS_LIMIT,
            "daily_profit_target": settings.RISK_DAILY_PROFIT_TARGET,
            "weekly_loss_limit": settings.RISK_WEEKLY_LOSS_LIMIT,
            "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
            "trailing_stop": settings.RISK_TRAILING_STOP,
            "trailing_step": settings.RISK_TRAILING_STEP,
            "trailing_start": settings.RISK_TRAILING_START,
        }
        self.state = self._load_state()
        logger.info("RiskManager inicializado")

    def reload_config(self):
        """Recarga la configuración desde .env"""
        from config import settings
        self.config = {
            "daily_loss_limit": settings.RISK_DAILY_LOSS_LIMIT,
            "daily_profit_target": settings.RISK_DAILY_PROFIT_TARGET,
            "weekly_loss_limit": settings.RISK_WEEKLY_LOSS_LIMIT,
            "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
            "trailing_stop": settings.RISK_TRAILING_STOP,
            "trailing_step": settings.RISK_TRAILING_STEP,
            "trailing_start": settings.RISK_TRAILING_START,
        }
        logger.info("RiskManager configuración recargada")

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
            "trades_today": 0,
            "last_reset_date": "",
            "last_week_reset": "",
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
        """Resetea contadores diarios si es necesario"""
        today = datetime.date.today().isoformat()

        if self.state.get("last_reset_date") != today:
            logger.info(f"Reseteando contadores diarios para {today}")
            self.state["daily_pnl"] = 0
            self.state["trades_today"] = 0
            self.state["last_reset_date"] = today

            # Reset semanal si es lunes
            if datetime.date.today().weekday() == 0:
                logger.info("Reseteando contadores semanales (lunes)")
                self.state["weekly_pnl"] = 0
                self.state["last_week_reset"] = today

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

    def update_pnl(self, pnl: float):
        """Actualiza el PnL"""
        self._reset_daily_if_needed()

        self.state["daily_pnl"] += pnl
        self.state["weekly_pnl"] += pnl
        self.state["trades_today"] += 1
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
            "balance": balance,
            "daily_loss_remaining": round(
                (self.config["daily_loss_limit"] / 100 * balance)
                + self.state["daily_pnl"],
                2,
            ),
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
            "trades_today": 0,
            "last_reset_date": "",
            "last_week_reset": "",
            "total_trades": 0,
            "winning_trades": 0,
        }
        self._save_state()
        logger.info("Estado del RiskManager reseteado completamente")
