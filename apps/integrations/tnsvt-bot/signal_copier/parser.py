"""
Signal Copier - Parser Ultra Flexible v2
Entiende CUALQUIER formato de señal
"""
import re
import logging

logger = logging.getLogger("SignalCopier.Parser")


class SignalParser:
    """Parsea señales de trading en cualquier formato"""

    BUY_WORDS = [
        "comprar", "compra", "buy", "long", "abrir compra", "abrir long",
        "entrada compra", "entrada long", "buy now", "buy now!", "comprar ahora",
        "ir long", "ir a long", "buy:"
    ]
    SELL_WORDS = [
        "vender", "venta", "sell", "short", "abrir venta", "abrir short",
        "entrada venta", "entrada short", "sell now", "sell now!", "vender ahora",
        "ir short", "ir a short", "sell:"
    ]
    CLOSE_WORDS = [
        "cerrar", "cierre", "close", "salir", "salida", "cerrar todo",
        "close all", "exit", "cambiar", "revertir"
    ]

    def __init__(self):
        self.pending_signal = None

    def parse_message(self, text: str, pending_signal: dict = None) -> dict:
        """Analiza cualquier formato de señal"""
        self.pending_signal = pending_signal
        original = text
        text_lower = text.lower().strip()
        
        signal = {
            "action": None,
            "symbol": None,
            "price": None,
            "price_range": None,  # Para rangos como "2990.50 - 2992.50"
            "sl": None,
            "tp": [],
            "lot": None,
            "is_update": False,
            "tp_percentages": [],  # Porcentajes para cada TP
        }

        # 1. Verificar si es solo SL/TP
        if self._is_sl_tp_update(text_lower):
            return self._parse_sl_tp_update(text, pending_signal)

        # 2. Detectar ACCIÓN
        signal["action"] = self._detect_action(text_lower, text)
        if not signal["action"]:
            return signal

        # 3. Detectar SÍMBOLO
        signal["symbol"] = self._detect_symbol(text, text_lower)
        if not signal["symbol"]:
            return signal

        # 4. Detectar precio (normal o rango)
        signal = self._detect_prices(text, signal)

        # 5. Detectar SL y TP
        signal = self._detect_sl_tp(text, signal)

        # 6. Calcular porcentajes para múltiples TP
        if len(signal["tp"]) > 1:
            signal["tp_percentages"] = self._calculate_tp_percentages(len(signal["tp"]))

        # 7. Detectar lote
        signal["lot"] = self._detect_lot(text_lower)

        logger.debug(f"Señal parseada: {signal}")
        return signal

    def _is_sl_tp_update(self, text: str) -> bool:
        """Verifica si es un mensaje de solo SL/TP"""
        sl_tp_indicators = ['sl', 'tp', 'stop', 'take', 'target', '@', 'stop loss', 'take profit']
        action_indicators = self.BUY_WORDS + self.SELL_WORDS + self.CLOSE_WORDS
        
        has_sl_tp = any(x in text for x in sl_tp_indicators)
        has_action = any(x in text for x in action_indicators)
        
        if has_sl_tp and not has_action:
            return True
        
        cleaned = text.strip()
        if not re.match(r'^[\d\s.,\-@]+$', cleaned):
            return False
        
        if re.match(r'^\d{1,2}[.,]\d{2}([.,]\d{2})?$', cleaned):
            return False
        
        price_like = re.findall(r'\d+[.,]\d{2,}', cleaned)
        if len(price_like) >= 2:
            return True
        
        return False

    def _parse_sl_tp_update(self, text: str, pending_signal: dict) -> dict:
        """Parsea actualización SL/TP"""
        if not pending_signal:
            logger.warning("SL/TP recibido pero no hay señal pendiente")
            return {"action": None, "symbol": None, "is_update": False}

        text_lower = text.lower()
        signal = pending_signal.copy()
        signal["is_update"] = True

        # Buscar SL
        sl_patterns = [
            r'(?:sl|stop\s*loss|stop)[:\s]*@?([\d]+[.,]?[\d]*)',
            r'❌\s*(?:stop\s*loss|sl)[:\s]*@?([\d]+[.,]?[\d]*)',
        ]
        for pattern in sl_patterns:
            match = re.search(pattern, text_lower)
            if match:
                signal["sl"] = float(match.group(1).replace(",", "."))
                break

        # Buscar TP (múltiples)
        tp_patterns = [
            r'(?:tp|take\s*profit|target|obj)[:\s]*@?([\d]+[.,]?[\d]*)',
            r'🥇?\s*(?:take\s*profit\s*\d*|tp\s*\d*)[:\s]*@?([\d]+[.,]?[\d]*)',
            r'tp\s*\d*[:\s]*@?([\d]+[.,]?[\d]*)',
        ]
        for pattern in tp_patterns:
            matches = re.findall(pattern, text_lower)
            for m in matches:
                try:
                    tp_val = float(m.replace(",", "."))
                    if tp_val not in signal["tp"]:
                        signal["tp"].append(tp_val)
                except:
                    pass

        # Si no hay labels, buscar números standalone
        if not signal["sl"] and not signal["tp"]:
            prices = re.findall(r'(\d+\.?\d{2,5})', text)
            if len(prices) >= 2:
                p1, p2 = float(prices[0]), float(prices[1])
                if signal["action"] == "BUY":
                    if p1 < signal.get("price", p2):
                        signal["sl"] = p1
                        signal["tp"] = [p2]
                    else:
                        signal["sl"] = p2
                        signal["tp"] = [p1]
                elif signal["action"] == "SELL":
                    if p1 > signal.get("price", p2):
                        signal["sl"] = p1
                        signal["tp"] = [p2]
                    else:
                        signal["sl"] = p2
                        signal["tp"] = [p1]
            elif len(prices) == 1:
                signal["sl"] = float(prices[0])

        # Recalcular porcentajes
        if len(signal["tp"]) > 1:
            signal["tp_percentages"] = self._calculate_tp_percentages(len(signal["tp"]))

        logger.info(f"SL/TP actualizado: SL={signal.get('sl')}, TP={signal.get('tp')}")
        return signal

    def _detect_action(self, text_lower: str, original: str) -> str:
        """Detecta la acción"""
        for word in self.CLOSE_WORDS:
            if word in text_lower:
                return "CLOSE"
        for word in self.BUY_WORDS:
            if word in text_lower:
                return "BUY"
        for word in self.SELL_WORDS:
            if word in text_lower:
                return "SELL"
        return None

    def _detect_symbol(self, original: str, text_lower: str) -> str:
        """Detecta el símbolo"""
        # Mapeo de nombres comunes
        SYMBOL_MAP = {
            "GOLD": "XAUUSD", "ORO": "XAUUSD", "XAU": "XAUUSD",
            "SILVER": "XAGUSD", "PLATA": "XAGUSD", "XAG": "XAGUSD",
            "BITCOIN": "BTCUSD", "BTC": "BTCUSD",
            "ETHEREUM": "ETHUSD", "ETH": "ETHUSD",
            "SOLANA": "SOLUSD", "SOL": "SOLUSD",
            "DOW": "US30", "DJ30": "US30", "DOW JONES": "US30",
            "NASDAQ": "US100", "USTEC": "US100",
            "DAX": "DE40", "FTSE": "UK100", "NIKKEI": "JP225",
        }

        # Buscar en el mapa primero
        upper = original.upper()
        for key, value in SYMBOL_MAP.items():
            if key in upper:
                return value

        # Buscar pares de forex (6 letras)
        forex_match = re.search(r'\b([A-Z]{6})\b', upper)
        if forex_match:
            return forex_match.group(1)

        # Buscar con dos puntos (ej: "EURUSD:")
        colon_match = re.search(r'\b([A-Z]{3,6})\b\s*:', upper)
        if colon_match:
            return colon_match.group(1)

        return None

    def _detect_prices(self, text: str, signal: dict) -> dict:
        """Detecta precio de entrada o rango"""
        # Buscar rango: "2990.50 - 2992.50" o "2990.50-2992.50"
        range_match = re.search(r'(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)', text)
        if range_match:
            p1 = float(range_match.group(1))
            p2 = float(range_match.group(2))
            signal["price_range"] = (min(p1, p2), max(p1, p2))
            signal["price"] = (p1 + p2) / 2  # Precio promedio
            return signal

        # Buscar precio con 💎, @ o :
        price_patterns = [
            r'💎\s*([\d]+[.,]?[\d]*)',
            r'@\s*([\d]+[.,]?[\d]*)',
            r':\s*([\d]+[.,]?[\d]*)',
            r'(?:price|precio|entry|entrada)[:\s]*([\d]+[.,]?[\d]*)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    price = float(match.group(1).replace(",", "."))
                    if price > 0:
                        signal["price"] = price
                        return signal
                except:
                    pass

        # Buscar números que parezcan precios (con 2+ decimales)
        prices = re.findall(r'\b(\d+\.\d{2,5})\b', text)
        if prices:
            try:
                signal["price"] = float(prices[0])
            except:
                pass

        return signal

    def _detect_sl_tp(self, text: str, signal: dict) -> dict:
        """Detecta SL y TP"""
        lines = text.split("\n")
        
        for line in lines:
            ll = line.lower()
            
            # Buscar SL
            sl_patterns = [
                r'(?:sl|stop\s*loss|stop|❌)[:\s]*@?([\d]+[.,]?[\d]*)',
            ]
            for pattern in sl_patterns:
                match = re.search(pattern, ll)
                if match:
                    try:
                        signal["sl"] = float(match.group(1).replace(",", "."))
                    except:
                        pass

            # Buscar TP (múltiples)
            tp_patterns = [
                r'(?:tp|take\s*profit)\s*\d*\s*[:\s]*@?(\d+[.,]?\d*)',
                r'(?:target|obj|🥇)[:\s]*@?([\d]+[.,]?[\d]*)',
            ]
            for pattern in tp_patterns:
                matches = re.findall(pattern, ll)
                for m in matches:
                    try:
                        tp_val = float(m.replace(",", "."))
                        if tp_val not in signal["tp"]:
                            signal["tp"].append(tp_val)
                    except:
                        pass

        # Si no encontró SL/TP con labels, buscar por posición
        if not signal["sl"] and not signal["tp"]:
            all_prices = []
            for line in lines:
                for m in re.findall(r'(\d+\.\d{2,5})', line):
                    try:
                        p = float(m)
                        if p > 0:
                            all_prices.append(p)
                    except:
                        pass
            
            if len(all_prices) >= 3:
                entry_price = signal.get("price")
                if entry_price is None:
                    entry_price = all_prices[0]
                    signal["price"] = entry_price
                    remaining = all_prices[1:3]
                else:
                    remaining = [p for p in all_prices if p != entry_price][:2]
                
                if len(remaining) >= 2:
                    if signal["action"] == "BUY":
                        signal["sl"] = min(remaining)
                        signal["tp"] = [max(remaining)]
                    elif signal["action"] == "SELL":
                        signal["sl"] = max(remaining)
                        signal["tp"] = [min(remaining)]

        return signal

    def _calculate_tp_percentages(self, num_tp: int) -> list:
        """Calcula porcentajes para cierre parcial"""
        if num_tp == 1:
            return [100]
        elif num_tp == 2:
            return [50, 50]
        elif num_tp == 3:
            return [50, 25, 25]
        elif num_tp == 4:
            return [25, 25, 25, 25]
        else:
            # Distribución uniforme con resto
            pct = 100 // num_tp
            remainder = 100 % num_tp
            result = [pct] * num_tp
            for i in range(remainder):
                result[i] += 1
            return result

    def _detect_lot(self, text: str) -> float:
        """Detecta lote"""
        match = re.search(r'(?:lot|lote|volumen|size|cantidad)[:\s]*([\d]+[.,]?[\d]*)', text)
        if match:
            try:
                lot = float(match.group(1).replace(",", "."))
                if 0.01 <= lot <= 100:
                    return lot
            except:
                pass
        return None

    def is_valid_signal(self, signal: dict) -> bool:
        """Valida si la señal tiene los campos mínimos"""
        return (
            signal.get("action") is not None
            and signal.get("symbol") is not None
            and signal["action"] in ["BUY", "SELL", "CLOSE"]
        )

    def has_sl_tp(self, signal: dict) -> bool:
        """Verifica si la señal tiene SL o TP"""
        return signal.get("sl") is not None or len(signal.get("tp", [])) > 0


if __name__ == "__main__":
    parser = SignalParser()
    
    tests = [
        "XAUUSD sell now @ 4066.5\nTp @ 4048\nTp2 @ 4020\nSl @ 408",
        "AUDCAD Buy: 0.9216\nTP: 0.9236\nSL: 0.91961",
        "GOLD SELL: 2990.50 - 2992.50\n❌Stop Loss : 2995.50\n🥇Take Profit 1 : 2988.00\n🥇Take Profit 2 : 2985.50",
        "Comprar EURUSD ahora @1.0500\nSL @1.0480\nTP @1.0550",
        "Vender GBPUSD ahora",
        "Buy XAUUSD",
        "SL: 4130\nTP: 4200",
    ]
    
    pending = None
    for test in tests:
        print(f"\n{'='*50}")
        print(f"INPUT: {test[:60]}...")
        result = parser.parse_message(test, pending)
        print(f"VALID: {parser.is_valid_signal(result)}")
        print(f"HAS_SL_TP: {parser.has_sl_tp(result)}")
        print(f"OUTPUT: {result}")
        
        if parser.is_valid_signal(result) and not parser.has_sl_tp(result):
            pending = result
            print("=> Guardado como pendiente")
