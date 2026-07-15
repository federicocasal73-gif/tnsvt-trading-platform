# TNSVT V2 — Flujos de Datos

**Versión:** 2.0  
**Fecha:** 14 de Julio de 2026  
**Clasificación:** Confidencial — Uso Interno  
**Estado:** Aprobado por Arquitectura  

---

## Índice

1. [Flujo 1: Señal → Parsing → Validación → Ejecución](#1-señal--parsing--validación--ejecución)
2. [Flujo 2: Risk Check → Approval → Order Routing](#2-risk-check--approval--order-routing)
3. [Flujo 3: AI Signal Scoring → Classification → Recommendation](#3-ai-signal-scoring--classification--recommendation)
4. [Flujo 4: User Authentication → OAuth2 → JWT → RBAC](#4-user-authentication--oauth2--jwt--rbac)
5. [Flujo 5: Billing → Subscription → License Check](#5-billing--subscription--license-check)
6. [Flujo 6: Copy Trading: One Signal → Multiple Accounts](#6-copy-trading-one-signal--multiple-accounts)
7. [Flujo 7: Backtesting → Walk Forward → Optimization → Deployment](#7-backtesting--walk-forward--optimization--deployment)
8. [Flujo 8: Heartbeat → Health Check → Recovery → Failover](#8-heartbeat--health-check--recovery--failover)

---

## Convenciones de los Diagramas

```
+=========================================================================+
|                    CONVENCIONES DE DIAGRAMAS                             |
+=========================================================================+
|                                                                          |
|  [Servicio]           = Componente del sistema                          |
|  ---> (flecha sólida) = Flujo síncrono (request/response)              |
|  - - -> (flecha punteada) = Flujo asincróno (NATS event)               |
|  ====>  (flecha triple) = Flujo crítico de alto impacto                |
|  ...>   (flecha de puntos) = Flujo condicional / opcional              |
|                                                                          |
|  NATS Subject: <domain>.<action>.<entity>                               |
|  Tiempo: ms (milisegundos), s (segundos), min (minutos)                 |
|  SLA: indicado por flujo                                                |
+=========================================================================+
```

---

## 1. Señal → Parsing → Validación → Ejecución

**Descripción:** Flujo principal de trading. Una señal ingresa al sistema,
se valida contra reglas de negocio, se ejecuta contra el broker, y se
propaga el resultado a todos los servicios interesados.

**Latencia objetivo total:** < 100ms (p99)  
**SLA del flujo:** 99.99%  
**Servicios involucrados:** 6  

```
+=========================================================================+
|  FLUJO 1: SEÑAL → PARSING → VALIDACIÓN → EJECUCIÓN                      |
+=========================================================================+
|                                                                          |
| [1]          [2]            [3]           [4]         [5]       [6]      |
| Platform   Trading       Risk          Broker      Audit     Notif.     |
| Signal     Engine        Manager       Gateway     Engine    Dispatcher |
| Ingest    Orchestrator  Validator     Router      Logger    Sender     |
|                                                                          |
|  |           |             |             |           |          |       |
|  |  Signal   |             |             |           |          |       |
|  |  Received |             |             |           |          |       |
|  +---------->|             |             |           |          |       |
|  |           |             |             |           |          |       |
|  |           |  [1a] Parse |             |           |          |       |
|  |           |  & Validate |             |           |          |       |
|  |           |  Signal     |             |           |          |       |
|  |           |  Format     |             |           |          |       |
|  |           |  (5ms)      |             |           |          |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  risk.check |             |           |          |       |
|  |           |  .request   |             |           |          |       |
|  |           |- - - - - - >|             |           |          |       |
|  |           |             |             |           |          |       |
|  |           |             | [2a] Eval   |           |          |       |
|  |           |             | Risk Rules  |           |          |       |
|  |           |             | (10ms)      |           |          |       |
|  |           |             |             |           |          |       |
|  |           |             | - Exposure? |           |          |       |
|  |           |             | - Drawdown? |           |          |       |
|  |           |             | - Max Loss? |           |          |       |
|  |           |             | - Circuit?  |           |          |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  risk.check |             |           |          |       |
|  |           |  .approved  |             |           |          |       |
|  |           |< - - - - - -|             |           |          |       |
|  |           |             |             |           |          |       |
|  |           | [3a] Route  |             |           |          |       |
|  |           | to Broker   |             |           |          |       |
|  |           | (by account |             |           |          |       |
|  |           |  config)    |             |           |          |       |
|  |           | (5ms)       |             |           |          |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  broker.    |             |           |          |       |
|  |           |  execute.   |             |           |          |       |
|  |           |  order      |             |           |          |       |
|  |           |- - - - - - - - - - - - -> |           |          |       |
|  |           |             |             |           |          |       |
|  |           |             |             | [4a] Send  |          |       |
|  |           |             |             | to Broker |          |       |
|  |           |             |             | API       |          |       |
|  |           |             |             | (20-50ms) |          |       |
|  |           |             |             |           |          |       |
|  |           |             |             | [4b] Recv  |          |       |
|  |           |             |             | Execution |          |       |
|  |           |             |             | Report    |          |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  trading.   |             |           |          |       |
|  |           |  order.     |             |           |          |       |
|  |           |  filled     |             |           |          |       |
|  |           |< - - - - - - - - - - - - -|           |          |       |
|  |           |             |             |           |          |       |
|  |           | [5a] Update |             |           |          |       |
|  |           | State       |             |           |          |       |
|  |           | Machine     |             |           |          |       |
|  |           | (5ms)       |             |           |          |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  audit.     |             |           |          |       |
|  |           |  event.     |             |           |          |       |
|  |           |  logged     |             |           |          |       |
|  |           |- - - - - - - - - - - - - - - - - - ->|          |       |
|  |           |             |             |           |          |       |
|  |           |             |             |           | [5b] Store|       |
|  |           |             |             |           | Event    |       |
|  |           |             |             |           | (5ms)    |       |
|  |           |             |             |           |          |       |
|  |           |  NATS:      |             |           |          |       |
|  |           |  notif.     |             |           |          |       |
|  |           |  send       |             |           |          |       |
|  |           |- - - - - - - - - - - - - - - - - - - - - - - -> |       |
|  |           |             |             |           |          |       |
|  |           |             |             |           | [6a] Send |       |
|  |           |             |             |           | Notif.   |       |
|  |           |             |             |           | (50ms)   |       |
|  |           |             |             |           |          |       |
|  v           v             v             v           v          v       |
|                                                                          |
|  RESUMEN DE TIMING:                                                      |
|  [1] Signal Received ──────────────────────────────────────────> 0ms    |
|  [2] Trading Engine Parse & Validate ──────────────────────────> 5ms    |
|  [3] Risk Check Request ───────────────────────────────────────> 10ms   |
|  [4] Risk Check Response ──────────────────────────────────────> 20ms   |
|  [5] Broker Route + Send ──────────────────────────────────────> 30ms   |
|  [6] Broker Execution Report ──────────────────────────────────> 50-80ms|
|  [7] Event Store Write ────────────────────────────────────────> 85ms   |
|  [8] Notification Dispatched ──────────────────────────────────> 100ms  |
|                                                                          |
|  TOTAL TARGET: < 100ms (p99)                                            |
+=========================================================================+
```

### Formato de Datos: Señal de Entrada

```json
{
  "signal_id": "sig_abc123",
  "source": "ai_scorer",
  "symbol": "EURUSD",
  "direction": "BUY",
  "type": "MARKET",
  "confidence": 87.5,
  "entry_price": 1.0850,
  "stop_loss": 1.0820,
  "take_profit": 1.0910,
  "timeframe": "M15",
  "strategy": "trend_following_v2",
  "metadata": {
    "regime": "trending",
    "atr_value": 0.0035,
    "rsi_value": 62.3,
    "risk_reward_ratio": 2.0
  },
  "timestamp": "2026-07-14T15:30:00.000Z"
}
```

### Formato de Datos: Execution Report

```json
{
  "execution_id": "exec_xyz789",
  "order_id": "ord_abc123",
  "signal_id": "sig_abc123",
  "broker": "binance",
  "account_id": "acc_001",
  "symbol": "EURUSD",
  "direction": "BUY",
  "type": "MARKET",
  "quantity": 0.1,
  "filled_price": 1.0851,
  "slippage": 0.0001,
  "commission": 0.35,
  "status": "FILLED",
  "filled_at": "2026-07-14T15:30:00.050Z",
  "latency_ms": 48
}
```

### NATS Subjects Utilizados

| Subject                          | Evento                    | Retención |
|----------------------------------|---------------------------|-----------|
| `trading.signal.received`        | Señal entra al sistema    | limits    |
| `risk.check.request`             | Solicitud de validación   | workqueue |
| `risk.check.approved`            | Riesgo aprobado           | workqueue |
| `trading.order.place`            | Orden a ejecutar          | workqueue |
| `broker.execute.order`           | Orden al broker           | workqueue |
| `broker.execution.report`        | Respuesta del broker      | workqueue |
| `trading.order.filled`           | Orden completada          | workqueue |
| `audit.event.logged`             | Evento de auditoría       | streams   |
| `notification.send`              | Notificación al usuario   | workqueue |

---

## 2. Risk Check → Approval → Order Routing

**Descripción:** Flujo detallado de validación de riesgo. Muestra cómo el
Risk Manager evalúa múltiples dimensiones antes de aprobar una orden.

**Latencia objetivo:** < 10ms para la evaluación completa  
**SLA del flujo:** 99.99%  
**Servicios involucrados:** 4  

```
+=========================================================================+
|  FLUJO 2: RISK CHECK → APPROVAL → ORDER ROUTING                         |
+=========================================================================+
|                                                                          |
| [Trading         [Risk          [Exposure        [Circuit                |
|  Engine]          Manager]       Calculator]      Breaker]               |
|                                                                          |
|  |                 |               |                |                   |
|  | RiskCheckReq    |               |                |                   |
|  | (order, acct)   |               |                |                   |
|  +---------------->|               |                |                   |
|  |                 |               |                |                   |
|  |                 | [2a] LOAD     |                |                   |
|  |                 | RISK RULES    |                |                   |
|  |                 | FROM REDIS    |                |                   |
|  |                 | (1ms)         |                |                   |
|  |                 |               |                |                   |
|  |                 | [2b] CHECK    |                |                   |
|  |                 | CIRCUIT       |                |                   |
|  |                 | BREAKER STATE |                |                   |
|  |                 |               |                |                   |
|  |                 | GetState      |                |                   |
|  |                 |──────────────>|                |                   |
|  |                 |               |                |                   |
|  |                 | State: CLOSED |                |                   |
|  |                 |<──────────────|                |                   |
|  |                 | (0.5ms)       |                |                   |
|  |                 |               |                |                   |
|  |                 | [2c] CALCULATE|                |                   |
|  |                 | CURRENT       |                |                   |
|  |                 | EXPOSURE      |                |                   |
|  |                 |               |                |                   |
|  |                 | CalcExposure  |                |                   |
|  |                 | (account, sym)|                |                   |
|  |                 |────────────────────────> |     |                   |
|  |                 |               |                |                   |
|  |                 |               | [2c.1] QUERY   |                   |
|  |                 |               | POSITIONS FROM |                   |
|  |                 |               | REDIS CACHE    |                   |
|  |                 |               | (0.5ms)        |                   |
|  |                 |               |                |                   |
|  |                 |               | [2c.2] CALC    |                   |
|  |                 |               | NET EXPOSURE   |                   |
|  |                 |               | (long - short) |                   |
|  |                 |               | (0.5ms)        |                   |
|  |                 |               |                |                   |
|  |                 | ExposureResult|                |                   |
|  |                 | (current:     |                |                   |
|  |                 |  $45,000,     |                |                   |
|  |                 |  max: $100K)  |                |                   |
|  |                 |<─────────────────────────|     |                   |
|  |                 | (1ms)         |                |                   |
|  |                 |               |                |                   |
|  |                 | [2d] EVALUATE RULES:           |                   |
|  |                 |               |                |                   |
|  |                 | Rule 1: Max exposure per       |                   |
|  |                 |   symbol: $50K     [PASS]      |                   |
|  |                 | Rule 2: Max total   [PASS]      |                   |
|  |                 |   exposure: $100K   ($45K+$5K)  |                   |
|  |                 | Rule 3: Max daily   [PASS]      |                   |
|  |                 |   drawdown: 5%      (current 2%)|                   |
|  |                 | Rule 4: Max orders  [PASS]      |                   |
|  |                 |   per hour: 20      (current 3) |                   |
|  |                 | Rule 5: Min R/R     [PASS]      |                   |
|  |                 |   ratio: 1.5        (current 2) |                   |
|  |                 | Rule 6: Blacklisted [PASS]      |                   |
|  |                 |   symbol: no        (EURUSD ok) |                   |
|  |                 |               |                |                   |
|  |                 | [2e] ALL      |                |                   |
|  |                 | RULES PASSED  |                |                   |
|  |                 |               |                |                   |
|  |  RiskCheckApproved              |                |                   |
|  |  (with limits recalculated)     |                |                   |
|  |<----------------|               |                |                   |
|  | (10ms total)    |               |                |                   |
|  |                 |               |                |                   |
|  v                 v               v                v                   |
|                                                                          |
+=========================================================================+
```

### Tabla de Reglas de Riesgo

| Regla                          | Parámetro Default        | Acción si Falla | Severidad  |
|--------------------------------|--------------------------|------------------|------------|
| Max exposure por símbolo       | $50,000                  | REJECT           | Alta       |
| Max exposure total             | $200,000                 | REJECT           | Crítica    |
| Max daily drawdown             | 5% del equity            | REJECT           | Crítica    |
| Max weekly drawdown            | 10% del equity           | REJECT           | Crítica    |
| Max órdenes por hora           | 20                       | REJECT           | Media      |
| Min Risk/Reward ratio          | 1.5                      | REJECT           | Media      |
| Max position size (% equity)   | 2%                       | REJECT           | Alta       |
| Blacklisted symbols            | Configurable por tenant  | REJECT           | Baja       |
| Circuit breaker abierto        | Cualquier umbral roto    | REJECT + CLOSE   | Crítica    |
| Trading hours check            | Mercado abierto          | REJECT           | Baja       |

### Formato de Datos: Risk Check Request

```json
{
  "check_id": "risk_check_001",
  "order": {
    "symbol": "EURUSD",
    "direction": "BUY",
    "type": "MARKET",
    "quantity": 0.1,
    "entry_price": 1.0850,
    "stop_loss": 1.0820,
    "take_profit": 1.0910
  },
  "account_id": "acc_001",
  "tenant_id": "tenant_abc",
  "timestamp": "2026-07-14T15:30:00.005Z"
}
```

### Formato de Datos: Risk Check Response

```json
{
  "check_id": "risk_check_001",
  "approved": true,
  "risk_score": 23,
  "risk_level": "LOW",
  "rules_evaluated": 6,
  "rules_passed": 6,
  "rules_failed": 0,
  "adjusted_params": {
    "quantity": 0.1,
    "stop_loss": 1.0820,
    "take_profit": 1.0910,
    "max_slippage_pips": 3
  },
  "current_exposure": {
    "symbol_exposure": 45000,
    "total_exposure": 78000,
    "daily_drawdown_pct": 2.1,
    "orders_this_hour": 3
  },
  "evaluated_at": "2026-07-14T15:30:00.010Z",
  "latency_ms": 5
}
```

---

## 3. AI Signal Scoring → Classification → Recommendation

**Descripción:** Flujo del pipeline de AI/ML que toma una señal raw, la
enriquece con features, la evalúa con modelos ML, y genera un score
de confianza con explicabilidad.

**Latencia objetivo:** < 500ms (p99)  
**SLA del flujo:** 99.9%  
**Servicios involucrados:** 5  

```
+=========================================================================+
|  FLUJO 3: AI SIGNAL SCORING → CLASSIFICATION → RECOMMENDATION          |
+=========================================================================+
|                                                                          |
| [Market        [Feature       [Signal        [LLM         [Regime      |
|  Data]          Engin.]        Scorer]       Gateway]     Detector]    |
|                                                                          |
|  |               |              |              |             |          |
|  | OHLC Data     |              |              |             |          |
|  | (H1, M15, M5) |              |              |             |          |
|  |-------------->|              |              |             |          |
|  |               |              |              |             |          |
|  |               | [3a] CALC    |              |             |          |
|  |               | 50+ FEATURES |              |             |          |
|  |               | (100ms)      |              |             |          |
|  |               |              |              |             |          |
|  |               | SMA(20,50)   |              |             |          |
|  |               | EMA(12,26)   |              |             |          |
|  |               | RSI(14)      |              |             |          |
|  |               | MACD(12,26,9)|              |             |          |
|  |               | BB(20,2)     |              |             |          |
|  |               | ATR(14)      |              |             |          |
|  |               | ADX(14)      |              |             |          |
|  |               | Volume Profile|             |             |          |
|  |               | Candlestick  |              |             |          |
|  |               | Patterns     |              |             |          |
|  |               |              |              |             |          |
|  | NATS:        |              |              |             |          |
|  | ai.features  |              |              |             |          |
|  | .updated     |              |              |             |          |
|  |- - - - - - - - - - - - ->  |              |             |          |
|  |               |              |              |             |          |
|  |               | [3b] QUANT   |              |             |          |
|  |               | SCORING      |              |             |          |
|  |               | (50ms)       |              |             |          |
|  |               |              |              |             |          |
|  |               | Random Forest|              |             |          |
|  |               | + XGBoost    |              |             |          |
|  |               |              |              |             |          |
|  |               | Quant Score: |              |             |          |
|  |               | 72/100       |              |             |          |
|  |               |              |              |             |          |
|  |               | [3c] ENRICH  |              |             |          |
|  |               | WITH CONTEXT |              |             |          |
|  |               | (50ms)       |              |             |          |
|  |               |              |              |             |          |
|  |               | Current Regime:              |             |          |
|  |               |< - - - - - - - - - - - - - - - - - - - - |          |
|  |               | "TRENDING"   |              |    (cached) |          |
|  |               |              |              |             |          |
|  |               | [3d] LLM ANALYSIS           |             |          |
|  |               | (200ms)      |              |             |          |
|  |               |              |              |             |          |
|  |               | Query:       |              |             |          |
|  |               | "Analyze BUY signal for EURUSD             |          |
|  |               |  given: RSI=62, MACD bullish,              |          |
|  |               |  regime=trending, ATR=0.0035"              |          |
|  |               |────────────────────────>  |             |          |
|  |               |              |              |             |          |
|  |               |              | [3d.1] CALL  |             |          |
|  |               |              | OLLAMA       |             |          |
|  |               |              | /api/generate|             |          |
|  |               |              | (150ms)      |             |          |
|  |               |              |              |             |          |
|  |               | LLM Response:              |             |          |
|  |               | "BUY signal aligns with    |             |          |
|  |               |  current uptrend. RSI not  |             |          |
|  |               |  overbought. MACD confirms |             |          |
|  |               |  momentum. RECOMMENDED."   |             |          |
|  |               |<────────────────────────── |             |          |
|  |               |              |              |             |          |
|  |               | [3e] COMBINE SCORES         |             |          |
|  |               | (quant + LLM) |             |             |          |
|  |               | (20ms)       |              |             |          |
|  |               |              |              |             |          |
|  |               | Combined:    |              |             |          |
|  |               | Quant: 72    |              |             |          |
|  |               | LLM: 85      |              |             |          |
|  |               | Weighted:    |              |             |          |
|  |               | 72*0.6 +     |              |             |          |
|  |               | 85*0.4 = 77.2|              |             |          |
|  |               |              |              |             |          |
|  |               | NATS:        |              |             |          |
|  |               | trading.     |              |             |          |
|  |               | signal.scored|              |             |          |
|  |               |< - - - - - - -|             |             |          |
|  |               |              |              |             |          |
|  v               v              v              v             v          |
|                                                                          |
|  RESUMEN DE TIMING:                                                      |
|  [3a] Feature Engineering ───────────────────────────────────> 100ms    |
|  [3b] Quant Scoring ─────────────────────────────────────────> 150ms    |
|  [3c] Context Enrichment ────────────────────────────────────> 200ms    |
|  [3d] LLM Analysis ──────────────────────────────────────────> 400ms    |
|  [3e] Score Combination ─────────────────────────────────────> 420ms    |
|  [3f] Publish Scored Signal ─────────────────────────────────> 450ms    |
|                                                                          |
|  TOTAL TARGET: < 500ms (p99)                                            |
+=========================================================================+
```

### Formato de Datos: Scored Signal

```json
{
  "signal_id": "sig_abc123",
  "score": {
    "quantitative": 72,
    "llm_analysis": 85,
    "combined": 77.2,
    "confidence_level": "HIGH",
    "recommendation": "BUY",
    "explanation": "BUY signal aligns with current uptrend. RSI at 62 (not overbought). MACD confirms bullish momentum. Regime is trending favoring trend-following strategies.",
    "risk_factors": [
      "Approaching resistance at 1.0870",
      "Upcoming NFP data in 3 hours"
    ]
  },
  "features_snapshot": {
    "rsi_14": 62.3,
    "macd_hist": 0.0012,
    "bb_position": 0.65,
    "atr_14": 0.0035,
    "adx_14": 28.5,
    "regime": "trending"
  },
  "model_version": "v2.3.1",
  "scored_at": "2026-07-14T15:30:00.420Z"
}
```

### Modelo de Ponderación para Score Combinado

| Componente              | Peso   | Fuente                     | Latencia |
|-------------------------|--------|----------------------------|----------|
| Quantitative (ML)       | 60%    | Random Forest + XGBoost    | 50ms     |
| LLM Analysis            | 40%    | Ollama (Llama3 8B)         | 200ms    |
| Regime Context          | Bonus  | Cache (actualiza cada 15m) | 0ms      |
| Feature Quality         | Pena   | Missing data penalty       | 0ms      |

### Umbrales de Clasificación

| Score Range  | Classification | Acción Sugerida                       |
|--------------|----------------|---------------------------------------|
| 85-100       | STRONG BUY     | Ejecutar con size estándar            |
| 70-84        | BUY            | Ejecutar con size reducido (75%)      |
| 50-69        | NEUTRAL        | No ejecutar, mantener en watchlist    |
| 30-49        | SELL           | Considerar cierre de posiciones long  |
| 15-29        | STRONG SELL    | Ejecutar cierre + posible short      |
| 0-14         | AVOID          | No operar este activo                 |

---

## 4. User Authentication → OAuth2 → JWT → RBAC

**Descripción:** Flujo completo de autenticación y autorización. Cubre
login OAuth2, emisión de JWT, validación de tokens, y verificación
de permisos RBAC en cada request.

**Latencia objetivo:** < 20ms para validación de token existente  
**SLA del flujo:** 99.99%  
**Servicios involucrados:** 4  

```
+=========================================================================+
|  FLUJO 4: USER AUTHENTICATION → OAuth2 → JWT → RBAC                     |
+=========================================================================+
|                                                                          |
| [User/Browser]  [Traefik]     [Auth Service]  [Redis]    [PostgreSQL]   |
|                                                                          |
|  === FASE A: LOGIN ===                                                   |
|                                                                          |
|  | POST /auth/login           |              |            |             |
|  | {email, password}          |              |            |             |
|  |--------------------------->|              |            |             |
|  |                            |              |            |             |
|  |                            | Forward to   |            |             |
|  |                            | Auth Service |            |             |
|  |                            |------------->|            |             |
|  |                            |              |            |             |
|  |                            | [4a] VALIDATE|            |             |
|  |                            | CREDENTIALS  |            |             |
|  |                            | (5ms)        |            |             |
|  |                            |              |            |             |
|  |                            | Query user   |            |             |
|  |                            | by email     |            |             |
|  |                            |-------------------------------------->|
|  |                            |              |            |             |
|  |                            | User record  |            |             |
|  |                            | (bcrypt hash)|            |             |
|  |                            |<--------------------------------------|
|  |                            | (5ms)        |            |             |
|  |                            |              |            |             |
|  |                            | Compare      |            |             |
|  |                            | bcrypt hash  |            |             |
|  |                            | (10ms)       |            |             |
|  |                            |              |            |             |
|  |                            | [4b] GENERATE|            |             |
|  |                            | JWT PAIR     |            |             |
|  |                            | (1ms)        |            |             |
|  |                            |              |            |             |
|  |                            | Access Token:|            |             |
|  |                            | {sub, tenant,|            |             |
|  |                            |  roles, exp} |            |             |
|  |                            | TTL: 15min   |            |             |
|  |                            |              |            |             |
|  |                            | Refresh Token:            |             |
|  |                            | {sub, jti}   |            |             |
|  |                            | TTL: 7 days  |            |             |
|  |                            |              |            |             |
|  |                            | Store session|            |             |
|  |                            |-------------------------------------->|
|  |                            |              | (session    |             |
|  |                            |              |  data)      |             |
|  |                            |              | TTL: 7d     |             |
|  |                            |              |            |             |
|  |  {access_token,           |              |            |             |
|  |   refresh_token,          |              |            |             |
|  |   user: {id, name,        |              |            |             |
|  |   roles, permissions}}    |              |            |             |
|  |<---------------------------|              |            |             |
|  | (20ms total)              |              |            |             |
|                                                                          |
|  === FASE B: AUTHENTICATED REQUEST ===                                   |
|                                                                          |
|  | GET /api/trading/orders    |              |            |             |
|  | Authorization: Bearer <JWT>|              |            |             |
|  |--------------------------->|              |            |             |
|  |                            |              |            |             |
|  |                            | [4c] VALIDATE|            |             |
|  |                            | JWT SIGNATURE|            |             |
|  |                            | (0.1ms)      |            |             |
|  |                            |              |            |             |
|  |                            | RSA-256 sig  |            |             |
|  |                            | verification |            |             |
|  |                            |              |            |             |
|  |                            | [4d] CHECK   |            |             |
|  |                            | TOKEN EXPIRY |            |             |
|  |                            | (0.01ms)     |            |             |
|  |                            |              |            |             |
|  |                            | exp > now?   |            |             |
|  |                            | YES → continue|           |             |
|  |                            |              |            |             |
|  |                            | [4e] RBAC    |            |             |
|  |                            | CHECK        |            |             |
|  |                            | (0.5ms)      |            |             |
|  |                            |              |            |             |
|  |                            | Role: trader |            |             |
|  |                            | Permission:  |            |             |
|  |                            | order:read   |            |             |
|  |                            | ✓ GRANTED    |            |             |
|  |                            |              |            |             |
|  |                            | [4f] FORWARD |            |             |
|  |                            | TO SERVICE   |            |             |
|  |                            |              |            |             |
|  |                            | Trading      |            |             |
|  |                            | Engine       |            |             |
|  |                            |------------->|            |             |
|  |                            |              |            |             |
|  |  {orders: [...]}          |              |            |             |
|  |<---------------------------|              |            |             |
|  | (< 5ms total)             |              |            |             |
+=========================================================================+
```

### Estructura JWT

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key_2026_07"
  },
  "payload": {
    "sub": "user_123456",
    "tenant": "tenant_abc",
    "roles": ["trader", "viewer"],
    "permissions": [
      "order:create",
      "order:read",
      "order:cancel",
      "signal:subscribe",
      "account:read"
    ],
    "account_ids": ["acc_001", "acc_002"],
    "plan": "pro",
    "iat": 1689426300,
    "exp": 1689427200,
    "iss": "tnsvt-auth",
    "aud": "tnsvt-api"
  }
}
```

### Matriz RBAC

| Rol         | order:create | order:read | order:cancel | signal:subscribe | signal:create | account:read | account:manage | admin:all |
|-------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Admin       | ✅  | ✅  | ✅  | ✅  | ✅  | ✅  | ✅  | ✅  |
| Manager     | ✅  | ✅  | ✅  | ✅  | ✅  | ✅  | ✅  | ❌  |
| Trader      | ✅  | ✅  | ✅  | ✅  | ❌  | ✅  | ❌  | ❌  |
| Viewer      | ❌  | ✅  | ❌  | ✅  | ❌  | ✅  | ❌  | ❌  |
| API         | ✅  | ✅  | ✅  | ✅  | ❌  | ✅  | ❌  | ❌  |

### Rate Limiting por Tier

| Tier     | Requests/min | Burst   | Window  |
|----------|-------------|---------|---------|
| Free     | 60          | 10      | 1min    |
| Starter  | 300         | 50      | 1min    |
| Pro      | 1,000       | 200     | 1min    |
| Enterprise | 10,000    | 2,000   | 1min    |

---

## 5. Billing → Subscription → License Check

**Descripción:** Flujo de verificación de licencia que ocurre antes de
permitir acciones de trading. Valida que el tenant tiene una suscripción
activa y dentro de los límites de su plan.

**Latencia objetivo:** < 5ms (cached)  
**SLA del flujo:** 99.9%  
**Servicios involucrados:** 4  

```
+=========================================================================+
|  FLUJO 5: BILLING → SUBSCRIPTION → LICENSE CHECK                        |
+=========================================================================+
|                                                                          |
| [Trading       [Billing       [Redis Cache]  [PostgreSQL]              |
|  Engine]        Service]                                                |
|                                                                          |
|  | LicenseCheck |              |              |                        |
|  | (tenant_id,  |              |              |                        |
|  |  action,     |              |              |                        |
|  |  account_id) |              |              |                        |
|  |------------->|              |              |                        |
|  |              |              |              |                        |
|  |              | [5a] CHECK   |              |                        |
|  |              | CACHE        |              |                        |
|  |              | (0.5ms)      |              |                        |
|  |              |              |              |                        |
|  |              | Get license: |              |                        |
|  |              | license:     |              |                        |
|  |              | tenant:abc   |              |                        |
|  |              |------------->|              |                        |
|  |              |              |              |                        |
|  |              | Cache HIT    |              |                        |
|  |              | {            |              |                        |
|  |              |  plan: "pro",|              |                        |
|  |              |  status:     |              |                        |
|  |              |  "active",   |              |                        |
|  |              |  orders_today: 45,          |                        |
|  |              |  max_orders: 200,           |                        |
|  |              |  signals_today: 120,        |                        |
|  |              |  max_signals: 500           |                        |
|  |              | }            |              |                        |
|  |              |<------------|              |                        |
|  |              |              |              |                        |
|  |              | [5b] CHECK   |              |                        |
|  |              | LIMITS       |              |                        |
|  |              | (0.1ms)      |              |                        |
|  |              |              |              |                        |
|  |              | action:      |              |                        |
|  |              | "place_order"|              |                        |
|  |              | orders_today:|              |                        |
|  |              | 45 < 200     |              |                        |
|  |              | ✓ PASS       |              |                        |
|  |              |              |              |                        |
|  |              | [5c] INCREMENT              |                        |
|  |              | COUNTER      |              |                        |
|  |              | (0.5ms)      |              |                        |
|  |              |              |              |                        |
|  |              | INCR         |              |                        |
|  |              | billing:     |              |                        |
|  |              | tenant:abc:  |              |                        |
|  |              | orders:      |              |                        |
|  |              | 2026-07-14   |              |                        |
|  |              |------------->|              |                        |
|  |              | NEW: 46      |              |                        |
|  |              |<------------|              |                        |
|  |              |              |              |                        |
|  |              | [5d] CHECK   |              |                        |
|  |              | USAGE ALERT  |              |                        |
|  |              | (0.1ms)      |              |                        |
|  |              |              |              |                        |
|  |              | 46/200 = 23% |              |                        |
|  |              | (< 80% → OK) |              |                        |
|  |              |              |              |                        |
|  | LicenseOK    |              |              |                        |
|  | {allowed:    |              |              |                        |
|  |  true,       |              |              |                        |
|  |  remaining:  |              |              |                        |
|  |  154,        |              |              |                        |
|  |  plan: "pro"}|              |              |                        |
|  |<------------|              |              |                        |
|  | (2ms cached) |              |              |                        |
|  |              |              |              |                        |
|  === CACHE MISS (cada 5 min) ===                                       |
|  |              |              |              |                        |
|  | LicenseCheck |              |              |                        |
|  |------------->|              |              |                        |
|  |              | Cache MISS   |              |                        |
|  |              |------------->|              |                        |
|  |              | nil          |              |                        |
|  |              |<------------|              |                        |
|  |              |              |              |                        |
|  |              | [5e] QUERY   |              |                        |
|  |              | DB           |              |                        |
|  |              | (5ms)        |              |                        |
|  |              |              |              |                        |
|  |              | SELECT * FROM|              |                        |
|  |              | subscriptions|              |                        |
|  |              | WHERE tenant |              |                        |
|  |              | = 'abc'      |              |                        |
|  |              | AND status = |              |                        |
|  |              | 'active'     |              |                        |
|  |              |-------------------------------------->             |
|  |              |              |              |                        |
|  |              | Subscription |              |                        |
|  |              | record       |              |                        |
|  |              |<--------------------------------------             |
|  |              | (5ms)        |              |                        |
|  |              |              |              |                        |
|  |              | [5f] POPULATE|              |                        |
|  |              | CACHE        |              |                        |
|  |              | TTL: 5 min   |              |                        |
|  |              |------------->|              |                        |
|  |              | OK           |              |                        |
|  |              |<------------|              |                        |
|  |              |              |              |                        |
|  | LicenseOK    |              |              |                        |
|  |<------------|              |              |                        |
|  | (10ms cold)  |              |              |                        |
+=========================================================================+
```

### Tabla de Planes

| Plan        | Precio/mes | Órdenes/día | Signals/día | API calls/mes | Brokers | Features               |
|-------------|------------|-------------|-------------|---------------|---------|------------------------|
| Free        | $0         | 10          | 50          | 1,000         | 1       | Basic                  |
| Starter     | $29        | 100         | 300         | 10,000        | 2       | Copy trading           |
| Pro         | $99        | 500         | 1,000       | 100,000       | 5       | AI scoring, backtest   |
| Enterprise  | Custom     | Unlimited   | Unlimited   | Unlimited     | All     | White-label, SLA       |

### Alertas de Uso

| Umbral | Acción                                    | Notificación               |
|--------|-------------------------------------------|-----------------------------|
| 50%    | Warning                                   | Email + In-app              |
| 80%    | Alert                                     | Email + Telegram            |
| 95%    | Critical                                  | Telegram + SMS              |
| 100%   | Hard limit (reject new orders)            | Telegram + SMS + In-app     |
| 100%+1d| Suspension (si persiste 3 días)           | Email + admin alert         |

---

## 6. Copy Trading: One Signal → Multiple Accounts

**Descripción:** Flujo de copy trading que muestra cómo una única señal
del master account se propaga a múltiples follower accounts con
configuración individual (lote, SL, TP, filtros).

**Latencia objetivo:** < 50ms para todas las copias combinadas  
**SLA del flujo:** 99.95%  
**Servicios involucrados:** 5  

```
+=========================================================================+
|  FLUJO 6: COPY TRADING — ONE SIGNAL → MULTIPLE ACCOUNTS                |
+=========================================================================+
|                                                                          |
| [Master        [Copy Trading   [Broker       [Risk         [Audit       |
|  Account]       Router]         Gateway]      Manager]      Engine]     |
|                                                                          |
|  | Master Signal |              |              |             |          |
|  | (BUY EURUSD   |              |              |             |          |
|  |  0.1 lot)     |              |              |             |          |
|  |-------------->|              |              |             |          |
|  |               |              |              |             |          |
|  |               | [6a] QUERY   |              |             |          |
|  |               | COPY CONFIG  |              |             |          |
|  |               | FOR MASTER   |              |             |          |
|  |               | (2ms)        |              |             |          |
|  |               |              |              |             |          |
|  |               | SELECT * FROM|              |             |          |
|  |               | copy_config  |              |             |          |
|  |               | WHERE master |              |             |          |
|  |               | = 'master_1' |              |             |          |
|  |               | AND active=  |              |             |          |
|  |               | true         |              |             |          |
|  |               |              |              |             |          |
|  |               | RESULT:      |              |             |          |
|  |               | 4 followers: |              |             |          |
|  |               |              |              |             |          |
|  |               | Follower A:  |              |             |          |
|  |               |  lot: 0.01   |              |             |          |
|  |               |  sl: 25 pips |              |             |          |
|  |               |  tp: 50 pips |              |             |          |
|  |               |  filter: ALL |              |             |          |
|  |               |  broker: MT5 |              |             |          |
|  |               |              |              |             |          |
|  |               | Follower B:  |              |             |          |
|  |               |  lot: 0.1    |              |             |          |
|  |               |  sl: 50 pips |              |             |          |
|  |               |  tp: 100 pips|              |             |          |
|  |               |  filter: FX  |              |             |          |
|  |               |  broker: cT  |              |             |          |
|  |               |              |              |             |          |
|  |               | Follower C:  |              |             |          |
|  |               |  lot: 0.05   |              |             |          |
|  |               |  sl: 30 pips |              |             |          |
|  |               |  tp: 60 pips |              |             |          |
|  |               |  filter:     |              |             |          |
|  |               |  RISK<30%    |              |             |          |
|  |               |  broker: BN  |              |             |          |
|  |               |              |              |             |          |
|  |               | Follower D:  |              |             |          |
|  |               |  lot: 0.005  |              |             |          |
|  |               |  sl: 20 pips |              |             |          |
|  |               |  tp: 40 pips |              |             |          |
|  |               |  filter: ALL |              |             |          |
|  |               |  broker: MT5 |              |             |          |
|  |               |              |              |             |          |
|  |               | [6b] APPLY   |              |             |          |
|  |               | FILTERS      |              |             |          |
|  |               | (1ms)        |              |             |          |
|  |               |              |              |             |          |
|  |               | A: ✓ ALL     |              |             |          |
|  |               | B: ✓ EURUSD  |              |             |          |
|  |               |    is FX     |              |             |          |
|  |               | C: ✓ RISK    |              |             |          |
|  |               |    score 23  |              |             |          |
|  |               |    < 30      |              |             |          |
|  |               | D: ✓ ALL     |              |             |          |
|  |               |              |              |             |          |
|  |               | 4/4 followers|              |             |          |
|  |               | eligible     |              |             |          |
|  |               |              |              |             |          |
|  |               | [6c] SCALE   |              |             |          |
|  |               | PARAMETERS   |              |             |          |
|  |               | (1ms)        |              |             |          |
|  |               |              |              |             |          |
|  |               | Master: 0.1 lot             |             |          |
|  |               |              |              |             |          |
|  |               | A: 0.1 * 0.01/0.1 = 0.01   |             |          |
|  |               | B: 0.1 * 0.1/0.1  = 0.1    |             |          |
|  |               | C: 0.1 * 0.05/0.1 = 0.05   |             |          |
|  |               | D: 0.1 * 0.005/0.1= 0.005  |             |          |
|  |               |              |              |             |          |
|  |               | [6d] PARALLEL │              |             |          |
|  |               | RISK + EXECUTE│              |             |          |
|  |               |              |              |             |          |
|  |               | === FOLLOWER A (MT5) ===     |             |          |
|  |               |--RiskCheck-->|              |             |          |
|  |               |  ✓ Approved   |              |             |          |
|  |               |---Execute---->|              |             |          |
|  |               |  ✓ Filled     |              |             |          |
|  |               |              |              |             |          |
|  |               | === FOLLOWER B (cTrader) === |             |          |
|  |               |--RiskCheck-->|              |             |          |
|  |               |  ✓ Approved   |              |             |          |
|  |               |---Execute---->|              |             |          |
|  |               |  ✓ Filled     |              |             |          |
|  |               |              |              |             |          |
|  |               | === FOLLOWER C (Binance) === |             |          |
|  |               |--RiskCheck-->|              |             |          |
|  |               |  ✓ Approved   |              |             |          |
|  |               |---Execute---->|              |             |          |
|  |               |  ✓ Filled     |              |             |          |
|  |               |              |              |             |          |
|  |               | === FOLLOWER D (MT5) ===     |             |          |
|  |               |--RiskCheck-->|              |             |          |
|  |               |  ✓ Approved   |              |             |          |
|  |               |---Execute---->|              |             |          |
|  |               |  ✓ Filled     |              |             |          |
|  |               |              |              |             |          |
|  |               | [6e] AGGREGATE|              |             |          |
|  |               | RESULTS      |              |             |          |
|  |               | (2ms)        |              |             |          |
|  |               |              |              |             |          |
|  |               | Audit:       |              |             |          |
|  |               | CopyTradeExecuted:          |             |          |
|  |               | master=master_1             |             |          |
|  |               | signal=sig_abc123           |             |          |
|  |               | followers=4                 |             |          |
|  |               | executed=4                  |             |          |
|  |               | failed=0                    |             |          |
|  |               |----------------------------->|             |          |
|  |               |              |              | [6f] Store  |          |
|  |               |              |              | Event       |          |
|  |               |              |              | (5ms)       |          |
|  |               |              |              |             |          |
|  v               v              v              v             v          |
|                                                                          |
|  RESUMEN:                                                               |
|  Master signal → 4 followers → 4 risk checks → 4 executions            |
|  Tiempo total: < 50ms (paralelo)                                        |
+=========================================================================+
```

### Tabla de Configuración de Copy Trading

| Campo                 | Tipo         | Descripción                                    |
|-----------------------|--------------|-------------------------------------------------|
| `copy_config_id`      | UUID         | ID único de configuración                       |
| `master_account_id`   | UUID         | Cuenta master cuya señal se copia               |
| `follower_account_id` | UUID         | Cuenta que recibe la copia                      |
| `lot_scaling`         | DECIMAL      | Factor de escala (0.01 = 1% del master)        |
| `fixed_lot`           | DECIMAL      | Lote fijo (override de lot_scaling)            |
| `sl_pips`             | INT          | Stop loss en pips (override del master)         |
| `tp_pips`             | INT          | Take profit en pips (override del master)       |
| `sl_multiplier`       | DECIMAL      | Multiplicador del SL del master (1.0 = igual)   |
| `tp_multiplier`       | DECIMAL      | Multiplicador del TP del master (1.0 = igual)   |
| `max_position_size`   | DECIMAL      | Límite máximo de posición                       |
| `filter_symbols`      | TEXT[]       | Filtro de símbolos (ALL, FOREX, CRYPTO, custom) |
| `filter_max_risk`     | DECIMAL      | Risk score máximo para copiar (0-100)           |
| `filter_min_confidence`| DECIMAL     | Score mínimo de la señal para copiar            |
| `active`              | BOOLEAN      | Si la copia está activa                         |
| `broker_config`       | JSONB        | Configuración específica del broker destino     |

---

## 7. Backtesting → Walk Forward → Optimization → Deployment

**Descripción:** Flujo completo de backtesting que incluye walk-forward
optimization, validación out-of-sample, y deployment automático
de la estrategia ganadora.

**Tiempo estimado:** 5-30 minutos (dependiendo del dataset)  
**SLA del flujo:** 99.5%  
**Servicios involucrados:** 4  

```
+=========================================================================+
|  FLUJO 7: BACKTESTING → WALK FORWARD → OPTIMIZATION → DEPLOYMENT       |
+=========================================================================+
|                                                                          |
| [User/CLI]   [Backtesting   [Strategy     [TimescaleDB] [Trading        |
|              Service]        Engine]                     Engine]        |
|                                                                          |
|  | BacktestRequest|            |              |             |          |
|  | {strategy_id,  |            |              |             |          |
|  |  symbol,       |            |              |             |          |
|  |  start_date,   |            |              |             |          |
|  |  end_date,     |            |              |             |          |
|  |  params: {     |            |              |             |          |
|  |    sma_fast:   |            |              |             |          |
|  |    [10..30],   |            |              |             |          |
|  |    sma_slow:   |            |              |             |          |
|  |    [50..200],  |            |              |             |          |
|  |    rsi_thresh: |            |              |             |          |
|  |    [30..70]    |            |              |             |          |
|  |  }}            |            |              |             |          |
|  |--------------->|            |              |             |          |
|  |                |            |              |             |          |
|  |                | [7a] LOAD  |              |             |          |
|  |                | HISTORICAL |              |             |          |
|  |                | DATA       |              |             |          |
|  |                | (2-10s)    |              |             |          |
|  |                |            |              |             |          |
|  |                | SELECT *   |              |             |          |
|  |                | FROM ohlc  |              |             |          |
|  |                | WHERE sym= |              |             |          |
|  |                | 'EURUSD'   |              |             |          |
|  |                | AND tf='H1'|              |             |          |
|  |                | AND date   |              |             |          |
|  |                | BETWEEN    |              |             |          |
|  |                | '2021-01-01'              |             |          |
|  |                | AND        |              |             |          |
|  |                | '2026-06-30'|             |             |          |
|  |                |------------|------------->|             |          |
|  |                |            | 5.5 years    |             |          |
|  |                |            | of H1 candles|             |          |
|  |                |            | (~48K bars)  |             |          |
|  |                |<-----------|--------------|             |          |
|  |                |            |              |             |          |
|  |                | [7b] WALK  |              |             |          |
|  |                | FORWARD    |              |             |          |
|  |                | OPTIMIZATION              |             |          |
|  |                | (30-120s)  |              |             |          |
|  |                |            |              |             |          |
|  |                | Split:     |              |             |          |
|  |                | Train: 2021-2024 (3y)    |             |          |
|  |                | Test: 2025-2026 (1.5y)   |             |          |
|  |                |            |              |             |          |
|  |                | Window 1:  |              |             |          |
|  |                |  Train: 2021-2022        |             |          |
|  |                |  Test: 2023-Q1           |             |          |
|  |                |  Optimize: SMA(12,89),   |             |          |
|  |                |   RSI(35) → Sharpe 1.8   |             |          |
|  |                |            |              |             |          |
|  |                | Window 2:  |              |             |          |
|  |                |  Train: 2021-2023        |             |          |
|  |                |  Test: 2023-Q2-Q3        |             |          |
|  |                |  Optimize: SMA(15,100),  |             |          |
|  |                |   RSI(40) → Sharpe 1.5   |             |          |
|  |                |            |              |             |          |
|  |                | Window 3:  |              |             |          |
|  |                |  Train: 2021-2023Q4      |             |          |
|  |                |  Test: 2024-Q1-Q2        |             |          |
|  |                |  Optimize: SMA(18,120),  |             |          |
|  |                |   RSI(38) → Sharpe 1.6   |             |          |
|  |                |            |              |             |          |
|  |                | ... (continua con más    |             |          |
|  |                |  windows hasta hoy)      |             |          |
|  |                |            |              |             |          |
|  |                | [7c] AGGREGATE RESULTS    |             |          |
|  |                | (1s)       |              |             |          |
|  |                |            |              |             |          |
|  |                | OOS Metrics (out-of-sample):             |          |
|  |                | - Sharpe Ratio: 1.55     |             |          |
|  |                | - Max Drawdown: -12.3%   |             |          |
|  |                | - Win Rate: 58.2%        |             |          |
|  |                | - Profit Factor: 1.82    |             |          |
|  |                | - Total Return: +67.4%   |             |          |
|  |                | - Trades: 847            |             |          |
|  |                | - Avg Trade: +$45.20     |             |          |
|  |                |            |              |             |          |
|  |                | [7d] MONTE |              |             |          |
|  |                | CARLO SIM  |              |             |          |
|  |                | (10-30s)   |              |             |          |
|  |                |            |              |             |          |
|  |                | 1000 random|              |             |          |
|  |                | permutations              |             |          |
|  |                |            |              |             |          |
|  |                | 95% CI:    |              |             |          |
|  |                | Return:    |              |             |          |
|  |                | [42%, 95%] |              |             |          |
|  |                | Sharpe:    |              |             |          |
|  |                | [1.1, 2.0] |              |             |          |
|  |                |            |              |             |          |
|  |                | [7e] VALIDATE|             |             |          |
|  |                | THRESHOLDS |              |             |          |
|  |                | (1ms)      |              |             |          |
|  |                |            |              |             |          |
|  |                | Min Sharpe: 1.0 → ✓     |             |          |
|  |                | Max DD: 20% → ✓ (-12.3%) |             |          |
|  |                | Min Trades: 100 → ✓      |             |          |
|  |                | Min Win Rate: 45% → ✓    |             |          |
|  |                |            |              |             |          |
|  |                | ALL VALIDATION PASSED     |             |          |
|  |                |            |              |             |          |
|  | BacktestResult |            |              |             |          |
|  | {metrics,      |            |              |             |          |
|  |  params,       |            |              |             |          |
|  |  equity_curve, |            |              |             |          |
|  |  trades,       |            |              |             |          |
|  |  approved: true}|           |              |             |          |
|  |<---------------|            |              |             |          |
|  |                |            |              |             |          |
|  === DEPLOYMENT (si approved) ===                                      |
|  |                |            |              |             |          |
|  | User confirms  |            |              |             |          |
|  | deployment     |            |              |             |          |
|  |--------------->|            |              |             |          |
|  |                |            |              |             |          |
|  |                | [7f] SAVE  |              |             |          |
|  |                | STRATEGY   |              |             |          |
|  |                | VERSION    |              |             |          |
|  |                |------------|------------->|             |          |
|  |                |            |              |             |          |
|  |                | strategy_versions:         |             |          |
|  |                | v3.2 (params, metrics,     |             |          |
|  |                |  status: "active")         |             |          |
|  |                |<-----------|--------------|             |          |
|  |                |            |              |             |          |
|  |                | NATS:      |              |             |          |
|  |                | trading.   |              |             |          |
|  |                | strategy.  |              |             |          |
|  |                | deployed   |              |             |          |
|  |                |- - - - - - - - - - - - - - - - - - - ->|          |
|  |                |            |              | [7g] Activate          |
|  |                |            |              | Strategy   |          |
|  |                |            |              | (1ms)      |          |
|  v                v            v              v             v          |
+=========================================================================+
```

### Métricas de Backtesting

| Métrica                  | Fórmula / Descripción                             | Target    |
|--------------------------|---------------------------------------------------|-----------|
| Sharpe Ratio             | (Return - Risk-free) / StdDev                     | > 1.0     |
| Sortino Ratio            | (Return - Risk-free) / DownsideStdDev             | > 1.5     |
| Max Drawdown             | Máxima caída desde pico a valle                    | < 20%     |
| Win Rate                 | Trades ganadores / Total trades                   | > 45%     |
| Profit Factor            | Gross Profit / Gross Loss                         | > 1.5     |
| Expectancy               | (Win% × AvgWin) - (Loss% × AvgLoss)              | > $0      |
| Calmar Ratio             | Annual Return / Max Drawdown                       | > 1.0     |
| Recovery Factor          | Net Profit / Max Drawdown                          | > 2.0     |
| Max Consecutive Losses   | Mayor racha de pérdidas consecutivas               | < 10      |
| Average Trade Duration   | Duración promedio de cada trade                    | Variable  |

---

## 8. Heartbeat → Health Check → Recovery → Failover

**Descripción:** Flujo de resiliencia que monitorea la salud de cada
servicio, detecta fallos, ejecuta recuperación automática, y activa
failover cuando es necesario.

**Latencia de detección:** < 5 segundos  
**SLA del flujo:** 99.99%  
**Servicios involucrados:** 6  

```
+=========================================================================+
|  FLUJO 8: HEARTBEAT → HEALTH CHECK → RECOVERY → FAILOVER              |
+=========================================================================+
|                                                                          |
| [Service A]  [K8s Probe]  [Prometheus]  [AlertMgr]  [Service B] [K8s]  |
| (Broker GW)  (liveness)   (scraper)     (evaluator) (MT5 Adpt)  (kube) |
|                                                                          |
|  === NORMAL OPERATION ===                                                |
|                                                                          |
|  | Heartbeat   |              |              |             |          |
|  | /healthz    |              |              |             |          |
|  | (cada 10s)  |              |              |             |          |
|  |------------>|              |              |             |          |
|  |             |              |              |             |          |
|  | {status:    |              |              |             |          |
|  |  "healthy", |              |              |             |          |
|  |  uptime:    |              |              |             |          |
|  |  "72h",     |              |              |             |          |
|  |  connections:              |              |             |          |
|  |  {mt5: 3,   |              |              |             |          |
|  |   cT: 2,    |              |              |             |          |
|  |   bn: 5},   |              |              |             |          |
|  |  metrics: {  |              |              |             |          |
|  |    orders_  |              |              |             |          |
|  |    per_sec: |              |              |             |          |
|  |    45.2,    |              |              |             |          |
|  |    p99_ms:  |              |              |             |          |
|  |    18       |              |              |             |          |
|  |  }}         |              |              |             |          |
|  |<------------|              |              |             |          |
|  | (HTTP 200)  |              |              |             |          |
|  |             |              |              |             |          |
|  |             | [8a] SCRAPE  |              |             |          |
|  |             | METRICS      |              |             |          |
|  |             | (cada 15s)   |              |             |          |
|  |             |              |              |             |          |
|  |             | HTTP GET     |              |             |          |
|  |             | :8100/metrics|              |             |          |
|  |             |------------->|              |             |          |
|  |             |              |              |             |          |
|  |             | # HELP       |              |             |          |
|  |             | broker_      |              |             |          |
|  |             | orders_total |              |             |          |
|  |             | # TYPE       |              |             |          |
|  |             | broker_      |              |             |          |
|  |             | orders_total |              |             |          |
|  |             | counter 12847|              |             |          |
|  |             |              |              |             |          |
|  |             | broker_      |              |             |          |
|  |             | latency_p99  |              |             |          |
|  |             | 18.5         |              |             |          |
|  |             |              |              |             |          |
|  |             |<------------|              |             |          |
|  |             | (Prometheus  |              |             |          |
|  |             |  format)     |              |             |          |
|  |             |              |              |             |          |
|  |             | [8b] EVALUATE|              |             |          |
|  |             | ALERT RULES  |              |             |          |
|  |             | (cada 15s)   |              |             |          |
|  |             |              |              |             |          |
|  |             | Rule:        |              |             |          |
|  |             | broker_      |              |             |          |
|  |             | latency_p99  |              |             |          |
|  |             | > 100?       |              |             |          |
|  |             | 18.5 > 100?  |              |             |          |
|  |             | NO → OK      |              |             |          |
|  |             |              |              |             |          |
|  === FAILURE DETECTED ===                                               |
|  |             |              |              |             |          |
|  | [MT5 Adapter|              |              |             |          |
|  |  CRASHES]   |              |              |             |          |
|  |             |              |              |             |          |
|  | [8c] LIVENESS|             |              |             |          |
|  | CHECK FAILS |              |              |             |          |
|  | (3 fallos   |              |              |             |          |
|  |  consecutivos|             |              |             |          |
|  |  = 30s)     |              |              |             |          |
|  |             |              |              |             |          |
|  | HTTP GET    |              |              |             |          |
|  | :8101/healthz|             |              |             |          |
|  | TIMEOUT     |              |              |             |          |
|  |------------>|              |              |             |          |
|  |             |              |              |             |          |
|  |             | [8d] K8s RESTART             |             |          |
|  |             | CONTAINER    |              |             |          |
|  |             | (auto)       |              |             |          |
|  |             |              |              |             |          |
|  |             | kubectl      |              |             |          |
|  |             | delete pod   |              |             |          |
|  |             | mt5-adapter- |              |             |          |
|  |             | xxx          |              |             |          |
|  |             |              |              |             |          |
|  |             | [8e] NEW POD  |              |             |          |
|  |             | SPAWNS       |              |             |          |
|  |             | (15-30s)     |              |             |          |
|  |             |              |              |             |          |
|  |             | [8f] READINESS|             |             |          |
|  |             | CHECK        |              |             |          |
|  |             |              |              |             |          |
|  |             | HTTP GET     |              |             |          |
|  |             | :8101/ready  |              |             |          |
|  |             | (cada 5s)    |              |             |          |
|  |             |              |              |             |          |
|  |             | Attempt 1: DB not ready → WAIT|             |          |
|  |             | Attempt 2: DB not ready → WAIT|             |          |
|  |             | Attempt 3: MT5 disconnected → RECONNECT    |          |
|  |             | Attempt 4: MT5 connected → READY           |          |
|  |             |              |              |             |          |
|  |             | [8g] TRAFFIC RESUMED         |             |          |
|  |             |              |              |             |          |
|  === FAILOVER SCENARIO ===                                              |
|  |             |              |              |             |          |
|  | [Broker GW  |              |              |             |          |
|  |  detects MT5|              |              |             |          |
|  |  adapter    |              |              |             |          |
|  |  unreachable|              |              |             |          |
|  |  for 30s]   |              |              |             |          |
|  |             |              |              |             |          |
|  | [8h] CIRCUIT|              |              |             |          |
|  | BREAKER     |              |              |             |          |
|  | OPENS       |              |              |             |          |
|  |             |              |              |             |          |
|  | State:      |              |              |             |          |
|  | CLOSED →    |              |              |             |          |
|  | OPEN        |              |              |             |          |
|  |             |              |              |             |          |
|  | [8i] ALERT  |              |              |             |          |
|  | FIRES       |              |              |             |          |
|  |             |              |              |             |          |
|  | NATS: risk.circuit.open    |              |             |          |
|  |------------------------------------------->|             |          |
|  |             |              |              |             |          |
|  |             | [8j] SEND    |              |             |          |
|  |             | ALERT        |              |             |          |
|  |             |              |              |             |          |
|  |             | Telegram:    |              |             |          |
|  |             | "MT5 Adapter |              |             |          |
|  |             |  DOWN. 3/5   |              |             |          |
|  |             |  orders      |              |             |          |
|  |             |  pending.    |              |             |          |
|  |             |  Circuit     |              |             |          |
|  |             |  breaker     |              |             |          |
|  |             |  OPEN."      |              |             |          |
|  |             |              |              |             |          |
|  |             | [8k] HALF-   |              |             |          |
|  |             | OPEN after   |              |             |          |
|  |             | cooldown     |              |             |          |
|  |             | (5 min)      |              |             |          |
|  |             |              |              |             |          |
|  |             | [8l] PROBE   |              |             |          |
|  |             | CONNECTION   |              |             |          |
|  |             |              |              |             |          |
|  |             | Send test    |              |             |          |
|  |             | order (0 lot)|              |             |          |
|  |             |────────────────────────────────────────── >|          |
|  |             |              |              |    [MT5 OK] |          |
|  |             |<────────────────────────────────────────── |          |
|  |             |              |              |             |          |
|  |             | [8m] CLOSED  |              |             |          |
|  |             | (normal)     |              |             |          |
|  |             |              |              |             |          |
|  v             v              v              v             v          |
+=========================================================================+
```

### Estados del Circuit Breaker

```
+=========================================================================+
|                    CIRCUIT BREAKER STATE MACHINE                        |
+=========================================================================+
|                                                                          |
|                    +-----------+                                         |
|  Normal            |           | Failure threshold exceeded             |
|  Operation   ----->|  CLOSED   |----->+                                |
|  (allow all)|      |           |      |                                |
|  |               |+-----------+      v                                |
|  |               |             +-----------+                           |
|  |               |             |           |                           |
|  |               |<------------|   OPEN    |                           |
|  |               | Half-open   |           |                           |
|  |               | probe       | Reject all|                           |
|  |               | succeeds    | requests  |                           |
|  |               |             |           |                           |
|  |               |             +-----+-----+                           |
|  |               |                   |                                  |
|  |               |                   | Cooldown period                  |
|  |               |                   | (5 min default)                  |
|  |               |                   v                                  |
|  |               |             +-----------+                           |
|  |               |             |           |                           |
|  +<--------------|-------------| HALF-OPEN |                           |
|  |               |             |           |                           |
|  |               |             | Probe 1   |                           |
|  |               |             | request   |                           |
|  |               |             |           |                           |
|  |               |             +-----+-----+                           |
|  |               |                   |                                  |
|  |               |          +--------+--------+                        |
|  |               |          |                 |                        |
|  |               v          v                 v                        |
|  |          SUCCESS      FAILURE          TIMEOUT                     |
|  |          (CLOSED)     (OPEN)           (OPEN)                       |
|  |               |          |                 |                        |
|  |               +----------+----------------+                        |
|  |                          |                                         |
|  +<--------------------------+                                         |
|                                                                          |
|  Configuración por defecto:                                            |
|  - Failure threshold: 3 consecutive failures                           |
|  - Cooldown period: 5 minutes                                          |
|  - Half-open probe: 1 request                                          |
|  - Success threshold to close: 1                                       |
+=========================================================================+
```

### Tabla de Health Checks

| Servicio          | Endpoint       | Interval | Timeout | Healthy Threshold | Unhealthy Threshold |
|-------------------|----------------|----------|---------|-------------------|---------------------|
| Trading Engine    | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| Risk Manager      | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| Broker Gateway    | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| MT5 Adapter       | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| AI/ML Services    | /healthz       | 30s      | 10s     | 1 success         | 3 failures          |
| Data Ingestion    | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| Auth Service      | /healthz       | 10s      | 5s      | 1 success         | 3 failures          |
| PostgreSQL        | TCP 5432       | 10s      | 5s      | 1 success         | 3 failures          |
| Redis             | PING           | 10s      | 2s      | 1 success         | 3 failures          |
| NATS              | PING           | 10s      | 2s      | 1 success         | 3 failures          |

### Métricas de Resiliencia

| Métrica                          | Target      | Fórmula                                    |
|----------------------------------|-------------|---------------------------------------------|
| Mean Time Between Failures       | > 90 días   | Total uptime / number of failures           |
| Mean Time to Detection           | < 5 segundos| Time from failure to alert                  |
| Mean Time to Recovery            | < 15 minutos| Time from detection to resolution           |
| Mean Time to Restart             | < 30 segundos| Time from pod delete to ready              |
| Failover Success Rate            | > 99%       | Successful failovers / total failovers      |
| Data Loss During Failover        | 0 events    | Events lost during failover                 |
| Circuit Breaker Open Events/mes  | < 5         | CB open triggered per month                 |
| Recovery Without Data Loss       | 100%        | Events recoverable from Event Store         |

---

## Aprobaciones

| Rol                  | Nombre           | Fecha       | Estado    |
|----------------------|------------------|-------------|-----------|
| CTO                  | ________________ | ____/__/__ | Pendiente |
| Lead Architect       | ________________ | ____/__/__ | Pendiente |
| QA Lead              | ________________ | ____/__/__ | Pendiente |

---

*Documento generado como parte del proceso de arquitectura de TNSVT V2.*
*Documento anterior: [02-SERVICES-CATALOG.md](02-SERVICES-CATALOG.md)*
*Proximo documento: [04-DATA-MODEL.md](04-DATA-MODEL.md)*
