# AI-CORE.md — Arquitectura del Motor de Inteligencia Artificial

**Proyecto:** TNSVT V2 — Plataforma SaaS de Trading  
**Versión:** 2.0.0  
**Última Actualización:** 2026-07-14  
**Estado:** Documento de Arquitectura — Fase de Diseño  

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Arquitectura General del AI Core](#2-arquitectura-general-del-ai-core)
3. [Detección de Régimen de Mercado](#3-detección-de-régimen-de-mercado)
4. [Scoring de Señales](#4-scoring-de-señales)
5. [Detección de Overtrading](#5-detección-de-overtrading)
6. [Análisis de Sentimiento](#6-análisis-de-sentimiento)
7. [Motor RAG](#7-motor-rag)
8. [Agente LLM (Ollama)](#8-agente-llm-ollama)
9. [Optimizador de Parámetros](#9-optimizador-de-parámetros)
10. [Detector de Anomalías](#10-detector-de-anomalías)
11. [Comunicación con Otros Servicios](#11-comunicación-con-otros-servicios)
12. [Servicio de Modelos](#12-servicio-de-modelos)
13. [Pipeline de Entrenamiento](#13-pipeline-de-entrenamiento)
14. [Seguridad y Cumplimiento](#14-seguridad-y-cumplimiento)
15. [Métricas y Observabilidad](#15-métricas-y-observabilidad)

---

## 1. Resumen Ejecutivo

El **AI Core** es el cerebro analítico de TNSVT V2. Representa el componente más crítico
de la plataforma, proporcionando capacidades de inteligencia artificial que transforman
datos de mercado en decisiones de trading accionables. Opera como un sistema distribuido
compuesto por múltiples microservicios especializados, todos comunicándose a través de
NATS Messaging.

### Principios Rectores

| Principio | Descripción |
|-----------|-------------|
| **Autonomía Controlada** | El agente LLM opera con autonomía definida por políticas de riesgo configurables |
| **Degradación Graciosa** | Si AI Core falla, el sistema de trading continúa operando con señales de fallback |
| **Latencia Predecible** | Scoring < 50ms p99, Detección de régimen < 200ms p99 |
| **Aprendizaje Continuo** | Reentrenamiento automático con walk-forward validation |
| **Multi-Tenant** | Modelos y datos aislados por tenant con shared infrastructure |
| **Zero Trust** | Validación criptográfica de cada inferencia y decisión |

---

## 2. Arquitectura General del AI Core

### 2.1 Diagrama de Arquitectura Completa

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI CORE — VISTA ALTA                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    CAPA DE INGESTA DE DATOS                          │   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │   │
│  │  │ WebSocket   │  │ News Feed   │  │ Social M.   │  │ Historial │  │   │
│  │  │ Market Data │  │ Aggregator  │  │ Scraper     │  │ DB Loader │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │   │
│  │         │                │                │               │         │   │
│  │         └────────┬───────┴───────┬────────┘               │         │   │
│  │                  │               │                        │         │   │
│  │           ┌──────▼──────┐  ┌─────▼────────┐        ┌─────▼──────┐  │   │
│  │           │ NATS:       │  │ NATS:        │        │ TimescaleDB│  │   │
│  │           │ market.     │  │ sentiment.   │        │ Historical │  │   │
│  │           │ tick.*      │  │ news.*       │        │ Data Store │  │   │
│  │           └──────┬──────┘  └──────┬───────┘        └─────┬──────┘  │   │
│  └──────────────────┼───────────────┼────────────────────────┘         │   │
│                     │               │                                   │   │
│  ┌──────────────────▼───────────────▼────────────────────────────────┐  │   │
│  │                   CAPA DE PROCESAMIENTO                            │  │   │
│  │                                                                    │  │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐  │  │   │
│  │  │ Regime          │  │ Signal         │  │ Overtrading        │  │  │   │
│  │  │ Detector        │  │ Scorer         │  │ Detector           │  │  │   │
│  │  │                 │  │                │  │                    │  │  │   │
│  │  │ • Vol Cluster   │  │ • ML Model     │  │ • Frequency Mon.   │  │  │   │
│  │  │ • ADX Analysis  │  │ • Context Feat │  │ • Loss Streak Mon. │  │  │   │
│  │  │ • Hurst Exp.    │  │ • Correlation  │  │ • Strategy Deviat. │  │  │   │
│  │  │ • Volatility    │  │ • Time-of-Day  │  │ • Correlation An.  │  │  │   │
│  │  └───────┬────────┘  └───────┬────────┘  └──────────┬─────────┘  │  │   │
│  │          │                   │                       │            │  │   │
│  │  ┌───────┴────────┐  ┌──────┴─────────┐  ┌─────────┴──────────┐  │  │   │
│  │  │ Anomaly         │  │ Parameter      │  │ Sentiment          │  │  │   │
│  │  │ Detector        │  │ Optimizer      │  │ Analyzer           │  │  │   │
│  │  │                 │  │                │  │                    │  │  │   │
│  │  │ • Price Anom.   │  │ • Bayesian Opt │  │ • News NLP         │  │  │   │
│  │  │ • Spread Anom.  │  │ • Walk-Forward │  │ • Social Sentiment │  │  │   │
│  │  │ • Volume Spike  │  │ • Grid Search  │  │ • Fear & Greed     │  │  │   │
│  │  └───────┬────────┘  └──────┬────────┘  └──────────┬─────────┘  │  │   │
│  └──────────┼──────────────────┼───────────────────────┼────────────┘  │   │
│             │                  │                       │                │   │
│  ┌──────────▼──────────────────▼───────────────────────▼────────────┐  │   │
│  │                   CAPA DE INFERENCIA                               │  │   │
│  │                                                                    │  │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │   │
│  │  │              OLLAMA INFERENCE SERVER                         │  │  │   │
│  │  │                                                             │  │  │   │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │  │  │   │
│  │  │  │ Llama 3  │  │ Mixtral  │  │ Phi-3    │  │ Custom    │  │  │  │   │
│  │  │  │ 8B/70B   │  │ 8x7B     │  │ 3.8B     │  │ Finetuned │  │  │  │   │
│  │  │  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │  │  │   │
│  │  │                                                             │  │  │   │
│  │  │  GPU Pool: NVIDIA A100 / RTX 4090 (shared)                 │  │  │   │
│  │  │  Model Cache: LRU with preloaded hot models                 │  │  │   │
│  │  │  Quantization: GGUF Q4_K_M / Q5_K_M                       │  │  │   │
│  │  └─────────────────────────────────────────────────────────────┘  │  │   │
│  │                                                                    │  │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │   │
│  │  │           RAG ENGINE (pgvector + Ollama Embeddings)         │  │  │   │
│  │  │                                                             │  │  │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │  │  │   │
│  │  │  │ Strategies   │  │ Backtest     │  │ Market Analysis  │ │  │  │   │
│  │  │  │ Docs Store   │  │ Results DB   │  │ Archive          │ │  │  │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────┘ │  │  │   │
│  │  │  Embeddings: nomic-embed-text (1536d)                     │  │  │   │
│  │  │  Similarity: Cosine + HNSW indexing                        │  │  │   │
│  │  └─────────────────────────────────────────────────────────────┘  │  │   │
│  └────────────────────────────┬───────────────────────────────────────┘  │   │
│                               │                                          │   │
│  ┌────────────────────────────▼───────────────────────────────────────┐  │   │
│  │                   CAPA DE DECISIÓN                                  │  │   │
│  │                                                                    │  │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │  │   │
│  │  │ Decision          │  │ Risk Gate        │  │ Action         │  │  │   │
│  │  │ Orchestrator      │  │ (Policy Engine)  │  │ Executor       │  │  │   │
│  │  │                   │  │                  │  │                │  │  │   │
│  │  │ Combina todos     │  │ Valida contra    │  │ Envía órdenes  │  │  │   │
│  │  │ los scores en     │  │ reglas de riesgo │  │ al broker via  │  │  │   │
│  │  │ una señal final   │  │ del tenant       │  │ Trading Core   │  │  │   │
│  │  └─────────┬────────┘  └────────┬─────────┘  └───────┬────────┘  │  │   │
│  └────────────┼────────────────────┼────────────────────┼────────────┘  │   │
│               │                    │                    │               │   │
│  ┌────────────▼────────────────────▼────────────────────▼────────────┐  │   │
│  │                   CAPA DE ALMACENAMIENTO                           │  │   │
│  │                                                                    │  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐│  │   │
│  │  │ TimescaleDB   │  │ Redis        │  │ PostgreSQL + pgvector     ││  │   │
│  │  │ Time-Series   │  │ Cache/State  │  │ Vector Store + Metadata   ││  │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────┘│  │   │
│  └───────────────────────────────────────────────────────────────────┘  │   │
│                                                                         │   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Componentes Principales

| Componente | Lenguaje | Responsabilidad | Latencia Objetivo |
|------------|----------|-----------------|-------------------|
| Regime Detector | Python | Clasificar estado del mercado | < 200ms |
| Signal Scorer | Python | Puntuar señales 0-100 | < 50ms |
| Overtrading Detector | Go | Monitorear patrones de trading | < 10ms |
| Sentiment Analyzer | Python | Análisis NLP de noticias | < 500ms |
| RAG Engine | Python | Recuperación contextual | < 300ms |
| LLM Agent | Python/Ollama | Análisis autónomo | < 2000ms |
| Parameter Optimizer | Python | Optimización Bayesiana | < 5s (batch) |
| Anomaly Detector | Go | Detección en tiempo real | < 20ms |

### 2.3 Flujo de Datos General

```
  Mercado (WebSocket)     Noticias (API)      Redes Sociales
        │                     │                      │
        ▼                     ▼                      ▼
  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐
  │ Tick Processor│    │ News Parser  │    │ Social Scraper   │
  └──────┬──────┘    └──────┬───────┘    └────────┬─────────┘
         │                  │                     │
         ▼                  ▼                     ▼
  ┌──────────────────────────────────────────────────────────┐
  │              NATS JetStream (Event Bus)                   │
  │                                                          │
  │  market.tick.EURUSD  │  sentiment.news  │  social.twitter │
  └──────────┬───────────┴──────────┬───────┴────────────────┘
             │                     │
     ┌───────┼─────────────────────┼───────┐
     │       │                     │       │
     ▼       ▼                     ▼       ▼
  ┌──────┐┌──────┐           ┌──────┐┌──────────┐
  │Regime││Anomaly│           │Senti-││Parameter │
  │Detect││Detect │           │ment  ││Optimizer │
  └──┬───┘└──┬───┘           └──┬───┘└────┬─────┘
     │       │                  │         │
     ▼       ▼                  ▼         ▼
  ┌──────────────────────────────────────────────┐
  │          Signal Scoring Engine                │
  │  (Combina: régimen + anomalía + sentimiento)  │
  └──────────────────┬───────────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────────┐
  │         Overtrading + Risk Gate               │
  └──────────────────┬───────────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────────┐
  │         Action Executor → Trading Core        │
  └──────────────────────────────────────────────┘
```

---

## 3. Detección de Régimen de Mercado

### 3.1 Objetivo

Clasificar el estado actual del mercado para cada instrumento en una de las siguientes
categorías en tiempo real:

| Régimen | Descripción | Estrategia Recomendada |
|---------|-------------|------------------------|
| `TRENDING_UP` | Tendencia alcista definida | Trend following, momentum |
| `TRENDING_DOWN` | Tendencia bajista definida | Trend following, momentum |
| `RANGING` | Mercado lateral, sin tendencia | Mean reversion, grid trading |
| `HIGH_VOLATILITY` | Volatilidad elevada, movimientos amplios | Reducir tamaño, ampliar SL |
| `LOW_VOLATILITY` | Volatilidad reducida, compressión | Scalping, breakout anticipado |
| `BREAKOUT` | Ruptura de rango con volumen | Entrada agresiva, trailing stop |
| `CRISIS` | Movimiento extremo, liquidez baja | No operar, hedge posiciones |

### 3.2 Algoritmo de Detección

```
┌──────────────────────────────────────────────────────────────┐
│              PIPELINE DE DETECCIÓN DE RÉGIMEN                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Input: OHLCV Data (últimos N períodos)                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ PASO 1: Volatilidad Clustering (GARCH(1,1))            │  │
│  │                                                        │  │
│  │ σ²(t) = ω + α·ε²(t-1) + β·σ²(t-1)                    │  │
│  │                                                        │  │
│  │ Clasificar:                                            │  │
│  │   σ(t) < σ_25   → LOW_VOL                             │  │
│  │   σ_25 ≤ σ < σ_75 → NORMAL_VOL                        │  │
│  │   σ(t) ≥ σ_75   → HIGH_VOL                            │  │
│  └───────────────────────┬────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼────────────────────────────────┐  │
│  │ PASO 2: Fuerza de Tendencia (ADX + DI)                 │  │
│  │                                                        │  │
│  │ ADX > 25 AND +DI > -DI  → TRENDING_UP                 │  │
│  │ ADX > 25 AND -DI > +DI  → TRENDING_DOWN               │  │
│  │ ADX ≤ 25                 → No trending (RANGING?)      │  │
│  │                                                        │  │
│  │ Smoothed TR = SMA(TR, 14)                             │  │
│  │ Smoothed +DM = SMA(+DM, 14)                           │  │
│  │ Smoothed -DM = SMA(-DM, 14)                           │  │
│  │ DX = |+DM - (-DM)| / (+DM + (-DM)) × 100              │  │
│  │ ADX = SMA(DX, 14)                                     │  │
│  └───────────────────────┬────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼────────────────────────────────┐  │
│  │ PASO 3: Exponente de Hurst                             │  │
│  │                                                        │  │
│  │ H > 0.5  → Tendencia persistente (momentum)            │  │
│  │ H = 0.5  → Random walk                                │  │
│  │ H < 0.5  → Mean reversion                             │  │
│  │                                                        │  │
│  │ Calculado sobre ventana de 100 períodos                │  │
│  │ usando R/S Analysis: H = log(R/S) / log(N)            │  │
│  └───────────────────────┬────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼────────────────────────────────┐  │
│  │ PASO 4: Detección de Breakout                          │  │
│  │                                                        │  │
│  │ Bollinger Band Width squeeze < percentil 10            │  │
│  │ followed by price closing outside bands                │  │
│  │ + Volume > 2× average volume                           │  │
│  │ → Classify as BREAKOUT                                 │  │
│  └───────────────────────┬────────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼────────────────────────────────┐  │
│  │ PASO 5: Combinación y Suavizado                        │  │
│  │                                                        │  │
│  │ regime_score = weighted_average(                        │  │
│  │   0.35 × garch_class,                                 │  │
│  │   0.30 × adx_class,                                   │  │
│  │   0.20 × hurst_class,                                 │  │
│  │   0.15 × breakout_class                               │  │
│  │ )                                                      │  │
│  │                                                        │  │
│  │ Aplicar EMA suavizado para evitar flickering           │  │
│  │ Transición solo si cambio ≥ 20% en score ponderado     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Output: RegimeSignal {                                      │
│    instrument: "EURUSD",                                     │
│    regime: TRENDING_UP,                                      │
│    confidence: 0.87,                                         │
│    sub_scores: { garch: 0.9, adx: 0.85, hurst: 0.7 },      │
│    timestamp: 2026-07-14T10:30:00Z,                         │
│    valid_until: 2026-07-14T10:45:00Z                        │
│  }                                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Configuración por Tenant

```json
{
  "regime_detection": {
    "enabled": true,
    "instruments": ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"],
    "update_interval_seconds": 60,
    "lookback_periods": 100,
    "garch_params": {
      "omega": 0.000001,
      "alpha": 0.1,
      "beta": 0.85
    },
    "adx_threshold": 25,
    "hurst_window": 100,
    "breakout_volume_multiplier": 2.0,
    "smoothing_ema_period": 5,
    "transition_threshold": 0.20
  }
}
```

### 3.4 Almacenamiento de Estados de Régimen

Los estados de régimen se almacenan como hipertables en TimescaleDB:

```sql
CREATE TABLE market_regime (
  time         TIMESTAMPTZ NOT NULL,
  instrument   TEXT NOT NULL,
  tenant_id    UUID NOT NULL,
  regime       TEXT NOT NULL,
  confidence   DOUBLE PRECISION NOT NULL,
  garch_score  DOUBLE PRECISION,
  adx_score    DOUBLE PRECISION,
  hurst_score  DOUBLE PRECISION,
  adx_value    DOUBLE PRECISION,
  atr_value    DOUBLE PRECISION,
  bb_width     DOUBLE PRECISION
);

SELECT create_hypertable('market_regime', 'time');
CREATE INDEX idx_regime_instrument ON market_regime (instrument, time DESC);
```

---

## 4. Scoring de Señales

### 4.1 Arquitectura del Scorer

El Signal Scorer asigna una puntuación de 0 a 100 a cada señal de trading antes de
que sea ejecutada. Utiliza un modelo de Gradient Boosting entrenado con histórico de
señales y sus resultados.

### 4.2 Features de Entrada

| Categoría | Feature | Descripción | Tipo |
|-----------|---------|-------------|------|
| **Régimen** | `regime_type` | Estado actual del mercado | Categórico |
| **Régimen** | `regime_confidence` | Confianza de la clasificación | Float [0,1] |
| **Régimen** | `adx_value` | Valor ADX actual | Float |
| **Régimen** | `atr_pct` | ATR como % del precio | Float |
| **Historial** | `signal_win_rate_7d` | Win rate de señales similares (7d) | Float [0,1] |
| **Historial** | `signal_avg_return_30d` | Retorno promedio (30d) | Float |
| **Historial** | `signal_sharpe_30d` | Sharpe ratio (30d) | Float |
| **Historial** | `total_signals_today` | Señales ejecutadas hoy | Integer |
| **Temporal** | `hour_of_day` | Hora del día (0-23) | Integer |
| **Temporal** | `day_of_week` | Día de la semana (0-6) | Integer |
| **Temporal** | `is_news_window` | Dentro de ventana de noticias | Boolean |
| **Correlación** | `correlated_positions` | Posiciones correlacionadas activas | Integer |
| **Correlación** | `portfolio_heat` | Exposición total del portafolio | Float |
| **Mercado** | `spread_pct` | Spread actual en % | Float |
| **Mercado** | `volume_vs_avg` | Volumen vs promedio | Float |
| **Mercado** | `bid_ask_imbalance` | Desequilibrio bid/ask | Float [-1,1] |
| **Sentimiento** | `sentiment_score` | Score de sentimiento [-1,1] | Float |
| **Sentimiento** | `sentiment_confidence` | Confianza del sentimiento | Float [0,1] |
| **Anomalía** | `anomaly_score` | Score de anomalía detectada | Float [0,1] |

### 4.3 Pipeline de Scoring

```
┌──────────────────────────────────────────────────────────────┐
│                SIGNAL SCORING PIPELINE                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Señal Bruta (from strategy)                                 │
│       │                                                      │
│       ▼                                                      │
│  ┌─────────────────┐                                         │
│  │ Feature          │ ← Regime State, Historical DB,         │
│  │ Extraction       │   Sentiment Cache, Anomaly Stream      │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐     ┌─────────────────────────────┐    │
│  │ Feature          │     │ Feature Store (Redis)        │    │
│  │ Enrichment       │────►│ Pre-computed features        │    │
│  └────────┬────────┘     │ updated every 60s            │    │
│           │              └─────────────────────────────┘    │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ ML Model         │  XGBoost / LightGBM                   │
│  │ Inference        │  Model loaded from Ollama/custom       │
│  │ (onnxruntime)    │  Inference < 10ms                     │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Score            │  raw_score → sigmoid → calibrated      │
│  │ Calibration      │  Calibrado contra distribución         │
│  │                  │  histórica de win rates                │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Threshold        │  score ≥ 70 → EXECUTE                 │
│  │ Decision         │  50 ≤ score < 70 → MONITOR            │
│  │                  │  score < 50 → REJECT                   │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  SignalScore {                                               │
│    score: 82,                                                │
│    action: EXECUTE,                                          │
│    confidence: 0.91,                                         │
│    explanation: "Strong trend + positive sentiment",         │
│    feature_importance: { regime: 0.35, win_rate: 0.25, ... }│
│  }                                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Modelo de Scoring

```python
class SignalScorer:
    """
    Scoring de señales basado en ML con calibración.
    Modelo: XGBoost Classifier (binario: win/loss)
    """
    
    FEATURE_COLUMNS = [
        'regime_type_encoded', 'regime_confidence', 'adx_value',
        'atr_pct', 'signal_win_rate_7d', 'signal_avg_return_30d',
        'signal_sharpe_30d', 'total_signals_today', 'hour_of_day',
        'day_of_week', 'is_news_window', 'correlated_positions',
        'portfolio_heat', 'spread_pct', 'volume_vs_avg',
        'bid_ask_imbalance', 'sentiment_score', 'sentiment_confidence',
        'anomaly_score'
    ]
    
    THRESHOLDS = {
        'execute': 70,
        'monitor': 50,
        'reject': 0
    }
    
    def score(self, signal: RawSignal, context: MarketContext) -> SignalScore:
        features = self.extract_features(signal, context)
        raw_probability = self.model.predict_proba(features)[0][1]
        calibrated_score = self.calibrator.transform(raw_probability)
        
        return SignalScore(
            score=calibrated_score,
            action=self._classify_action(calibrated_score),
            confidence=raw_probability,
            feature_importance=self._explain(features),
            model_version=self.model_version
        )
```

### 4.5 Reentrenamiento Automático

```
┌─────────────────────────────────────────────────────────┐
│           CICLO DE REENTRENAMIENTO                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Cada 7 días (domingo 02:00 UTC):                       │
│                                                         │
│  1. Recopilar señales de los últimos 30 días            │
│  2. Calcular resultados reales (P&L)                    │
│  3. Dividir: 70% train, 15% val, 15% test              │
│  4. Entrenar nuevo modelo con walk-forward              │
│  5. Validar: nueva_AUC > vieja_AUC × 1.02              │
│  6. Si pasa: promover a producción                      │
│  7. Si no: mantener modelo actual + alerta              │
│  8. Actualizar feature store con nuevas features        │
│  9. Log de métricas para monitoring                     │
│                                                         │
│  Walk-Forward: ventanas de 7 días, validación 1 día     │
│  Mínimo de muestras: 500 señales por reentrenamiento    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. Detección de Overtrading

### 5.1 Métricas Monitoreadas

| Métrica | Umbral de Alerta | Umbral de Bloqueo | Ventana |
|---------|-------------------|-------------------|---------|
| Frecuencia de trades | > 20/hora | > 50/hora | 1 hora |
| Pérdidas consecutivas | ≥ 3 | ≥ 5 | Sesión |
| Desviación de estrategia | > 15% del drawdown máximo | > 25% del drawdown máximo | 24 horas |
| Drawdown actual | > 5% del balance | > 10% del balance | Diario |
| Correlación de posiciones | > 0.8 con posiciones existentes | > 0.95 | Tiempo real |
| Tamaño de posición vs promedio | > 3× promedio | > 5× promedio | 7 días |
| Drawdown semanal | > 8% del balance | > 15% del balance | 7 días |
| Ratio pérdida/ganancia | < 1.5 durante 20 trades | < 1.0 durante 30 trades | Variable |

### 5.2 Pipeline de Detección

```
┌──────────────────────────────────────────────────────────────────┐
│               OVERTRADING DETECTION PIPELINE                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Evento: Nueva orden ejecutada                                   │
│       │                                                          │
│       ▼                                                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Frecuencia Monitor                                          │  │
│  │ • Contador de trades en ventana deslizante de 1 hora       │  │
│  │ • Si > UMBRAL_ALERTA: emitir NATS event `ot.warning`       │  │
│  │ • Si > UMBRAL_BLOQUEO: emitir NATS event `ot.block`        │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
│                                     │                            │
│  ┌──────────────────────────────────▼─────────────────────────┐  │
│  │ Consecutive Loss Detector                                   │  │
│  │ • Mantener ventana de últimas 50 trades                     │  │
│  │ • Contar streak de pérdidas desde el final                  │  │
│  │ • Si ≥ 3: reducir tamaño de posición 25%                   │  │
│  │ • Si ≥ 5: suspender trading 4 horas + notificación         │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
│                                     │                            │
│  ┌──────────────────────────────────▼─────────────────────────┐  │
│  │ Strategy Deviation Monitor                                  │  │
│  │ • Comparar acciones reales contra plan de la estrategia    │  │
│  │ • Calcular desviación % del drawdown máximo esperado       │  │
│  │ • Si > 15%: alertar al trader                              │  │
│  │ • Si > 25%: pausar estrategia + requiere aprobación       │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
│                                     │                            │
│  ┌──────────────────────────────────▼─────────────────────────┐  │
│  │ Correlation Analyzer                                        │  │
│  │ • Calcular correlación de posiciones activas                │  │
│  │ • Si correlación > 0.8: advertencia de concentración       │  │
│  │ • Si correlación > 0.95: bloquear nueva posición           │  │
│  │ • Factor de diversificación: 1 - max_correlation            │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
│                                     │                            │
│                                     ▼                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Decision Engine                                           │   │
│  │                                                           │   │
│  │ ACCIONES:                                                 │   │
│  │ • PASS: No hay overtrading                                │   │
│  │ • WARN: Emitir alerta, continuar                          │   │
│  │ • REDUCE: Reducir tamaño de posición                      │   │
│  │ • PAUSE: Pausar estrategia temporalmente                  │   │
│  │ • BLOCK: Bloquear nuevas órdenes                          │   │
│  │ • EMERGENCY: Cerrar todas las posiciones                  │   │
│  └──────────────────────────────────┬───────────────────────┘   │
│                                     │                           │
│                                     ▼                           │
│                          NATS → overtrading.action.*             │
│                          → Trading Core ejecuta                  │
│                          → Notificación al usuario              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.3 Configuración de Alertas por Tenant

```json
{
  "overtrading_protection": {
    "enabled": true,
    "levels": {
      "frequency_hourly_warning": 20,
      "frequency_hourly_block": 50,
      "consecutive_loss_warning": 3,
      "consecutive_loss_block": 5,
      "drawdown_daily_warning_pct": 5.0,
      "drawdown_daily_block_pct": 10.0,
      "drawdown_weekly_warning_pct": 8.0,
      "drawdown_weekly_block_pct": 15.0,
      "correlation_warning": 0.8,
      "correlation_block": 0.95
    },
    "actions": {
      "on_warning": ["notify", "log"],
      "on_reduce": ["notify", "reduce_position_25pct", "log"],
      "on_pause": ["notify", "pause_strategy", "log", "email"],
      "on_block": ["notify", "block_orders", "log", "email", "sms"],
      "on_emergency": ["close_all", "notify", "log", "email", "sms", "call"]
    },
    "cooldown_minutes": 60,
    "require_manual_reset": true
  }
}
```

---

## 6. Análisis de Sentimiento

### 6.1 Fuentes de Datos

| Fuente | Tipo | Frecuencia | Latencia | Costo |
|--------|------|------------|----------|-------|
| Financial news APIs | Estructurada | Cada 5 min | < 30s | $50-200/mes |
| Twitter/X API | Social | Cada 2 min | < 10s | $100-500/mes |
| Reddit (r/wallstreetbets, r/forex) | Social | Cada 10 min | < 60s | Gratis |
| Fed/Central Bank releases | Oficial | Event-driven | < 5 min | Gratis |
| Earnings calendars | Estructurada | Diario | < 1 hora | $20-100/mes |
| Fear & Greed Index | Agregado | Diario | < 1 hora | Gratis |
| VIX / Volatility indices | Mercado | Tiempo real | < 1s | Incluido en datos |

### 6.2 Pipeline de Análisis

```
┌──────────────────────────────────────────────────────────────────┐
│                 SENTIMENT ANALYSIS PIPELINE                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ News API │  │ Twitter  │  │ Reddit   │  │ Fed News │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │
│       ▼              ▼              ▼              ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Text Normalization Layer                      │   │
│  │  • Remove noise, URLs, emojis                            │   │
│  │  • Extract relevant entities (companies, pairs)           │   │
│  │  • Language detection (en, es, pt, zh)                    │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Sentiment Model (Ollama)                      │   │
│  │                                                            │   │
│  │  Modelo: fine-tuned Phi-3 (3.8B) para sentimiento         │   │
│  │  • Input: texto normalizado + contexto del mercado        │   │
│  │  • Output: { sentiment: -1..+1, confidence: 0..1,        │   │
│  │             entities: [...], topics: [...] }              │   │
│  │                                                            │   │
│  │  Para texto financiero se usa prompt especializado:       │   │
│  │  "Analyze the following financial text and provide..."    │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Aggregation & Decay                           │   │
│  │                                                            │   │
│  │  • Agregar sentimiento por instrumento                    │   │
│  │  • Aplicar decaimiento temporal: score × e^(-λ×t)        │   │
│  │  • λ = 0.1 por hora (noticias pierden influencia)        │   │
│  │  • Pesos por fuente: News=0.4, Twitter=0.3,              │   │
│  │    Reddit=0.2, Official=0.1                               │   │
│  │                                                            │   │
│  │  sentiment_final = Σ(weight_i × score_i × decay_i)        │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│                      NATS: sentiment.update.{instrument}         │
│                      Redis: cache:sentiment:{instrument}         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 Modelo de Sentimiento Financiero

```python
SENTIMENT_PROMPT_TEMPLATE = """
You are a financial sentiment analysis expert. Analyze the following text
and provide a sentiment assessment for the specified financial instrument.

Text: "{text}"
Instrument: {instrument}
Current Market Context: {context}

Respond in JSON format:
{{
  "sentiment_score": <-1.0 to 1.0>,
  "confidence": <0.0 to 1.0>,
  "impact_duration": "<immediate|short_term|medium_term|long_term>",
  "key_factors": ["factor1", "factor2"],
  "risk_level": "<low|medium|high|extreme>",
  "summary": "<one line summary>"
}}
"""
```

---

## 7. Motor RAG

### 7.1 Arquitectura RAG

```
┌──────────────────────────────────────────────────────────────────┐
│                    RAG ENGINE ARCHITECTURE                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                FASE 1: INDEXACIÓN                          │   │
│  │                                                            │   │
│  │  Fuentes de Conocimiento:                                  │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐ │   │
│  │  │ Documentos de │  │ Resultados de │  │ Análisis de   │ │   │
│  │  │ Estrategias   │  │ Backtesting   │  │ Mercado       │ │   │
│  │  │ (.md, .pdf)   │  │ (JSON, CSV)   │  │ (archivos)    │ │   │
│  │  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘ │   │
│  │          │                   │                   │         │   │
│  │          ▼                   ▼                   ▼         │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │ Chunking Pipeline                                    │  │   │
│  │  │ • Text splitting: 512 tokens, 50 token overlap      │  │   │
│  │  │ • Structured data: serialize to natural language     │  │   │
│  │  │ • Metadata extraction: instrument, strategy, date   │  │   │
│  │  └────────────────────────┬────────────────────────────┘  │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │ Embedding Generation (Ollama)                        │  │   │
│  │  │ Model: nomic-embed-text (1536 dimensions)            │  │   │
│  │  │ Batch size: 64 chunks per batch                      │  │   │
│  │  └────────────────────────┬────────────────────────────┘  │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │  ┌─────────────────────────────────────────────────────┐  │   │
│  │  │ Storage: pgvector (PostgreSQL extension)             │  │   │
│  │  │ Index: HNSW with cosine similarity                   │  │   │
│  │  │ Table: document_embeddings                           │  │   │
│  │  └─────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                FASE 2: RECUPERACIÓN                        │   │
│  │                                                            │   │
│  │  Query: "¿Cuál fue el rendimiento de la estrategia de     │   │
│  │          trend following en EURUSD durante alta volatilidad?" │
│  │                                                            │   │
│  │  1. Embed query → vector (nomic-embed-text)               │   │
│  │  2. HNSW search: top 20 candidates (cosine similarity)    │   │
│  │  3. Metadata filter: instrument=EURUSD, type=strategy      │   │
│  │  4. Re-rank with cross-encoder (ms-marco-MiniLM)          │   │
│  │  5. Return top 5 chunks with scores                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                FASE 3: GENERACIÓN                         │   │
│  │                                                            │   │
│  │  1. Construir prompt con chunks recuperados               │   │
│  │  2. Enviar a Ollama (Llama 3 8B) con contexto            │   │
│  │  3. Generar respuesta con referencias                     │   │
│  │  4. Validar consistencia factual contra chunks            │   │
│  │  5. Formatear respuesta con citations                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 7.2 Schema de la Base de Datos de Vectores

```sql
CREATE TABLE document_embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  document_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536) NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice HNSW para búsqueda similarity
CREATE INDEX idx_embedding_hnsw 
  ON document_embeddings 
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Índices para filtrado por tenant y metadata
CREATE INDEX idx_embedding_tenant ON document_embeddings (tenant_id);
CREATE INDEX idx_embedding_metadata ON document_embeddings USING GIN (metadata);

-- Función de búsqueda
CREATE OR REPLACE FUNCTION search_documents(
  p_tenant_id UUID,
  p_query_embedding vector(1536),
  p_metadata_filter JSONB DEFAULT '{}',
  p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
  id UUID,
  content TEXT,
  metadata JSONB,
  similarity DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    de.id,
    de.content,
    de.metadata,
    1 - (de.embedding <=> p_query_embedding) AS similarity
  FROM document_embeddings de
  WHERE de.tenant_id = p_tenant_id
    AND de.metadata @> p_metadata_filter
  ORDER BY de.embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;
```

### 7.3 Tipos de Consulta Soportados

| Tipo de Consulta | Ejemplo | Fuentes Utilizadas |
|-----------------|---------|-------------------|
| Estrategia | "¿Cómo funciona la estrategia X?" | Documentos de estrategias |
| Backtest | "¿Cuál fue el Sharpe de Y en 2025?" | Resultados de backtesting |
| Mercado | "¿Qué pasó con EURUSD la semana pasada?" | Análisis de mercado |
| Riesgo | "¿Cuál es el drawdown máximo aceptable?" | Políticas de riesgo |
| Configuración | "¿Cómo configuro el trailing stop?" | Documentación técnica |
| Comparativa | "¿Qué estrategia rindió mejor en ranging?" | Backtest + Documentos |

---

## 8. Agente LLM (Ollama)

### 8.1 Modelos Disponibles

| Modelo | Parámetros | RAM Requerida | GPU | Uso Principal |
|--------|-----------|---------------|-----|---------------|
| Llama 3 8B | 8B | 8 GB | 6+ GB VRAM | Análisis general, insights |
| Llama 3 70B | 70B | 40 GB | 24+ GB VRAM | Análisis profundo, reportes |
| Mixtral 8x7B | 46B | 32 GB | 16+ GB VRAM | Razonamiento complejo |
| Phi-3 Mini | 3.8B | 4 GB | 4+ GB VRAM | Sentimiento, clasificación |
| Nomic Embed | 137M | 1 GB | Opcional | Embeddings para RAG |
| Custom Fine-tuned | Variable | Variable | Variable | Señales específicas del tenant |

### 8.2 Arquitectura del Agente

```
┌──────────────────────────────────────────────────────────────────┐
│                  LLM AGENT ARCHITECTURE                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    AGENT CORE                              │   │
│  │                                                            │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │                System Prompt Manager                │   │   │
│  │  │                                                      │   │   │
│  │  │  Role: "Eres un analista financiero experto para    │   │   │
│  │  │  TNSVT. Tienes acceso a datos de mercado en        │   │   │
│  │  │  tiempo real, históricos, y análisis previos.       │   │   │
│  │  │  Tu objetivo es proporcionar insights accionables."  │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  │                                                            │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │                Tool Registry                         │   │   │
│  │  │                                                      │   │   │
│  │  │  • get_market_data(instrument, timeframe, periods)   │   │   │
│  │  │  • get_regime_state(instrument)                      │   │   │
│  │  │  • get_sentiment(instrument)                         │   │   │
│  │  │  • search_knowledge_base(query)                      │   │   │
│  │  │  • get_portfolio_status(tenant_id)                   │   │   │
│  │  │  • get_active_strategies(tenant_id)                  │   │   │
│  │  │  • calculate_indicator(indicator, params)            │   │   │
│  │  │  • get_news_headlines(instrument, limit)             │   │   │
│  │  │  • run_backtest(strategy, params, period)            │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  │                                                            │   │
│  │  ┌────────────────────────────────────────────────────┐   │   │
│  │  │                Agent Loop (ReAct)                    │   │   │
│  │  │                                                      │   │   │
│  │  │  Thought → Action → Observation → Thought → ...      │   │   │
│  │  │                                                      │   │   │
│  │  │  Max iterations: 10                                  │   │   │
│  │  │  Timeout: 30 seconds                                 │   │   │
│  │  │  Temperature: 0.3 (conservative for finance)         │   │   │
│  │  └────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  OLLAMA INFERENCE SERVER                    │   │
│  │                                                            │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │   │
│  │  │ Model       │  │ Model      │  │ Model              │  │   │
│  │  │ Router      │  │ Cache      │  │ Preloader          │  │   │
│  │  │             │  │ (LRU)      │  │                    │  │   │
│  │  │ Selecciona  │  │            │  │ Precarga modelos   │  │   │
│  │  │ modelo      │  │ Evict LRU  │  │ populares en       │  │   │
│  │  │ según tarea │  │ cuando RAM │  │ startup            │  │   │
│  │  └────────────┘  │ llena      │  └────────────────────┘  │   │
│  │                  └────────────┘                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.3 Casos de Uso del Agente

```python
class LLMInsightRequest(BaseModel):
    """Solicitud de análisis al agente LLM."""
    tenant_id: UUID
    instrument: str
    insight_type: Literal[
        "market_summary",      # Resumen del mercado actual
        "strategy_review",     # Revisión de estrategia activa
        "risk_assessment",     # Evaluación de riesgo del portafolio
        "trade_analysis",      # Análisis de un trade específico
        "daily_briefing",      # Briefing diario del mercado
        "anomaly_explanation"  # Explicación de una anomalía detectada
    ]
    context: dict = {}  # Datos adicionales específicos del tipo
    max_tokens: int = 1024
    model_preference: str = "llama3:8b"


class LLMInsightResponse(BaseModel):
    """Respuesta del agente LLM."""
    insight: str                    # Texto del análisis
    model_used: str                 # Modelo que generó la respuesta
    confidence: float               # Confianza del agente
    sources: list[str]              # Fuentes consultadas
    key_points: list[str]           # Puntos clave extraídos
    action_items: list[str]         # Items de acción sugeridos
    risk_flags: list[str]           # Banderas de riesgo identificadas
    tokens_used: int                # Tokens consumidos
    latency_ms: float               # Latencia de inferencia
    cached: bool                    # Si la respuesta vino de cache
```

### 8.4 Prompts Especializados

```python
MARKET_SUMMARY_PROMPT = """
Eres un analista financiero senior de TNSVT. Genera un resumen del mercado
para {instrument} en timeframe {timeframe}.

Datos disponibles:
- Precio actual: {current_price}
- Cambio 24h: {change_24h}%
- Régimen detectado: {regime} (confianza: {regime_confidence})
- Sentimiento: {sentiment} (confianza: {sentiment_confidence})
- Volatilidad ATR: {atr}
- Volumen vs promedio: {volume_ratio}

Historial reciente (últimas 24h):
{recent_history}

Proporciona:
1. Resumen ejecutivo (2-3 oraciones)
2. Factores clave (3-5 bullets)
3. Nivel de riesgo actual
4. Potencial dirección (con nivel de confianza)
5. Riesgos a monitorear

Responde en español, sé conciso y preciso. No des consejos financieros
específicos, solo análisis.
"""
```

---

## 9. Optimizador de Parámetros

### 9.1 Método: Optimización Bayesiana con Walk-Forward

```
┌──────────────────────────────────────────────────────────────────┐
│              PARAMETER OPTIMIZATION PIPELINE                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input:                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Parámetros a optimizar:                                   │   │
│  │ • Lot size: [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]             │   │
│  │ • Stop Loss: [10, 20, 30, 50, 100, 200] pips            │   │
│  │ • Take Profit: [20, 50, 100, 200, 500] pips             │   │
│  │ • Trailing Stop: [10, 20, 30, 50] pips                   │   │
│  │ • Trailing Activation: [10, 20, 50] pips                 │   │
│  │ • Max Open Trades: [1, 2, 3, 5]                          │   │
│  │ • Time Window: [London, NY, Overlap, Asian]               │   │
│  │                                                           │   │
│  │ Espacio de búsqueda: ~46,080 combinaciones                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ FASE 1: Optimización Bayesiana (scikit-optimize)          │   │
│  │                                                            │   │
│  │ • Surrogate: Gaussian Process (GP)                        │   │
│  │ • Acquisition: Expected Improvement (EI)                  │   │
│  │ • Iteraciones: 200 puntos de evaluación                   │   │
│  │ • Objetivo: Maximizar Sharpe Ratio                        │   │
│  │                                                            │   │
│  │ Constraints:                                               │   │
│  │ • Max drawdown ≤ 15%                                       │   │
│  │ • Min win rate ≥ 45%                                       │   │
│  │ • Min trades ≥ 50 en período de prueba                    │   │
│  └───────────────────────────────┬──────────────────────────┘   │
│                                  │                               │
│  ┌───────────────────────────────▼──────────────────────────┐   │
│  │ FASE 2: Walk-Forward Validation                            │   │
│  │                                                            │   │
│  │ Período total: 12 meses de datos históricos               │   │
│  │                                                            │   │
│  │  │ Entrenamiento │ Test │                                  │   │
│  │  │   3 meses    │ 1 mes│ ← Window 1                       │   │
│  │  │        │ Entrenamiento │ Test │                         │   │
│  │  │        │   3 meses    │ 1 mes│ ← Window 2              │   │
│  │  │              │        │     │                           │   │
│  │  │              │  ...hasta cubrir 12 meses...             │   │
│  │  │                                    │ Entrenamiento │    │   │
│  │  │                                    │   3 meses    │Test││   │
│  │  │                                    │              │1mes│←W12│
│  │                                                            │   │
│  │ Cada ventana:                                               │   │
│  │ 1. Optimizar parámetros en período de entrenamiento        │   │
│  │ 2. Validar en período de test (out-of-sample)              │   │
│  │ 3. Registrar métricas de cada ventana                      │   │
│  │                                                            │   │
│  │ Métricas finales: promedio de ventanas de test             │   │
│  └───────────────────────────────┬──────────────────────────┘   │
│                                  │                               │
│  ┌───────────────────────────────▼──────────────────────────┐   │
│  │ FASE 3: Selección y Deploy                                 │   │
│  │                                                            │   │
│  │ • Comparar contra baseline (parámetros actuales)           │   │
│  │ • Si Sharpe mejor ≥ 10% Y max_dd no empeora > 5%         │   │
│  │   → Promover a producción                                  │   │
│  │ • Si no → Mantener parámetros actuales + alerta            │   │
│  │ • Guardar historial de optimizaciones para auditoría       │   │
│  │ • Notificar al tenant con reporte                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 9.2 Métricas de Evaluación

| Métrica | Fórmula | Peso en Objetivo |
|---------|---------|-------------------|
| Sharpe Ratio | (R_p - R_f) / σ_p | 40% |
| Sortino Ratio | (R_p - R_f) / σ_d | 20% |
| Win Rate | trades_ganadores / total_trades | 15% |
| Profit Factor | gross_profit / gross_loss | 15% |
| Max Drawdown | max(peak - trough) / peak | 10% (penalización) |

### 9.3 Ejecución Programada

```json
{
  "parameter_optimizer": {
    "schedule": "0 3 * * 0",  // Domingos a las 03:00 UTC
    "instruments": ["EURUSD", "GBPUSD", "XAUUSD"],
    "strategies": ["trend_following", "mean_reversion", "breakout"],
    "lookback_months": 12,
    "walk_forward_windows": 12,
    "training_window_months": 3,
    "test_window_months": 1,
    "bayesian_iterations": 200,
    "objective": "sharpe_ratio",
    "constraints": {
      "max_drawdown_pct": 15,
      "min_win_rate_pct": 45,
      "min_trades": 50
    },
    "promotion_threshold": {
      "sharpe_improvement_pct": 10,
      "max_drawdown_degradation_pct": 5
    }
  }
}
```

---

## 10. Detector de Anomalías

### 10.1 Tipos de Anomalías Detectadas

| Tipo | Descripción | Método | Umbral |
|------|-------------|--------|--------|
| **Price Spike** | Movimiento de precio inusual | Z-score con ventana rolling | \|z\| > 3.5 |
| **Spread Anomaly** | Spread anormalmente alto | Percentil histórico | > percentil 99 |
| **Volume Spike** | Volumen inusualmente alto/bajo | Media móvil + desviación | > 3σ de la media |
| **Gap Detection** | Gap significativo entre velas | Comparación open vs prev_close | > 2× ATR |
| **Liquidity Drop** | Caída repentina de liquidez | Profundidad del libro | < 30% del promedio |
| **Correlation Break** | Breakdown de correlación histórica | Rolling correlation | Δ > 0.3 en 1 hora |
| **Flash Crash** | Caída/ subida extrema y rápida | Velocidad de movimiento | > 5σ en < 5 minutos |

### 10.2 Algoritmo Z-Score Adaptativo

```python
class AdaptiveAnomalyDetector:
    """
    Detector de anomalías con ventana adaptativa.
    Ajusta la sensibilidad según el régimen de mercado.
    """
    
    def __init__(self):
        self.base_window = 100
        self.base_threshold = 3.5
    
    def detect(self, prices: np.ndarray, regime: str) -> list[Anomaly]:
        # Ajustar ventana según régimen
        window = self._adjust_window(regime)
        threshold = self._adjust_threshold(regime)
        
        # Calcular estadísticas rolling
        rolling_mean = pd.Series(prices).rolling(window).mean()
        rolling_std = pd.Series(prices).rolling(window).std()
        
        # Z-score
        z_scores = (prices - rolling_mean) / rolling_std
        
        # Detectar anomalías
        anomalies = []
        for i, z in enumerate(z_scores):
            if abs(z) > threshold:
                anomalies.append(Anomaly(
                    type=self._classify_anomaly_type(z, prices, i),
                    severity=min(abs(z) / threshold, 5.0),
                    z_score=z,
                    timestamp=i,
                    price=prices[i],
                    context={
                        'regime': regime,
                        'window_used': window,
                        'threshold_used': threshold
                    }
                ))
        
        return anomalies
    
    def _adjust_window(self, regime: str) -> int:
        adjustments = {
            'HIGH_VOLATILITY': int(self.base_window * 0.5),  # Más sensible
            'LOW_VOLATILITY': int(self.base_window * 1.5),   # Menos sensible
            'BREAKOUT': int(self.base_window * 0.7),         # Moderado
            'CRISIS': int(self.base_window * 0.3),           # Muy sensible
        }
        return adjustments.get(regime, self.base_window)
    
    def _adjust_threshold(self, regime: str) -> float:
        adjustments = {
            'HIGH_VOLATILITY': self.base_threshold * 1.2,
            'LOW_VOLATILITY': self.base_threshold * 0.8,
            'BREAKOUT': self.base_threshold * 0.9,
            'CRISIS': self.base_threshold * 0.7,
        }
        return adjustments.get(regime, self.base_threshold)
```

### 10.3 Pipeline de Anomalías en Tiempo Real

```
┌──────────────────────────────────────────────────────────────────┐
│              ANOMALY DETECTION REAL-TIME PIPELINE                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WebSocket Tick Data (1000+ ticks/seg por instrumento)          │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Tick Aggregator (ventanas de 1 segundo)                    │   │
│  │ • OHLCV de 1s                                             │   │
│  │ • Volume-weighted price                                    │   │
│  │ • Bid/Ask spread promedio                                  │   │
│  │ • Tick count                                               │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│  ┌──────────────────────────▼───────────────────────────────┐   │
│  │ Multi-Detector Engine (paralelo en Go)                    │   │
│  │                                                            │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │   │
│  │  │ Price Anomaly │ │ Spread Anom. │ │ Volume Anom. │      │   │
│  │  │ Detector      │ │ Detector     │ │ Detector     │      │   │
│  │  │ Goroutine     │ │ Goroutine    │ │ Goroutine    │      │   │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘      │   │
│  │         │                │                │               │   │
│  │  ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────┐      │   │
│  │  │ Gap Detector │ │ Liquidity    │ │ Correlation  │      │   │
│  │  │ Goroutine    │ │ Detector     │ │ Break Det.   │      │   │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘      │   │
│  │         │                │                │               │   │
│  │         └────────┬───────┴────────┬───────┘               │   │
│  │                  │                │                       │   │
│  └──────────────────┼────────────────┼───────────────────────┘   │
│                     │                │                           │
│                     ▼                ▼                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Anomaly Aggregator                                         │   │
│  │ • Deduplicar anomalías en ventana de 5s                   │   │
│  │ • Calcular severity_score compuesto                       │   │
│  │ • Clasificar: CRITICAL / HIGH / MEDIUM / LOW / INFO       │   │
│  │ • Generar explanation (texto legible)                      │   │
│  └──────────────────────────┬───────────────────────────────┘   │
│                             │                                    │
│              ┌──────────────┼──────────────┐                    │
│              ▼              ▼              ▼                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ NATS:        │  │ TimescaleDB: │  │ Redis:       │          │
│  │ anomaly.     │  │ anomaly_log  │  │ latest_      │          │
│  │ detected.*   │  │ (historial)  │  │ anomaly.*    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  CRITICAL anomalies additionally trigger:                        │
│  • WebSocket push al usuario                                    │
│  • Email / SMS alert                                             │
│  • Overtrading detector review                                   │
│  • LLM Agent explanation request                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 11. Comunicación con Otros Servicios

### 11.1 Diagrama de Comunicación

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    COMUNICACIÓN AI CORE ↔ OTROS SERVICIOS                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          ┌──────────────────┐                               │
│                          │    NATS JETSTREAM │                               │
│                          │    (Event Bus)    │                               │
│                          └────────┬─────────┘                               │
│                                   │                                          │
│         ┌─────────────────────────┼─────────────────────────┐               │
│         │                         │                         │               │
│         ▼                         ▼                         ▼               │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         │
│  │ Trading Core │         │  AI Core     │         │ API Gateway  │         │
│  │ (Go)         │         │  (Python)    │         │ (Next.js)    │         │
│  └──────────────┘         └──────────────┘         └──────────────┘         │
│                                                                              │
│  SUBJECTS (NATS):                                                            │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ INBOUND TO AI CORE:                                                    │ │
│  │                                                                        │ │
│  │ market.tick.{instrument}      ← Trading Core (WebSocket feed)         │ │
│  │ market.ohlcv.{inst}.{tf}     ← Trading Core (velas completadas)       │ │
│  │ trade.executed.{tenant}       ← Trading Core (trade completado)        │ │
│  │ trade.failed.{tenant}         ← Trading Core (trade fallido)           │ │
│  │ strategy.signal.{tenant}      ← Trading Core (señal de estrategia)     │ │
│  │ news.article.{instrument}     ← News Aggregator                        │ │
│  │ sentiment.social.{instrument} ← Social Scraper                        │ │
│  │ portfolio.updated.{tenant}    ← Trading Core (portfolio cambió)        │ │
│  │ risk.alert.{tenant}           ← Trading Core (alerta de riesgo)        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ OUTBOUND FROM AI CORE:                                                 │ │
│  │                                                                        │ │
│  │ signal.score.{tenant}         → Trading Core (score de señal)          │ │
│  │ regime.state.{instrument}     → Trading Core + API Gateway             │ │
│  │ anomaly.detected.{inst}       → Trading Core + API Gateway             │ │
│  │ overtrading.action.{tenant}   → Trading Core (pausar/bloquear)         │ │
│  │ sentiment.update.{inst}       → API Gateway (para UI)                  │ │
│  │ insight.generated.{tenant}    → API Gateway (insights del LLM)         │ │
│  │ param.optimize.{tenant}       → Trading Core (nuevos parámetros)       │ │
│  │ model.retrained.{model_id}    → Internal (notificación de retrain)     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Contratos de Mensajes

```protobuf
// NATS Message Schema: signal.score
message SignalScore {
  string signal_id = 1;
  string tenant_id = 2;
  string instrument = 3;
  string strategy_name = 4;
  int32 score = 5;              // 0-100
  string action = 6;            // EXECUTE, MONITOR, REJECT
  float confidence = 7;
  map<string, float> feature_importance = 8;
  string explanation = 9;
  string model_version = 10;
  int64 timestamp_ms = 11;
}

// NATS Message Schema: regime.state
message RegimeState {
  string instrument = 1;
  string regime = 2;            // TRENDING_UP, TRENDING_DOWN, RANGING, etc.
  float confidence = 3;
  map<string, float> sub_scores = 4;
  int64 valid_until_ms = 5;
  int64 timestamp_ms = 6;
}

// NATS Message Schema: anomaly.detected
message AnomalyDetected {
  string anomaly_id = 1;
  string instrument = 2;
  string anomaly_type = 3;      // PRICE_SPIKE, SPREAD_ANOMALY, etc.
  string severity = 4;          // CRITICAL, HIGH, MEDIUM, LOW, INFO
  float severity_score = 5;
  string description = 6;
  map<string, string> context = 7;
  int64 timestamp_ms = 8;
}
```

### 11.3 Patrón de Comunicación Request-Reply

Para consultas síncronas (ej: scoring de señal en tiempo real), se usa
el patrón request-reply de NATS:

```python
async def request_signal_score(signal: RawSignal, timeout_ms: int = 50) -> SignalScore:
    """
    Envía señal para scoring y espera respuesta.
    Timeout: 50ms. Si no responde, usar score de fallback.
    """
    try:
        response = await nats_client.request(
            subject=f"aicore.score.{signal.tenant_id}",
            payload=signal.serialize(),
            timeout=timeout_ms / 1000
        )
        return SignalScore.deserialize(response.data)
    except NATSTimeoutError:
        # Fallback: score conservador
        return SignalScore(
            score=50,
            action="MONITOR",
            confidence=0.5,
            explanation="AI Core timeout, using conservative fallback"
        )
```

---

## 12. Servicio de Modelos

### 12.1 Infraestructura GPU

| Componente | Especificación | Cantidad | Costo Estimado |
|------------|---------------|----------|----------------|
| GPU Primaria | NVIDIA RTX 4090 (24GB VRAM) | 1-2 | $1,600-3,200 |
| GPU Secundaria | NVIDIA A100 (40GB VRAM) | 0-1 | $10,000-15,000 |
| RAM del servidor | 128 GB DDR5 | 1 | $400-600 |
| Storage | NVMe SSD 2TB | 1 | $200-300 |
| **Total para 100 usuarios** | | | **~$12,200-19,100** |
| **Total para 100K usuarios** | | | **~$50,000-100,000** |

### 12.2 Estrategia de Caché de Modelos

```
┌──────────────────────────────────────────────────────────────┐
│              MODEL CACHING STRATEGY                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Nivel 1: Model Preloading (RAM/VRAM)                       │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Modelos precargados en GPU al iniciar Ollama:          │  │
│  │ • llama3:8b (siempre cargado)                          │  │
│  │ • nomic-embed-text (siempre cargado)                   │  │
│  │ • phi3:mini (cargado si hay suficiente VRAM)            │  │
│  │                                                         │  │
│  │ Carga bajo demanda (evict LRU):                        │  │
│  │ • mixtral:8x7b                                         │  │
│  │ • llama3:70b                                           │  │
│  │ • custom-finetuned                                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Nivel 2: Response Cache (Redis)                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Cache de respuestas frecuentes:                        │  │
│  │ • Market summary: TTL = 5 minutos                      │  │
│  │ • Sentiment analysis: TTL = 2 minutos                  │  │
│  │ • Regime classification: TTL = 1 minuto                │  │
│  │ • RAG query results: TTL = 15 minutos                  │  │
│  │                                                         │  │
│  │ Key format: ai:cache:{type}:{instrument}:{hash(params)}│  │
│  │ Max memory: 2 GB                                       │  │
│  │ Eviction: LRU                                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Nivel 3: Batch Inference                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Para operaciones no urgentes, agruntar inference:      │  │
│  │ • Sentiment batch: cada 30 segundos                    │  │
│  │ • RAG indexing: cuando hay 100+ documentos nuevos      │  │
│  │ • Model retraining: nocturno                           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 12.3 Métricas de Inferencia

```python
class InferenceMetrics:
    """Métricas de rendimiento de inferencia."""
    
    # Latencia
    INFERENCE_LATENCY = Histogram(
        'ollama_inference_latency_seconds',
        'Tiempo de inferencia de Ollama',
        ['model', 'task_type'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
    )
    
    # Throughput
    INFERENCE_REQUESTS = Counter(
        'ollama_inference_requests_total',
        'Total de solicitudes de inferencia',
        ['model', 'task_type', 'status']
    )
    
    # GPU
    GPU_UTILIZATION = Gauge(
        'gpu_utilization_percent',
        'Utilización de GPU',
        ['gpu_id']
    )
    
    GPU_MEMORY = Gauge(
        'gpu_memory_usage_bytes',
        'Uso de memoria GPU',
        ['gpu_id']
    )
    
    # Modelo
    MODEL_LOAD_TIME = Histogram(
        'ollama_model_load_seconds',
        'Tiempo de carga de modelo',
        ['model']
    )
    
    CACHE_HITS = Counter(
        'ai_cache_hits_total',
        'Cache hits por tipo',
        ['cache_type']
    )
    
    CACHE_MISSES = Counter(
        'ai_cache_misses_total',
        'Cache misses por tipo',
        ['cache_type']
    )
```

---

## 13. Pipeline de Entrenamiento

### 13.1 Flujo Completo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE END-TO-END                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FASE 1: RECOLECCIÓN DE DATOS                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │ │
│  │  │ TimescaleDB   │  │ NATS Stream  │  │ External     │                │ │
│  │  │ Historical   │  │ Real-time    │  │ APIs         │                │ │
│  │  │ OHLCV + Vol  │  │ Tick data    │  │ News, etc.   │                │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │ │
│  │         └────────┬────────┴────────┬────────┘                         │ │
│  │                  ▼                 ▼                                   │ │
│  │         ┌────────────────────────────────┐                            │ │
│  │         │ Data Lake (TimescaleDB + S3)   │                            │ │
│  │         │ Raw data retention: 5 años     │                            │ │
│  │         └────────────────────────────────┘                            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FASE 2: FEATURE ENGINEERING                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Feature Groups:                                                       │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐         │ │
│  │  │ Technical  │ │ Sentiment  │ │ Temporal   │ │ Market     │         │ │
│  │  │ Indicators │ │ Features   │ │ Features   │ │ Microstr.  │         │ │
│  │  │            │ │            │ │            │ │            │         │ │
│  │  │ • RSI      │ │ • Score    │ │ • Hour     │ │ • Spread   │         │ │
│  │  │ • MACD     │ │ • Momentum │ │ • Day      │ │ • Depth    │         │ │
│  │  │ • Bollinger│ │ • Trend    │ │ • Month    │ │ • Imbalance│         │ │
│  │  │ • ATR      │ │ • Volume   │ │ • Session  │ │ • Tick     │         │ │
│  │  │ • ADX      │ │ • Social   │ │ • Holiday  │ │ • VWAP     │         │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘         │ │
│  │                                                                        │ │
│  │  Output: Feature Matrix (n_samples × n_features)                      │ │
│  │  Storage: Redis Feature Store + TimescaleDB raw features               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FASE 3: ENTRENAMIENTO                                                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ Model Training Jobs (Kubernetes Jobs / Airflow)                   │ │ │
│  │  │                                                                    │ │ │
│  │  │ Job Types:                                                        │ │ │
│  │  │ • Signal Scorer: XGBoost (daily)                                  │ │ │
│  │  │ • Regime Classifier: Random Forest (weekly)                       │ │ │
│  │  │ • Anomaly Detector: Isolation Forest (weekly)                     │ │ │
│  │  │ • LLM Fine-tuning: LoRA on Phi-3 (monthly)                       │ │ │
│  │  │ • Sentiment Model: Fine-tuned Phi-3 (monthly)                     │ │ │
│  │  │                                                                    │ │ │
│  │  │ Training Resources:                                               │ │ │
│  │  │ • CPU: 8 cores per job                                            │ │ │
│  │  │ • RAM: 32 GB per job                                              │ │ │
│  │  │ • GPU: 1× A100 for LLM fine-tuning                               │ │ │
│  │  │ • Storage: 50 GB per model version                                │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FASE 4: VALIDACIÓN                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  Validation Pipeline:                                                  │ │
│  │  1. Unit tests del modelo (mínimo de samples, feature completeness)    │ │
│  │  2. Backtesting con datos out-of-sample                               │ │
│  │  3. Walk-forward validation                                            │ │
│  │  4. Comparación contra baseline (modelo anterior)                      │ │
│  │  5. Fairness checks (no bias por horario/instrumento)                 │ │
│  │  6. Latency validation (inference time < SLA)                         │ │
│  │                                                                        │ │
│  │  GO/NO-GO Criteria:                                                    │ │
│  │  • AUC > baseline × 1.02                                              │ │
│  │  • Sharpe ratio improvement ≥ 5%                                      │ │
│  │  • Inference latency < 50ms p99                                       │ │
│  │  • No fairness violations                                              │ │
│  │  • Model size < memory budget                                          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FASE 5: DESPLIEGUE                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                                                                        │ │
│  │  1. Push model to Ollama registry (custom model store)                 │ │
│  │  2. Update model metadata in PostgreSQL                                │ │
│  │  3. Canary deployment (10% traffic → 50% → 100%)                      │ │
│  │  4. Monitor inference metrics for 24 hours                             │ │
│  │  5. Auto-rollback if error rate > 1%                                   │ │
│  │  6. Notify tenants of model update                                     │ │
│  │                                                                        │ │
│  │  Model Registry:                                                       │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │ model_registry:                                                   │ │ │
│  │  │   model_id: uuid                                                  │ │ │
│  │  │   name: "signal_scorer_v3"                                       │ │ │
│  │  │   version: "3.2.1"                                               │ │ │
│  │  │   type: "xgboost_classifier"                                     │ │ │
│  │  │   metrics: { auc: 0.847, sharpe_improvement: 0.12 }             │ │ │
│  │  │   status: "production" | "staging" | "archived"                  │ │ │
│  │  │   created_at: timestamp                                           │ │ │
│  │  │   promoted_at: timestamp                                          │ │ │
│  │  │   artifact_path: "s3://models/signal_scorer/v3.2.1/model.onnx"  │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Calendario de Entrenamiento

| Modelo | Frecuencia | Ventana de Datos | Recursos | Tiempo Estimado |
|--------|-----------|------------------|----------|-----------------|
| Signal Scorer (XGBoost) | Diario | 30 días | 4 CPU, 8 GB RAM | ~5 min |
| Regime Classifier | Semanal | 90 días | 4 CPU, 8 GB RAM | ~15 min |
| Anomaly Detector (IF) | Semanal | 60 días | 4 CPU, 8 GB RAM | ~10 min |
| Sentiment Model (Phi-3) | Mensual | 180 días | 8 CPU, 32 GB, 1 GPU | ~4 horas |
| LLM Fine-tuning | Mensual | 365 días | 8 CPU, 64 GB, 1 GPU | ~12 horas |
| Parameter Optimizer | Semanal | 365 días | 4 CPU, 16 GB RAM | ~30 min |

---

## 14. Seguridad y Cumplimiento

### 14.1 Principios de Seguridad

| Principio | Implementación |
|-----------|---------------|
| **Zero Trust** | Cada inferencia validada criptográficamente con Ed25519 |
| **Aislamiento de Tenant** | Modelos y datos segregados por tenant_id |
| **Cifrado en Tránsito** | TLS 1.3 para todas las comunicaciones |
| **Cifrado en Reposo** | AES-256 para datos sensibles en PostgreSQL |
| **Auditoría** | Log inmutable de cada decisión de trading (Event Sourcing) |
| **Rate Limiting** | Límites de inferencia por tenant para prevenir abuso |
| **Model Security** | Modelos firmados, verificación de integridad antes de cargar |

### 14.2 Auditoría de Decisiones IA

```sql
-- Cada decisión del AI Core se registra como evento inmutable
CREATE TABLE ai_decision_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  decision_type TEXT NOT NULL,        -- SIGNAL_SCORE, REGIME, ANOMALY, etc.
  input_hash TEXT NOT NULL,           -- SHA-256 de los datos de entrada
  output_hash TEXT NOT NULL,          -- SHA-256 de la decisión tomada
  model_id UUID NOT NULL,
  model_version TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  execution_time_ms DOUBLE NOT NULL,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  signature TEXT NOT NULL,            -- Ed25519 signature
  metadata JSONB DEFAULT '{}'
);

-- Retención: 7 años (regulación financiera)
SELECT add_retention_policy('ai_decision_audit', INTERVAL '7 years');
```

---

## 15. Métricas y Observabilidad

### 15.1 Dashboard de Métricas AI Core

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        AI CORE DASHBOARD - GRAFANA                            │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │ Requests/sec      │ │ Avg Latency      │ │ Error Rate       │            │
│  │    12,450         │ │    23ms          │ │    0.02%         │            │
│  │  ▲ +15% vs ayer   │ │  ▼ -5% vs ayer   │ │  ▼ -0.01%        │            │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘            │
│                                                                              │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐            │
│  │ GPU Utilization   │ │ Model Cache Hit  │ │ Active Models    │            │
│  │    67%            │ │    94.2%         │ │    4             │            │
│  │  RTX 4090 #1     │ │  Target: > 90%   │ │  of 6 loaded     │            │
│  └──────────────────┘ └──────────────────┘ └──────────────────┘            │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Inference Latency Distribution (última hora)                         │  │
│  │                                                                       │  │
│  │ p50: 15ms  │ p95: 35ms  │ p99: 48ms  │ p999: 95ms                   │  │
│  │                                                                       │  │
│  │ [████████████████████████░░░░░░░░░░░░░░░░░░░░░░░]                     │  │
│  │  0ms        25ms        50ms        75ms       100ms+                │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Model Performance Comparison                                         │  │
│  │                                                                       │  │
│  │ Model          │ Requests │ Avg Lat │ Error │ Cache Hit              │  │
│  │ ─────────────────────────────────────────────────────────            │  │
│  │ llama3:8b      │ 8,234   │ 180ms   │ 0.01% │ 87%                   │  │
│  │ phi3:mini      │ 3,120   │ 45ms    │ 0.00% │ 96%                   │  │
│  │ nomic-embed    │ 12,450  │ 12ms    │ 0.00% │ 99%                   │  │
│  │ signal_scorer  │ 11,890  │ 8ms     │ 0.02% │ N/A (onnx)            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 15.2 Alertas Configuradas

| Alerta | Condición | Severidad | Acción |
|--------|-----------|-----------|--------|
| AI Core Down | Health check falla > 30s | CRITICAL | Page on-call + Trading Core fallback |
| Latencia Alta | p99 > 100ms por 5 min | HIGH | Auto-scale GPU workers |
| GPU Overload | Utilización > 95% por 10 min | HIGH | Evict low-priority models |
| Cache Hit Bajo | Hit rate < 80% por 15 min | MEDIUM | Revisar TTL configuration |
| Model Degraded | AUC cae > 5% vs baseline | HIGH | Revert to previous model |
| Anomaly Flood | > 100 anomalies/min | MEDIUM | Revisar detector thresholds |
| Training Failed | Job falla 3 consecutivas | HIGH | Alert ML engineer |
| OOM GPU | Out of memory error | CRITICAL | Restart Ollama + reduce batch |

---

## Documentos Relacionados

| Documento | Relación |
|-----------|----------|
| [TRADING-CORE.md](./TRADING-CORE.md) | Consumidor principal de señales AI |
| [EVENT-SOURCING.md](./EVENT-SOURCING.md) | Almacén inmutable de decisiones AI |
| [SCALE-100K.md](./SCALE-100K.md) | Estrategia de escalamiento de AI Core |
| [RISKS.md](./RISKS.md) | Riesgos específicos del componente AI |
| [INFRASTRUCTURE.md](./INFRASTRUCTURE.md) | GPU y compute resources |

---

*Documento generado como parte de la arquitectura de TNSVT V2.*  
*Última revisión: 2026-07-14*
