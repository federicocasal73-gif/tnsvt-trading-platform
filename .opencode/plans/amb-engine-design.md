# Absolute Multi-Timeframe Bias Engine (AMB) — Diseño Técnico

## 1. Filosofía

El AMB es el motor analítico central del TNSVT Financial Terminal. Su propósito es determinar el **bias direccional absoluto** de un símbolo en cada marco temporal, usando una jerarquía **top-down** donde los marcos superiores gobiernan a los inferiores.

**Principio fundamental:** Un timeframe inferior NO puede invalidar a uno superior. M15 puede buscar entrada en la dirección de H1, pero H1 no puede contradecir a Daily, y así hasta Macro.

## 2. Jerarquía Temporal (8 niveles)

```
Nivel  | Timeframe | Rol
--------|-----------|----------------------
1       | MACRO     | Contexto macro global (índices, VIX, commodities)
2       | WEEKLY    | Tendencia estructural (semanas-meses)
3       | DAILY     | Tendencia principal (días-semanas)
4       | H4        | Tendencia intermedia (sesión)
5       | H1        | Dirección operativa (horas)
6       | M15       | Timing de entrada (15-30 min)
7       | M5        | Precisión de entrada (5-10 min)
8       | M1        | Ejecución (punto de entrada exacto)
```

## 3. Fuentes de Datos

- **Bridge API** (`http://localhost:5001`): Obtener velas OHLCV históricas
- **Trading Economics**: Contexto macro (GDP, CPI, unemployment)
- **Investing.com**: Calendario económico, impacto, pronósticos
- **Alpha Vantage**: VIX, índices, noticias con sentimiento
- **TNSVT Client**: Estado del copiador, trades recientes

## 4. Detección de Patrones (Price Action + SMC)

### 4.1 Price Action
- Soporte / Resistencia (S/R): Niveles clave horizontales
- Líneas de tendencia: Canales alcistas/bajistas
- Velas: Doji, engulfing, martillo, estrella fugaz, inside bar
- Estructura: HH/HL (uptrend), LH/LL (downtrend), rango

### 4.2 SMC (Smart Money Concepts)
- **FVG (Fair Value Gap):** 3-vela gap donde la vela1 baja + vela2 alta tienen espacio sin traslape
- **Order Block (OB):** Última vela en contra de la tendencia antes del movimiento fuerte
- **Liquidity Sweep:** Ruptura falsa de S/R que barre stops
- **CISD (Change in State of Delivery):** Ruptura de estructura de mercado (quiebre de HH/HL o LH/LL)
- **Imbalance:** Desequilibrio oferta/demanda visible en FVG

## 5. Scoring System (0–100)

### 5.1 Peso por Timeframe

| Timeframe | Peso % | Descripción |
|-----------|--------|-------------|
| MACRO     | 25     | Contexto global, aprieta o cancela todo |
| WEEKLY    | 20     | Tendencia estructural |
| DAILY     | 20     | Tendencia principal |
| H4        | 15     | Tendencia intermedia |
| H1        | 10     | Dirección operativa |
| M15       | 5      | Timing |
| M5        | 3      | Precisión |
| M1        | 2      | Ejecución |

### 5.2 Factores de scoring por TF

Cada timeframe puntúa de 0 a 100 basado en:

1. **Estructura de mercado (0-40):** HH/HL = alcista, LH/LL = bajista, rango = neutral
2. **FVG / Order Blocks (0-25):** Presencia y alineación de gaps/SMC
3. **S/R proximity (0-15):** Cerca de nivel clave + reacción
4. **Indicadores secundarios (0-10):** RSI, MACD, EMA
5. **Velas / Patrones (0-10):** Confirmación en la vela actual

### 5.3 Clasificación final

| Puntaje   | Clasificación | Acción |
|-----------|---------------|--------|
| ≥ 92      | AAA+          | Operar con convicción máxima |
| 85–91     | AA+           | Operar con confianza |
| 75–84     | A+            | Operar |
| 65–74     | BBB           | Operar con cautela |
| 55–64     | BB            | Preferible esperar |
| 45–54     | B+            | Dudoso, buscar confirmación extra |
| 35–44     | CCC           | Alta probabilidad de fracaso |
| 25–34     | CC            | Muy riesgoso |
| 15–24     | C             | Evitar |
| 5–14      | D             | No operar |
| 0–4       | NO TRADE      | Prohibido |

### 5.4 Filtro RR (Risk:Reward)

- Si RR < 1:2 → NO TRACE automático, independientemente del score
- Si RR ≥ 1:2 → se permite según score

## 6. Macro RED_ALERT

Si VIX > 35 (o crisis macro detectada):

