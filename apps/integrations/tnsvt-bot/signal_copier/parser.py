"""
Signal Copier - Parser Universal v3
Detecta señales de XAU LIQUIDITY, World Forex, COBRAX VIP, VIP Signals Oil
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("SignalCopier.ParserV3")

GOLD_ALIASES = {"ORO", "EL ORO", "GOLD", "XAU", "GOLD/XAUUSD", "XAUUSD"}
SYMBOL_ALIASES = {
    "GOLD": "XAUUSD", "ORO": "XAUUSD", "XAU": "XAUUSD",
    "SILVER": "XAGUSD", "PLATA": "XAGUSD", "XAG": "XAGUSD",
    "BITCOIN": "BTCUSD", "BTC": "BTCUSD",
    "ETHEREUM": "ETHUSD", "ETH": "ETHUSD",
    "SOLANA": "SOLUSD", "SOL": "SOLUSD",
    "DOW": "US30", "DJ30": "US30", "DOW JONES": "US30",
    "NASDAQ": "US100", "USTEC": "US100",
    "DAX": "DE40", "FTSE": "UK100", "NIKKEI": "JP225",
    "OIL": "XTIUSD", "CRUDE": "XTIUSD", "USOIL": "XTIUSD", "WTI": "XTIUSD",
}

IGNORED_WORDS = {"other", "running", "back", "entry", "limit", "now", "back entry"}

BUY_WORDS = {
    "buy", "long", "buy now", "buy:", "buy limit",
    "compra", "comprar", "comprar ahora", "entrada compra",
}
SELL_WORDS = {
    "sell", "short", "sell now", "sell:", "sell limit",
    "venta", "vender", "vender ahora", "entrada venta",
}


@dataclass
class ParsedSignal:
    action: Optional[str] = None
    symbol: Optional[str] = None
    price: Optional[float] = None
    price_range: Optional[tuple] = None
    sl: Optional[float] = None
    tp: list = field(default_factory=list)
    tp_percentages: list = field(default_factory=list)
    lot: Optional[float] = None
    is_update: bool = False
    is_complete: bool = False
    raw_symbol: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "price": self.price,
            "price_range": self.price_range,
            "sl": self.sl,
            "tp": self.tp,
            "tp_percentages": self.tp_percentages,
            "lot": self.lot,
            "is_update": self.is_update,
            "is_complete": self.is_complete,
            "raw_symbol": self.raw_symbol,
        }


class SignalParserV3:
    BUY_WORDS = BUY_WORDS
    SELL_WORDS = SELL_WORDS

    def __init__(self):
        self.pending: dict[str, dict] = {}

    def parse_message(self, text: str, pending_signal: dict = None) -> dict:
        cleaned = self._clean_text(text)
        signal = self._parse(cleaned, text, pending_signal)
        if signal.is_complete:
            self.pending.pop(text[:50], None)
        return signal.to_dict()

    def _clean_text(self, text: str) -> str:
        """Limpia ruido de COBRAX y otros canales ruidosos"""
        original = text
        text = text.strip()
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[\d\.\s]+$', line):
                continue
            if re.match(r'^\d+[hs]$', line, re.IGNORECASE):
                continue
            if re.match(r'^\d+\s+\d+$', line):
                continue
            cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _parse(self, cleaned: str, original: str, pending_signal: dict = None) -> ParsedSignal:
        signal = ParsedSignal()

        if self._is_sl_tp_only(cleaned):
            signal.is_update = True
            return self._parse_sl_tp_update(cleaned, pending_signal)

        signal.action = self._detect_action(cleaned)
        if not signal.action:
            return signal

        signal.symbol, signal.raw_symbol = self._detect_symbol(original, cleaned)
        if not signal.symbol:
            signal.symbol = self._detect_implicit_symbol(cleaned)

        signal = self._detect_prices(cleaned, signal)
        signal = self._detect_sl_tp(cleaned, signal)
        signal = self._detect_lot(cleaned, signal)

        if len(signal.tp) > 1:
            signal.tp_percentages = self._calculate_tp_percentages(len(signal.tp))

        signal.is_complete = self._is_complete(signal)
        return signal

    def _is_sl_tp_only(self, text: str) -> bool:
        text_lower = text.lower()
        sl_tp_indicators = ['sl', 'tp', 'stop', 'take', 'target', 'tp-', 'tp+', 'sl@', 'tp@']
        has_sl_tp = any(x in text_lower for x in sl_tp_indicators)
        has_action = any(x in text_lower for x in list(BUY_WORDS) + list(SELL_WORDS))
        if has_sl_tp and not has_action:
            if re.match(r'^[\d\s\.\-@]+$', text.strip()):
                return False
            if re.match(r'^\d{1,2}[.,]\d{2}([.,]\d{2})?$', text.strip()):
                return False
            return True
        return False

    def _parse_sl_tp_update(self, text: str, pending_signal: dict) -> ParsedSignal:
        signal = ParsedSignal()
        signal.is_update = True
        pending_sl = pending_signal.get("sl") if pending_signal else None
        pending_tp = list(pending_signal.get("tp", [])) if pending_signal else []
        if pending_signal:
            signal.action = pending_signal.get("action")
            signal.symbol = pending_signal.get("symbol")
            signal.price = pending_signal.get("price")
            signal.price_range = pending_signal.get("price_range")
            signal.tp = pending_tp[:]
        text_lower = text.lower()
        sl_val = self._extract_first_number(text, patterns=[r'sl@([\d.]+)', r'sl[:\s]+([\d.]+)', r'stop loss[:\s]+([\d.]+)'])
        if sl_val:
            signal.sl = sl_val
        elif pending_sl:
            signal.sl = pending_sl
        tps = re.findall(r'tp[@:\-]?(\d*?)[:\s@]*([\d.]+)', text_lower)
        for tp_match in tps:
            val_str = tp_match[1]
            try:
                val = float(val_str)
                if val not in signal.tp:
                    signal.tp.append(val)
            except:
                pass
        sl_was_extracted = sl_val is not None
        if not signal.tp and not tps and not pending_tp and not sl_was_extracted:
            nums = re.findall(r'([\d.]+)', text)
            for n in nums:
                try:
                    val = float(n)
                    if val not in signal.tp and len(signal.tp) < 3:
                        signal.tp.append(val)
                except:
                    pass
        if len(signal.tp) > 1:
            signal.tp_percentages = self._calculate_tp_percentages(len(signal.tp))
        return signal

    def _detect_action(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        words -= IGNORED_WORDS
        for word in BUY_WORDS:
            if word in text_lower:
                if "sell" in text_lower and "buy" not in words:
                    continue
                return "BUY"
        for word in SELL_WORDS:
            if word in text_lower:
                return "SELL"
        if "venta" in text_lower or "vender" in text_lower:
            return "SELL"
        if "compra" in text_lower or "comprar" in text_lower:
            return "BUY"
        return None

    def _detect_symbol(self, original: str, text: str) -> tuple:
        text_upper = original.upper()
        words = re.findall(r'\b[A-Za-z]{3,6}(?:/[A-Za-z]{3,6})?\b', text_upper)
        for word in words:
            clean = word.replace("/", "")
            if len(clean) == 6 and clean.isupper():
                if self._is_valid_forex_symbol(clean):
                    return clean, word
            if "/" in word:
                parts = word.split("/")
                if len(parts) == 2:
                    mapped = parts[0] + parts[1]
                    if self._is_valid_forex_symbol(mapped):
                        return mapped, word
        for alias, symbol in SYMBOL_ALIASES.items():
            if alias in text_upper:
                return symbol, alias
        return None, None

    def _detect_implicit_symbol(self, text: str) -> Optional[str]:
        text_upper = text.upper()
        for alias in GOLD_ALIASES:
            if alias.upper() in text_upper:
                return "XAUUSD"
        return None

    def _is_valid_forex_symbol(self, s: str) -> bool:
        if len(s) != 6:
            return False
        if not s.isupper():
            return False
        if s in {"ORO", "XAU", "SILVER", "XAG", "GOLD"}:
            return False
        majors = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
                  "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"}
        return s in majors or (s[:3] in {"EUR", "GBP", "USD", "AUD", "NZD", "USDC", "XAU", "XAG", "BTC", "ETH"} and s[3:] in {"USD", "JPY", "CHF", "CAD", "AUD", "NZD", "GBP"})

    def _detect_prices(self, text: str, signal: ParsedSignal) -> ParsedSignal:
        text_lower = text.lower()
        symbol_match = re.search(r'\b([A-Z]{6})\b', text.upper())
        symbol_prefix = symbol_match.group(1) + " " if symbol_match else ""

        at_price_patterns = [
            rf'{symbol_prefix}@\s*([\d.]+)',
            rf'@\s*([\d.]+)',
            r'price[:\s]+([\d.]+)',
            r'entry[:\s]+([\d.]+)',
            r'precio[:\s]+([\d.]+)',
            r'💎\s*([\d.]+)',
        ]
        for pattern in at_price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    signal.price = float(match.group(1))
                    return signal
                except:
                    pass

        range_patterns = [
            r'entry[:\s]*([\d.]+)\s*[-–]\s*([\d.]+)',
            r'price[:\s]*([\d.]+)\s*[-–]\s*([\d.]+)',
            r'@\s*([\d.]+)\s*[-–]\s*([\d.]+)',
        ]
        for pattern in range_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    p1, p2 = float(match.group(1)), float(match.group(2))
                    signal.price_range = (min(p1, p2), max(p1, p2))
                    signal.price = (p1 + p2) / 2
                    return signal
                except:
                    pass

        numbers = re.findall(r'(?:^|\s)([\d.]+)(?:\s|$)', text)
        for num_str in numbers:
            try:
                val = float(num_str)
                if 0.1 < val < 200000:
                    signal.price = val
                    return signal
            except:
                pass

        return signal

    def _detect_sl_tp(self, text: str, signal: ParsedSignal) -> ParsedSignal:
        text_lower = text.lower()
        lines = text.split("\n")

        sl_patterns = [
            r'sl@([\d.]+)',
            r'sl[@:\s]+([\d.]+)',
            r'stop\s*loss[@:\s]+([\d.]+)',
            r'stop[@:\s]+([\d.]+)',
            r'sl$',
            r'❌\s*sl[:\s]+([\d.]+)',
        ]
        for line in lines:
            ll = line.lower().strip()
            for pattern in sl_patterns:
                if pattern.endswith('sl') and not ll.strip().startswith('sl'):
                    continue
                match = re.search(pattern, ll)
                if match:
                    try:
                        if match.lastindex and match.lastindex >= 1:
                            signal.sl = float(match.group(1))
                        break
                    except:
                        pass

        tp_patterns = [
            r'tp[@:\s]+([\d.]+)',
            r'tp\d*[@:\s]+([\d.]+)',
            r'tp-\d*[@:\s]+([\d.]+)',
            r'tp[@:\s]+(\d+)\s+([\d.]+)',
            r'\+tp(\d*)[:\s@]*([\d.]+)',
            r'\.\+tp(\d*)[:\s@]*([\d.]+)',
            r'take\s*profit[:\s]+([\d.]+)',
            r'target[:\s]+([\d.]+)',
            r'🥇[:\s]+([\d.]+)',
            r'tp[:\s]+open',
        ]
        for line in lines:
            ll = line.lower().strip()
            for pattern in tp_patterns:
                if 'open' in pattern:
                    continue
                match = re.search(pattern, ll)
                if match:
                    try:
                        if match.lastindex and match.lastindex >= 2:
                            val = float(match.group(2))
                        elif match.lastindex and match.lastindex == 1:
                            val = float(match.group(1))
                        else:
                            val_str = match.group(0).replace('tp', '').replace('@', '').replace(':', '').replace('+', '').replace('.', '').strip()
                            val = float(val_str)
                        if val > 0 and val not in signal.tp:
                            signal.tp.append(val)
                    except:
                        pass

        if not signal.sl and not signal.tp:
            numbers = re.findall(r'([\d.]+)', text)
            valid = []
            for n in numbers:
                try:
                    v = float(n)
                    if 10 < v < 200000:
                        valid.append(v)
                except:
                    pass
            if len(valid) >= 2 and not signal.sl:
                if signal.action == "BUY":
                    sl_candidate = min(valid)
                    tp_candidates = [v for v in valid if v != sl_candidate]
                    if tp_candidates:
                        signal.sl = sl_candidate
                        signal.tp = tp_candidates[:3]
                elif signal.action == "SELL":
                    sl_candidate = max(valid)
                    tp_candidates = [v for v in valid if v != sl_candidate]
                    if tp_candidates:
                        signal.sl = sl_candidate
                        signal.tp = tp_candidates[:3]

        return signal

    def _detect_lot(self, text: str, signal: ParsedSignal) -> ParsedSignal:
        text_lower = text.lower()
        match = re.search(r'(?:lot|lote|volumen|size)[:\s]*([\d.]+)', text_lower)
        if match:
            try:
                lot = float(match.group(1))
                if 0.01 <= lot <= 100:
                    signal.lot = lot
            except:
                pass
        return signal

    def _extract_first_number(self, text: str, patterns: list) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    pass
        return None

    def _calculate_tp_percentages(self, num_tp: int) -> list:
        if num_tp == 1:
            return [100]
        elif num_tp == 2:
            return [50, 50]
        elif num_tp == 3:
            return [50, 25, 25]
        elif num_tp == 4:
            return [25, 25, 25, 25]
        else:
            pct = 100 // num_tp
            remainder = 100 % num_tp
            result = [pct] * num_tp
            for i in range(remainder):
                result[i] += 1
            return result

    def _is_complete(self, signal: ParsedSignal) -> bool:
        return (
            signal.action in ("BUY", "SELL")
            and signal.symbol is not None
            and signal.sl is not None
            and len(signal.tp) >= 1
        )

    def is_valid_signal(self, signal: dict) -> bool:
        return (
            signal.get("action") in ("BUY", "SELL")
            and signal.get("symbol") is not None
        )

    def has_sl_tp(self, signal: dict) -> bool:
        return signal.get("sl") is not None or len(signal.get("tp", [])) > 0


if __name__ == "__main__":
    parser = SignalParserV3()

    tests = [
        ("XAU LIQUIDITY - VENTA", "VENTA EN EL ORO\nSL:4020.3 (100 PIPS)\nTP:3980.3 (300 PIPS)"),
        ("XAU LIQUIDITY - COMPRA", "COMPRA EN EL ORO\nSL:4059.1 (100 PIPS)\nTP:4099.1 (300 PIPS)"),
        ("World Forex buy", "XAUUSD buy now @ 4038.5\nother buy @ 4031\ntp @ 4062\ntp2 @ 4090\nSL @ 4017"),
        ("World Forex sell limit", "XAUUSD sell limit @ 4122\nTp @ 4090\nSl @ 4137"),
        ("World Forex TP lines", "XAUUSD buy now @ 3995\ntp @ 4004\ntp2 @ 4016\nSL @ 3987"),
        ("VIP Signals Oil", "Vender limit xauusd @4897\nSl@4941\ntp-1@4850\ntp-2@4772"),
        ("VIP Signals Oil 2", "Vender EURUSD ahora @1.18182\n@1.18320\nTp-1@1.18020\nTp-2@1.17880"),
        ("COBRAX noisy", "SELL GOLD/XAUUSD @ NOW\nEntry: 3990-3992\nSL: 3997\n+TP1 3984\n.+TP2 3975\nTP3: Open"),
        ("COBRAX buy", "BUY GOLD/XAUUSD @ NOW\nEntry: 3995-3993\nSL: 3989\nTP1 4001\nTP2 4010\nLTP3: Open"),
    ]

    for name, test in tests:
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"INPUT: {test[:80]}...")
        result = parser.parse_message(test)
        print(f"VALID: {parser.is_valid_signal(result)}")
        print(f"COMPLETE: {result.get('is_complete')}")
        print(f"HAS_SL_TP: {parser.has_sl_tp(result)}")
        print(f"RESULT: action={result.get('action')} symbol={result.get('symbol')} "
              f"price={result.get('price')} sl={result.get('sl')} tp={result.get('tp')} "
              f"range={result.get('price_range')}")
