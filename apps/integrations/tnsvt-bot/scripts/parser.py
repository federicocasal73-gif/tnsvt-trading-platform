import re

class SignalParser:

    def normalize_number(self, s):
        """
        Normaliza números con coma o punto decimal.
        Ej:
        128,4 -> 128.4
        """
        s = s.replace(' ', '')
        if s.count(',') == 1 and s.count('.') == 0:
            s = s.replace(',', '.')
        return float(s)

    def parse_message(self, text):
        text = text.lower().strip()

        signal = {
            'action': None,
            'symbol': None,
            'price': None,
            'sl': None,
            'tp': [],
            'valid': True
        }

        # =========================
        # 1. ACCIÓN + SÍMBOLO
        # =========================

        ignores = r'(?:now|ahora|ya|fast|rapido|go|market|mercado|execution|ejecucion|instante)'

        # Regex MEJORADO: Soporta conjugaciones (compre, vendo, etc)
        pattern = (
            r'(comprar|compre|compra|buy|'
            r'vender|vendo|venda|sell|'
            r'cerrar|close)\s+'
            r'(?:' + ignores + r'\s+)?'
            r'([a-zA-Z0-9#\._]+)'
        )

        action_match = re.search(pattern, text)

        if action_match:
            action_str = action_match.group(1)
            symbol_str = action_match.group(2).upper()

            signal['symbol'] = symbol_str

            if action_str in ('vender', 'vendo', 'venda', 'sell'):
                signal['action'] = 'SELL'
            elif action_str in ('cerrar', 'close'):
                signal['action'] = 'CLOSE'
            else:
                signal['action'] = 'BUY'

        # =========================
        # 2. PROCESAR LÍNEAS (Regla de Oro v15.2)
        # =========================
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        
        for idx, line in enumerate(lines):
            low_line = line.lower()

            # ---------- SL (Soporta explícito y POSICIONAL) ----------
            if signal['sl'] is None:
                # Caso A: Dice explícitamente "sl" o "stop loss"
                sl_match = re.search(r'(sl|stop\s*loss)\s*[\.:=\-]*\s*@?\s*([\d\.,]+)', low_line)
                if sl_match:
                    try:
                        signal['sl'] = self.normalize_number(sl_match.group(2))
                    except: pass
                
                # Caso B: REGLA DE ORO (Posición 2da línea, empieza con @ y no es TP)
                elif idx == 1 and line.startswith("@") and "tp" not in low_line:
                    price_in_line = re.search(r'@\s*([\d\.,]+)', line)
                    if price_in_line:
                        try:
                            signal['sl'] = self.normalize_number(price_in_line.group(1))
                        except: pass

            # ---------- TP (Soporta Tp-1, Tp:, Take Profit) ----------
            tp_match = re.search(r'(tp|take\s*profit)\s*[\-]?\s*\d*\s*[:=\-]*\s*@?\s*([\d\.,]+)', low_line)
            if tp_match:
                try:
                    signal['tp'].append(self.normalize_number(tp_match.group(2)))
                except: pass

            # ---------- PRECIO ENTRADA ----------
            if signal['price'] is None:
                # Solo buscamos precio de entrada en la PRIMERA línea (estándar)
                if idx == 0:
                    price_match = re.search(r'@\s*([\d\.,]+)', line)
                    if price_match:
                        try:
                            signal['price'] = self.normalize_number(price_match.group(1))
                        except: pass

        # =========================
        # 3. PRECIO FALLBACK
        # =========================

        if signal['price'] is None and signal['symbol']:
            nums = re.findall(r'(\d+[\.,]\d+)', text) # Buscar en todo el texto si falla línea por línea
            if nums:
                try:
                    # Usamos el primer número encontrado que parezca precio
                    signal['price'] = self.normalize_number(nums[0])
                except:
                    pass

        # =========================
        # 4. VALIDACIÓN FINAL
        # =========================

        if signal['action'] in ('BUY', 'SELL'):
            if signal['sl'] is None or not signal['tp']:
                signal['valid'] = False

        return signal


# =========================
# TESTS INCLUIDOS
# =========================
if __name__ == "__main__":
    p = SignalParser()
    t = "Compre eurusd ahora @1.18476\nSl.@1.184350\nTp-1@1.188800"
    print(p.parse_message(t))
