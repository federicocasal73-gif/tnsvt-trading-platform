import MetaTrader5 as mt5
import config
import time
import database
from datetime import datetime, timedelta

class MT5Executor:
    def __init__(self):
        self.connected = False

    def connect(self):
        if not mt5.initialize():
            print("Error al iniciar MT5:", mt5.last_error())
            self.connected = False
            return False
        
        print(f"Conectado a MT5: {mt5.terminal_info().name}")
        self.connected = True
        return True

    def shutdown(self):
        mt5.shutdown()

    def check_risk_limits(self):
        """Verifica límites de Ganancia/Pérdida Diaria"""
        config.reload()
        risk = config._config.get("risk_management", {})
        if not any(risk.values()): return True
            
        account_info = mt5.account_info()
        if not account_info: return True
            
        deals = mt5.history_deals_get(datetime.now().replace(hour=0, minute=0, second=0), datetime.now())
        daily_profit = sum(d.profit + d.swap + d.commission for d in deals) if deals else 0.0
        
        start_balance = account_info.balance - daily_profit
        if start_balance == 0: start_balance = 1
        profit_pct = (daily_profit / start_balance) * 100
        
        if risk.get("active_daily_profit") and profit_pct >= risk.get("daily_profit_target", 2.0):
            print(f"⚠️ META DIARIA ALCANZADA ({profit_pct:.2f}%)")
            return False
        if risk.get("active_daily_loss") and profit_pct <= -risk.get("daily_loss_limit", 2.0):
            print(f"⛔ LÍMITE PÉRDIDA ALCANZADO ({profit_pct:.2f}%)")
            return False
        return True

    def _send_order_with_retry(self, request):
        for filling in [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
            request['type_filling'] = filling
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE: return result
            if result.retcode != 10030: return result
        return result

    def check_volume(self, symbol, vol):
        info = mt5.symbol_info(symbol)
        if not info: return False
        if vol < info.volume_min or vol > info.volume_max: return False
        return True

    def _profile_allows(self, ctx: dict, symbol: str) -> tuple[bool, str]:
        """Phase 2: ¿el ChannelProfile permite esta operación?"""
        # 1) Block list siempre gana
        channels = config._config.get("channels_data", [])
        ch_id = ctx.get("channel_id")
        profile = None
        for c in channels:
            if c.get("id") == ch_id and c.get("topic_id") == ctx.get("topic_id"):
                profile = c.get("profile")
                break
        if not profile:
            return True, ""  # sin profile = sin restricción

        block = profile.get("block_symbols") or []
        if symbol in block:
            return False, f"symbol {symbol} bloqueado por canal"

        allow = profile.get("allow_symbols") or []
        if allow and symbol not in allow:
            return False, f"symbol {symbol} no está en allow list"

        return True, ""

    def _check_position_count(self, ctx: dict, symbol: str) -> tuple[bool, str]:
        """Phase 2: ¿la nueva posición respeta max_positions?"""
        channels = config._config.get("channels_data", [])
        ch_id = ctx.get("channel_id")
        profile = None
        for c in channels:
            if c.get("id") == ch_id and c.get("topic_id") == ctx.get("topic_id"):
                profile = c.get("profile")
                break
        if not profile:
            return True, ""

        max_pos = profile.get("max_positions", 0)
        if max_pos <= 0:
            return True, ""

        # Si multi_same_symbol=False, validar también duplicado de símbolo
        if not profile.get("multi_same_symbol", True):
            cnt_symbol = sum(
                1
                for p in mt5.positions_get(symbol=symbol) or []
                if p.magic == 234000
            )
            if cnt_symbol >= 1:
                return False, f"multi_same_symbol=false y ya hay posición abierta en {symbol}"

        # Contar todas las posiciones abiertas por nosotros (cualquier símbolo)
        cnt = sum(1 for p in mt5.positions_get() or [] if p.magic == 234000)
        if cnt >= max_pos:
            return False, f"max_positions={max_pos} ya alcanzado"
        return True, ""

    def _check_spread(self, symbol: str, profile_limit_pips: int) -> tuple[bool, str]:
        """Phase 2: ¿el spread actual es aceptable?"""
        if profile_limit_pips <= 0:
            return True, ""
        info = mt5.symbol_info(symbol)
        if not info:
            return True, ""
        digits = info.digits
        pip = 10 ** (-(digits - 2)) if digits >= 3 else 0.01
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return True, ""
        spread = tick.ask - tick.bid
        if spread > pip * profile_limit_pips:
            return False, f"spread={spread/pip:.1f}pips > {profile_limit_pips}pips"
        return True, ""

    def _channel_profile(self, ctx: dict) -> dict | None:
        channels = config._config.get("channels_data", [])
        for c in channels:
            if c.get("id") == ctx.get("channel_id") and c.get("topic_id") == ctx.get("topic_id"):
                return c.get("profile")
        return None

    def execute_trade(self, signal):
        if not self.connected and not self.connect(): return False
        ctx = signal.get('_context', {}) or {}
        if not self.check_risk_limits():
            database.log_trade(signal['symbol'], "REJECTED_RISK", 0, 0, "", "Limit Reached", 0,
                               channel_id=ctx.get('channel_id'),
                               channel_title=ctx.get('channel_title'),
                               topic_id=ctx.get('topic_id'))
            return False

        # Phase 2: aplicar ChannelProfile (allow/block/multi/max/spread)
        profile = self._channel_profile(ctx)
        if profile:
            base_symbol_check = signal['symbol']
            ok, reason = self._profile_allows(ctx, base_symbol_check)
            if not ok:
                database.log_trade(base_symbol_check, "REJECTED_PROFILE", 0, 0, "", reason, 0,
                                   channel_id=ctx.get('channel_id'),
                                   channel_title=ctx.get('channel_title'),
                                   topic_id=ctx.get('topic_id'))
                return False
            ok, reason = self._check_position_count(ctx, base_symbol_check)
            if not ok:
                database.log_trade(base_symbol_check, "REJECTED_PROFILE", 0, 0, "", reason, 0,
                                   channel_id=ctx.get('channel_id'),
                                   channel_title=ctx.get('channel_title'),
                                   topic_id=ctx.get('topic_id'))
                return False

        # --- SMART SYMBOL RESOLVER ---
        base_symbol = signal['symbol']
        # Intento 1: Símbolo Directo
        target_symbol = base_symbol
        if not mt5.symbol_info(target_symbol):
            # Intento 2: Usar Sufijo Configurado (si existe)
            if config.SYMBOL_SUFFIX:
                target_symbol = base_symbol + config.SYMBOL_SUFFIX
            
            # Intento 3: Auto-Discovery Optimizado
            if not mt5.symbol_info(target_symbol):
                print(f"🔎 Buscando par real para '{base_symbol}' en MT5...")
                # Usar filtro para no descargar miles de símbolos (ej. "EURUSD*")
                matches = mt5.symbols_get(group=f"*{base_symbol}*")
                found = False
                if matches:
                    for s in matches:
                        # Priorizar coincidencia exacta al inicio y longitud lógica
                        if s.name.startswith(base_symbol):
                             # Evitar símbolos raros muy largos si hay uno corto (ej preferir "EURUSD-T" sobre "EURUSD-T_pro_b")
                            target_symbol = s.name
                            found = True
                            print(f"✅ Auto-Detectado: Usando '{target_symbol}' en lugar de '{base_symbol}'")
                            break
                if not found:
                    print(f"❌ Error CRÍTICO: No existe '{base_symbol}' ni variantes en tu MT5.")
                    return False
        
        symbol = target_symbol
        action_type = signal['action']

        if not mt5.symbol_select(symbol, True): return False

        # Phase 2: spread check (post-symbol-resolve, sólo aperturas)
        if action_type in ('BUY', 'SELL') and profile:
            ok, reason = self._check_spread(symbol, profile.get('max_spread_pips', 0))
            if not ok:
                database.log_trade(symbol, "REJECTED_PROFILE", 0, 0, "", reason, 0,
                                   channel_id=ctx.get('channel_id'),
                                   channel_title=ctx.get('channel_title'),
                                   topic_id=ctx.get('topic_id'))
                return False

        # --- LÓGICA DE CIERRE ---
        if action_type == 'CLOSE':
            positions = mt5.positions_get(symbol=symbol)
            if not positions: return False
            for pos in positions:
                ot_close = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                p_close = mt5.symbol_info_tick(symbol).bid if ot_close == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask
                req = {
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": pos.volume,
                    "type": ot_close, "position": pos.ticket, "price": p_close,
                    "deviation": config.DEVIATION, "magic": 234000, "comment": "Close Bot"
                }
                self._send_order_with_retry(req)
            return True

        # --- LÓGICA DE APERTURA ---
        # 1. Determinar Lotaje (Fijo o Dinámico)
        lot = config.LOT_SIZE
        if config._config.get("lot_mode") == "PERCENTAGE":
            acc = mt5.account_info()
            if acc:
                # Fórmula Estándar: (Balance * %) / 100,000
                # Ej: $10,000 * 1% -> (10,000 * 1) / 100,000 = 0.10 lots.
                raw_lot = (acc.balance * config._config.get("lot_percentage", 0.5)) / 100000
                lot = raw_lot
                print(f"💰 Lotaje Dinámico Sugerido: {lot:.4f} ({config._config.get('lot_percentage')}% de {acc.balance})")

        # 2. Corregir Volumen (Error 10014 Prevention)
        sym_info = mt5.symbol_info(symbol)
        if sym_info:
            if lot < sym_info.volume_min: lot = sym_info.volume_min
            if lot > sym_info.volume_max: lot = sym_info.volume_max
            # Normalizar al paso (step)
            step = sym_info.volume_step
            lot = round(lot / step) * step
            lot = round(lot, 2) # Limpieza final

        order_type = mt5.ORDER_TYPE_BUY if action_type == 'BUY' else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if action_type == 'BUY' else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "deviation": config.DEVIATION,
            "magic": 234000,
            "comment": "T-Bot Signal",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        if signal['sl']: request["sl"] = signal['sl']
        if signal['tp']: request["tp"] = signal['tp'][0]

        result = self._send_order_with_retry(request)

        status = "EXECUTED" if result.retcode == mt5.TRADE_RETCODE_DONE else f"FAIL: {result.comment}"
        database.log_trade(symbol, action_type, result.price if result.retcode == mt5.TRADE_RETCODE_DONE else price,
                           signal['sl'], signal['tp'][0] if signal['tp'] else 0, status,
                           result.order if result.retcode == mt5.TRADE_RETCODE_DONE else 0,
                           channel_id=ctx.get('channel_id'),
                           channel_title=ctx.get('channel_title'),
                           topic_id=ctx.get('topic_id'))

        # ─── TNSVT INTEGRATION: publicar a bridge con garantía de cola ───
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            self._publish_to_tnsvt(
                symbol=symbol,
                action=action_type,
                volume=lot,
                price=result.price,
                sl=signal.get("sl"),
                tp=signal.get("tp", [None])[0] if signal.get("tp") else None,
                ticket=result.order,
                comment=result.comment or "T-Bot Signal",
                channel_id=ctx.get('channel_id'),
                channel_title=ctx.get('channel_title'),
                topic_id=ctx.get('topic_id'),
            )
            print(f"✅ Orden ejecutada: {action_type} {symbol} @ {result.price} (Lote: {lot})")
        else:
            print(f"❌ Error MT5: {result.comment}")

        return result.retcode == mt5.TRADE_RETCODE_DONE

    def _publish_to_tnsvt(
        self,
        symbol: str,
        action: str,
        volume: float,
        price: float,
        sl: float = None,
        tp: float = None,
        ticket: int = None,
        comment: str = None,
        channel_id: int = None,
        channel_title: str = None,
        topic_id: int = None,
    ) -> None:
        """Encola la orden en SQLite local para publicarla al bridge TNSVT.

        Garantía:
        - Insert ANTES de intentar POST, así si el bridge está caído la
          orden queda persistida y el outbox_worker la reintenta.
        - POST síncrono con timeout corto: si responde OK, marca delivered.
        - Si falla, el worker daemon (outbox_worker.OutboxWorker) reintenta
          con backoff hasta que el bridge esté disponible.
        """
        payload = {
            "symbol": symbol,
            "action": action,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "ticket": ticket,
            "comment": comment,
            "source": "telegram-bot",
            "channel_id": channel_id,
            "channel_title": channel_title,
            "topic_id": topic_id,
        }
        # 1. Persistir localmente (siempre primero)
        try:
            event_id = database.enqueue_bridge_event(payload, source="mt5-bot")
            print(f"📤 TNSVT: orden encolada #{event_id} ({action} {symbol})")
        except Exception as e:
            print(f"⚠️ TNSVT: no se pudo encolar en SQLite local: {e}")
            return

        # 2. Intentar POST síncrono al bridge (rápido)
        import requests
        bridge_url = config._config.get(
            "bridge_url", "http://localhost:8522"
        ) + "/api/v1/bridge/mt5/order"
        try:
            r = requests.post(bridge_url, json=payload, timeout=2)
            if r.status_code < 500:
                database.mark_bridge_delivered(event_id)
                print(f"✅ TNSVT: orden #{event_id} entregada (HTTP {r.status_code})")
            else:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                database.mark_bridge_failed(event_id, err, 1)
                print(f"⚠️ TNSVT: bridge devolvió {r.status_code}, worker reintentará")
        except requests.RequestException as e:
            err = f"{type(e).__name__}: {e}"
            database.mark_bridge_failed(event_id, err, 1)
            print(f"⚠️ TNSVT: bridge no alcanzable ({err[:80]}), worker reintentará")
