import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from google import genai
import json
import os

# CONFIGURACIÓN
GOOGLE_API_KEY = "AIzaSyB2X7Mn-R4QPCW-AY4m1KIH-HM3dTBW1dA" 

class AIParser:
    def __init__(self):
        if GOOGLE_API_KEY.startswith("AIza"):
            try:
                # Inicialización v1.0 (Nuevo SDK)
                self.client = genai.Client(api_key=GOOGLE_API_KEY)
                
                # TEST DE CONEXIÓN REAL (Ping a Gemini)
                print("🧠 Conectando con Gemini AI (gemini-2.0-flash-lite)...")
                test_response = self.client.models.generate_content(
                    model='gemini-2.0-flash-lite-001', 
                    contents="Responde OK si me escuchas."
                )
                if test_response and test_response.text:
                    print("✅ Cerebro IA: LISTO y VERIFICADO (Ping exitoso).")
                else:
                    print("⚠️ Cerebro IA: Conectado pero sin respuesta en test.")
                    
            except Exception as e:
                print(f"❌ ERROR FATAL IA: No se pudo conectar. Verifica tu API Key. Detalle: {e}")
                self.client = None
        else:
            print("⚠️ ADVERTENCIA: API Key de Gemini no válida o no configurada.")
            self.client = None

    def parse_signal(self, text):
        if not self.client: return None
        
        # El "Prompt" (Instrucción Maestra) - REFORZADO PARA SL/TP
        prompt = f"""
        Eres un experto extractor de señales de trading. Tu trabajo es analizar el mensaje y devolver ÚNICAMENTE un JSON con la información exacta.
        
        REGLAS CRÍTICAS:
        1. **Acción**: Detecta si es BUY (compra/long/alcista), SELL (venta/short/bajista) o CLOSE (cerrar/salir).
        2. **Símbolo**: Normaliza el par/activo a formato estándar (ej: "oro" → "XAUUSD", "euro" → "EURUSD", "bitcoin" → "BTCUSD").
        3. **Precio de Entrada (price)**: Si se menciona un precio específico de entrada, extráelo. Si no, deja null.
        4. **Stop Loss (sl)**: 
           - OBLIGATORIO. Busca "SL", "stop loss", etc.
           - REGLA DE ORO: Si en la segunda línea del mensaje aparece un precio con "@" (ej: "@1.18435") y no contiene la palabra "TP", considéralo el SL aunque no tenga la etiqueta "SL".
        5. **Take Profit (tp)**: Busca "TP", "take profit", "objetivo", "target".
        6. **Si el mensaje NO es una señal de trading**, devuelve un JSON vacío: {{}}.
        
        EJEMPLOS DE EXTRACCIÓN:
        
        Caso 1 (Formato Implícito - Tu prioridad v15.2):
        Mensaje: 
        "Compre eurusd ahora @1.18476
        @1.184350
        Tp-1@1.188800"
        → {{"action": "BUY", "symbol": "EURUSD", "price": 1.18476, "sl": 1.18435, "tp": [1.188800]}}
        (Nota: Aquí el SL se extrajo de la segunda línea por posición).

        Caso 2 (Estilo Emoji Vertical):
        Mensaje: 
        "👑 #SELL USDCAD 👑
        💎 1.37877
        ‼️ SL: 1.38003
        ✅ TP: 1.37751"
        → {{"action": "SELL", "symbol": "USDCAD", "price": 1.37877, "sl": 1.38003, "tp": [1.37751]}}

        Caso 3 (Estilo Rápido):
        "Compra BTCUSD SL 95000 TP 98000" → {{"action": "BUY", "symbol": "BTCUSD", "price": null, "sl": 95000, "tp": [98000]}}
        
        MENSAJE A ANALIZAR:
        "{text}"
        
        RESPONDE SOLO CON EL JSON (sin markdown, sin explicaciones):
        """
        
        try:
            # Llamada v1.0 (Nuevo SDK)
            response = self.client.models.generate_content(
                model='gemini-2.0-flash-lite-001', contents=prompt
            )
            
            # Limpieza robusta del JSON
            clean_text = response.text.replace('```json', '').replace('```', '').strip()
            signal_data = json.loads(clean_text)
            
            # Validación estricta: Debe tener acción y símbolo
            if not signal_data.get('action') or not signal_data.get('symbol'):
                return None
            
            # Normalizar formato para Executor
            normalized_signal = {
                'action': signal_data.get('action').upper(),
                'symbol': signal_data.get('symbol').upper(),
                'price': float(signal_data.get('price')) if signal_data.get('price') else None,
                'sl': float(signal_data.get('sl')) if signal_data.get('sl') else None,
                'tp': []
            }
            
            # Normalizar TP (puede venir como float, string o lista)
            raw_tp = signal_data.get('tp')
            if isinstance(raw_tp, list):
                normalized_signal['tp'] = [float(x) for x in raw_tp if x]
            elif raw_tp:
                normalized_signal['tp'] = [float(raw_tp)]
            
            # VALIDACIÓN CRÍTICA: Si no hay SL, rechazar la señal (seguridad)
            if not normalized_signal['sl']:
                print(f"⚠️ IA: Señal rechazada por falta de Stop Loss. Symbol: {normalized_signal.get('symbol')}")
                return None
                
            return normalized_signal

        except Exception as e:
            print(f"❌ Error CRÍTICO en IA (Gemini): {e}")
            import traceback
            traceback.print_exc()
            return None

if __name__ == "__main__":
    # Test rápido
    p = AIParser()
    if p.client:
        print(p.parse_signal("chicos vendan oro yaaa en 2030 sl 2035"))
