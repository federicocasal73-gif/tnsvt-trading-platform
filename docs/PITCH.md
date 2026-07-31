# TNSVT V2 — Executive Summary

**Plataforma SaaS de Trading Algorítmico Multi-Broker**

> Versión 2.0 · Julio 2026 · Confidencial

---

## The Problem

Trading algorítmico empresarial actual enfrenta tres barreras críticas:

- **Fragilidad**: Stack monolítico (PHP Symfony), sin mensajería confiable, sin tolerancia a fallos granular
- **Escala limitada**: ~50 usuarios concurrentes, SQLite, copy trading rígido 1:1 sin configuración por cuenta
- **Sin inteligencia**: Decisiones basadas únicamente en reglas fijas, sin AI/ML, sin análisis de sentimiento

## The Solution

TNSVT V2 es una plataforma SaaS de trading algorítmico **event-driven**, **multi-broker**, con **AI autoalojada y copy trading 1:N configurable por cuenta**.

| Dimensión | Antes (V1) | Ahora (V2) |
|-----------|-----------|------------|
| Stack | PHP monolítico + FastAPI aislado | Go microservicios + Python AI/ML |
| Mensajería | Sin bus | NATS JetStream (event sourcing) |
| Base de datos | SQLite | PostgreSQL + TimescaleDB |
| Escala | ~50 usuarios | 100,000+ (por diseño) |
| Brokers | 1 (MT5) | 5+ (MT5, cTrader, Binance, Bybit, IBKR) |
| Latencia | 2-5s | < 100ms p99 |
| Copy trading | Rígido 1:1 | 1:N configurable por cuenta |
| AI | Sin AI | Ollama self-hosted + RAG + scoring |
| Frontend | Streamlit | React + Vite + WebSocket |
| Autoalojado | No | Sí (Docker Compose, sin dependencias externas) |

## Architecture

![Arquitectura general](diagrams/architecture.png)

### Core Components

**13 microservicios** en producción, desplegables con `docker-compose up`:

| Capa | Servicios | Tecnología |
|------|-----------|-----------|
| 🚪 Gateway | `api-gateway` | Go + JWT + rate limit |
| 🏗️ Platform | `auth-service`, `account-manager` | Go + PostgreSQL |
| 📊 Trading | `signal-engine`, `execution-engine`, `copy-trading`, `risk-engine` | Go + NATS |
| 🧠 AI/ML | `signal-generator`, `orchestrator`, `news-analyzer` | Python + Ollama |
| 📈 Market | `price-feed` | Go + WebSocket |
| 🔔 Notification | `telegram-bot-service` | Go + Telegram API |
| 🔗 Bridge | `bridge-api` (MT5↔TNSVT) | Python |
| 🏦 Broker | `mt5-connector` | Go |

### Signal Pipeline (E2E)

![Pipeline de señales](diagrams/pipeline.png)

```
Signal Source → NATS → signal-engine → NATS → copy-trading → risk-engine → execution-engine → mt5-connector → Broker
```

## Key Differentiators

### 1. Copy Trading Inteligente 1:N

Un solo signal → N cuentas destino, cada una con su propia configuración (lote, ratio, riesgo máximo, símbolos permitidos). No es mirror trading rígido.

### 2. AI Autoalojado (Privacidad Total)

Ollama self-hosted para scoring de señales y análisis de sentimiento NLP. Sin dependencia de APIs externas. Sin fuga de datos de trading.

### 3. Autoalojable + SaaS

La misma imagen Docker funciona en:
- `docker-compose up` (single server)
- Docker Swarm / Kubernetes (HA)
- Instancia cloud gestionada (próximamente)

### 4. Risk Framework en Tiempo Real

Cada orden pasa por 3 gates de riesgo antes de ejecutarse:
- Drawdown máximo (< 15%)
- Posiciones abiertas máximas (< 3)
- Exposición por símbolo

### 5. Multi-Broker por Diseño

API de broker abstracta (`mt5-connector` como referencia). Agregar un broker nuevo es implementar 3 métodos: `Connect`, `SendOrder`, `GetPositions`.

## Current State

- ✅ **13/15 servicios** operativos (13 running, 2 planeados para Fase 2)
- ✅ **Pipeline E2E verificado**: signal → NATS → copy → execution → broker
- ✅ **Dashboard funcional**: Login, positions, signals, history, settings
- ✅ **Bridge MT5** activo: telegram signals → bridge-api → copy-trading
- ✅ **AI integrado**: news-analyzer con Ollama + orchestrator multi-symbol
- ✅ **Telegram Bot** con proxy-aware paths

## Roadmap

| Fase | Timeline | Features |
|------|----------|----------|
| **1 (Actual)** | Jul 2026 | Core trading + copy + risk + bridge MT5 |
| **2** | Q3 2026 | Multi-broker (cTrader), WebSocket streaming, Grafana dashboards |
| **3** | Q4 2026 | Frontend React completo, Tauri desktop app, multi-tenancy |
| **4** | Q1 2027 | Scale to 100k users, Kubernetes HA, white-label |

## Demo

- **URL**: `http://localhost:8000`
- **Login**: `admin@tnsvt.local` / `Admin123!Demo`
- **Stack**: `docker-compose up` (13 servicios)

---

*TNSVT V2 — Trading Network Signals & Vault Technology*