- **Todas las puntuaciones se congelan en NO TRADE**
- Se envía alerta al chat de admin
- No se ejecutan nuevas operaciones
- Las posiciones abiertas existentes pueden cerrarse manualmente

## 7. State Machine de Trade

```
         +----------+
         |  IDLE    |
         +----+-----+
              |
      (score >= umbral + RR ok)
              |
              v
         +----------+
         | ENTRY_OK | → Alerta al usuario
         +----+-----+
              |
      (precio alcanza entrada)
              |
              v
         +----------+
         |   OPEN   | → Alerta apertura
         +----+-----+
              |
    +---------+---------+
    |                   |
    v                   v
+------+           +--------+
| TP   |           | SL     |
+------+           +--------+
    |                   |
    v                   v
+----------+       +----------+
| WIN      |       | LOSS     |
+----------+       +----------+
    |                   |
    +-------+-----------+
            |
            v
       +----------+
       |  IDLE    |
       +----------+
```

## 8. Arquitectura Técnica

### 8.1 Módulos

```
bot/analytics/
├── __init__.py
├── amb_engine.py          # Core del motor
├── calendar.py            # Investing.com calendar (ART)
├── macro_filter.py        # VIX, crisis detection
├── indicator_wrappers.py  # RSI, MACD, EMA, ATR
└── patterns/
    ├── __init__.py
    ├── price_action.py    # S/R, tendencias, velas
    └── smc.py             # FVG, OB, liquidity sweep, CISD
```

### 8.2 Flujo de llamada

```
Handler (/analisis, /r, /reporte)
    │
    ▼
amb_engine.analyze(symbol: str)
    │
    ├── macro_filter.evaluate()  → RED_ALERT check
    │
    ├── patterns/price_action.get_structure(tf)
    ├── patterns/smc.get_fvg(tf)
    ├── patterns/smc.get_order_blocks(tf)
    │
    ├── indicator_wrappers.rsi(tf)
    ├── indicator_wrappers.macd(tf)
    ├── indicator_wrappers.ema(tf)
    ├── indicator_wrappers.atr(tf)
    │
    ├── score_tf(macro_data, pa_data, smc_data, ind_data) → 0-100
    │
    ├── calculate_weighted_score(all_tf_scores) → 0-100
    │
    ├── classify(final_score) → AAA+ ... NO TRADE
    │
    ├── apply_rr_filter(score, rr) → score or NO TRADE
    │
    └── return AnalysisResult(bias, score, classification, details)
```

### 8.3 Caching

- OHLCV data: caché en memoria con TTL = 30s (intraday) o 5min (daily+)
- Scores intermedios: TTL = 30s
- Macro data: TTL = 5min

### 8.4 Manejo de errores

- Timeout por API externa: 5s máximo
- Si una fuente falla, se degrada gracefulmente (score = 0 para ese factor, se continúa)
- Si todas las fuentes fallan: `AnalysisResult(symbol, None, 0, "NO DATA", {error})`

## 9. Plantilla de Mensaje

### /analisis EURUSD

```
📊 Análisis Técnico: EURUSD
━━━━━━━━━━━━━━━━━━━━━━━

🏆 Clasificación: AA+ (87/100) → COMPRABLE
📐 Bias general: ALCISTA

━━━ Jerarquía Temporal ━━━
🌍 MACRO    : ALCISTA  (92/100) [25%]
📅 SEMANAL  : ALCISTA  (85/100) [20%]
📅 DIARIO   : ALCISTA  (78/100) [20%]
⚡ H4       : ALCISTA  (70/100) [15%]
⚡ H1       : NEUTRAL  (55/100) [10%]
⏱️ M15      : ALCISTA  (60/100) [ 5%]
⏱️ M5       : ALCISTA  (65/100) [ 3%]
⏱️ M1       : NEUTRAL  (50/100) [ 2%]

━━━ Patrones Detectados ━━━
🟢 FVG Alcista en H1     → $1.0850-1.0870
🟢 OB Alcista en Daily    → $1.0800-1.0820
🟢 CISD Confirmado en H4  → Ruptura HH
🟡 Liquidity Sweep M15    → Falso quiebre bajista

━━━ Indicadores ━━━
📈 RSI(14)  H4: 62  → Neutral-Alcista
📊 MACD     H4: Alcista (línea > señal > 0)
📉 EMA(50)  > EMA(200) → Golden Cross

━━━ Recomendación ━━━
✅ COMPRA en M15 / M5
🎯 TP1: 1.0920 | TP2: 1.0960 | SL: 1.0830
📐 RR: 1:2.8 → ✅ Viable
🚫 Sin alertas macro activas

💡 Momento de entrada ideal: próximo retroceso a FVG H1
```
