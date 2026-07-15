# TNSVT V2 — Modelo de Datos

**Versión:** 2.0  
**Fecha:** 14 de Julio de 2026  
**Clasificación:** Confidencial — Uso Interno  
**Estado:** Aprobado por Arquitectura  

---

## Índice

1. [Estrategia Multi-Tenant](#1-estrategia-multi-tenant)
2. [Usuarios y Tenants](#2-usuarios-y-tenants)
3. [Trading](#3-trading)
4. [Risk](#4-risk)
5. [Market Data](#5-market-data)
6. [AI/ML](#6-aiml)
7. [Billing](#7-billing)
8. [Audit / Event Sourcing](#8-audit--event-sourcing)
9. [TimescaleDB Hypertables](#9-timescaledb-hypertables)
10. [Índices y Optimización](#10-índices-y-optimización)
11. [Estrategia de Migración](#11-estrategia-de-migración)

---

## 1. Estrategia Multi-Tenant

### 1.1 Schema-per-Tenant

```
+=========================================================================+
|                    ESTRATEGIA MULTI-TENANT                              |
+=========================================================================+
|                                                                          |
|  PostgreSQL Database: tnsvt_main                                         |
|                                                                          |
|  +------------------------------------------------------------------+  |
|  | SCHEMA: public (compartido)                                     |  |
|  |                                                                   |  |
|  |  tenants           — Registro de todos los tenants               |  |
|  |  plans             — Planes de suscripción disponibles          |  |
|  |  global_config     — Configuración global del sistema           |  |
|  |  broker_registry   — Catálogo de brokers disponibles            |  |
|  +------------------------------------------------------------------+  |
|                                                                          |
|  +------------------------------------------------------------------+  |
|  | SCHEMA: tenant_abc (aislado)                                    |  |
|  |                                                                   |  |
|  |  users             — Usuarios del tenant                        |  |
|  |  accounts          — Cuentas de trading                         |  |
|  |  orders            — Órdenes ejecutadas                         |  |
|  |  positions         — Posiciones abiertas                        |  |
|  |  signals           — Señales de trading                         |  |
|  |  copy_configs      — Configuraciones de copy trading           |  |
|  |  risk_config       — Configuración de riesgo                    |  |
|  |  strategies        — Estrategias del tenant                     |  |
|  |  events            — Eventos de audit (Event Sourcing)          |  |
|  |  snapshots         — Snapshots de aggregates                    |  |
|  |  projections       — Read models proyectados                    |  |
|  +------------------------------------------------------------------+  |
|                                                                          |
|  +------------------------------------------------------------------+  |
|  | SCHEMA: tenant_xyz (aislado)                                    |  |
|  |  ... (mismo patrón que tenant_abc)                              |  |
|  +------------------------------------------------------------------+  |
|                                                                          |
|  +------------------------------------------------------------------+  |
|  | SCHEMA: TimescaleDB (global)                                    |  |
|  |                                                                   |  |
|  |  ohlc_global       — Hypertable: OHLC candles (todos tenants)   |  |
|  |  metrics_global    — Hypertable: Métricas de sistema            |  |
|  |  equity_curves     — Hypertable: Equity curves por account      |  |
|  +------------------------------------------------------------------+  |
+=========================================================================+
```

### 1.2 Ventajas del Schema-per-Tenant

| Ventaja                | Descripción                                              |
|------------------------|----------------------------------------------------------|
| Aislamiento completo   | Un tenant no puede ver datos de otro                    |
| Backup por tenant      | pg_dump de un schema individual                          |
| Performance            | Menos locks, mejor cache de índices por tenant          |
| Compliance             | GDPR: deletion de un tenant = DROP SCHEMA               |
| Granularidad           | Permisos a nivel de schema                              |
| Migration control      | Migrar tenant por tenant si es necesario                |

---

## 2. Usuarios y Tenants

### T-01: tenants (Schema: public)

```sql
CREATE TABLE public.tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    slug            VARCHAR(50) NOT NULL UNIQUE,
    schema_name     VARCHAR(63) NOT NULL UNIQUE,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'suspended', 'deactivated', 'pending')),
    plan_id         UUID NOT NULL REFERENCES public.plans(id),
    settings        JSONB NOT NULL DEFAULT '{}',
    max_users       INT NOT NULL DEFAULT 5,
    max_accounts    INT NOT NULL DEFAULT 3,
    max_orders_day  INT NOT NULL DEFAULT 100,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_tenants_slug ON public.tenants(slug);
CREATE INDEX idx_tenants_status ON public.tenants(status);
CREATE INDEX idx_tenants_plan ON public.tenants(plan_id);
```

| Campo            | Tipo         | Descripción                                    |
|------------------|--------------|-------------------------------------------------|
| `id`             | UUID         | Identificador único del tenant                  |
| `name`           | VARCHAR(200)| Nombre comercial del tenant                     |
| `slug`           | VARCHAR(50) | URL-friendly identifier (para subdomain)       |
| `schema_name`    | VARCHAR(63) | Nombre del schema PostgreSQL (tenant_{slug})   |
| `status`         | VARCHAR(20) | Estado actual del tenant                       |
| `plan_id`        | UUID FK      | Referencia al plan activo                      |
| `settings`       | JSONB        | Configuración flexible (brokers habilitados, etc.) |
| `max_users`      | INT          | Límite de usuarios en el tenant                |
| `max_accounts`   | INT          | Límite de cuentas de trading                   |
| `max_orders_day` | INT          | Límite diario de órdenes                       |
| `metadata`       | JSONB        | Datos adicionales (billing cycle, etc.)        |

---

### T-02: plans (Schema: public)

```sql
CREATE TABLE public.plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL UNIQUE,
    slug            VARCHAR(50) NOT NULL UNIQUE,
    price_monthly   DECIMAL(10,2) NOT NULL DEFAULT 0,
    price_yearly    DECIMAL(10,2) NOT NULL DEFAULT 0,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    features        JSONB NOT NULL DEFAULT '{}',
    limits          JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    sort_order      INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- features JSONB example:
-- {
--   "ai_scoring": true,
--   "backtesting": true,
--   "copy_trading": true,
--   "white_label": false,
--   "api_access": true,
--   "priority_support": false
-- }

-- limits JSONB example:
-- {
--   "max_users": 10,
--   "max_accounts": 5,
--   "max_orders_day": 500,
--   "max_signals_day": 1000,
--   "max_api_calls_month": 100000,
--   "max_brokers": 5,
--   "max_backtest_days": 1825,
--   "data_retention_days": 365
-- }
```

---

### T-03: users (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    email           VARCHAR(320) NOT NULL,
    password_hash   VARCHAR(255),
    full_name       VARCHAR(200) NOT NULL,
    avatar_url      VARCHAR(500),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'locked', 'pending')),
    roles           TEXT[] NOT NULL DEFAULT '{viewer}',
    oauth_provider  VARCHAR(50),
    oauth_id        VARCHAR(255),
    mfa_enabled     BOOLEAN NOT NULL DEFAULT false,
    mfa_secret      VARCHAR(100),
    last_login_at   TIMESTAMPTZ,
    login_attempts  INT NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    preferences     JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(tenant_id, email)
);

CREATE INDEX idx_users_email ON {schema}.users(email);
CREATE INDEX idx_users_tenant ON {schema}.users(tenant_id);
CREATE INDEX idx_users_status ON {schema}.users(status);
CREATE INDEX idx_users_oauth ON {schema}.users(oauth_provider, oauth_id)
    WHERE oauth_provider IS NOT NULL;
```

| Campo            | Tipo         | Descripción                                    |
|------------------|--------------|-------------------------------------------------|
| `id`             | UUID         | Identificador único del usuario                |
| `tenant_id`      | UUID FK      | Tenant al que pertenece                        |
| `email`          | VARCHAR(320)| Email único por tenant                         |
| `password_hash`  | VARCHAR(255)| bcrypt hash (nullable para OAuth-only users)   |
| `full_name`      | VARCHAR(200)| Nombre completo                                |
| `roles`          | TEXT[]       | Array de roles: admin, manager, trader, viewer |
| `oauth_provider` | VARCHAR(50) | google, github, discord (nullable)             |
| `mfa_enabled`    | BOOLEAN     | Si tiene MFA activado                          |
| `mfa_secret`     | VARCHAR(100)| TOTP secret (encrypted at rest)                |
| `preferences`    | JSONB        | Tema, idioma, timezone, notificaciones         |

---

### T-04: accounts (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    user_id         UUID NOT NULL REFERENCES {schema}.users(id),
    name            VARCHAR(100) NOT NULL,
    broker          VARCHAR(50) NOT NULL,
    account_number  VARCHAR(100) NOT NULL,
    account_type    VARCHAR(20) NOT NULL DEFAULT 'live'
                    CHECK (account_type IN ('live', 'demo', 'paper')),
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'disconnected', 'suspended')),
    is_master       BOOLEAN NOT NULL DEFAULT false,
    config          JSONB NOT NULL DEFAULT '{}',
    balance         DECIMAL(18,4) NOT NULL DEFAULT 0,
    equity          DECIMAL(18,4) NOT NULL DEFAULT 0,
    margin_used     DECIMAL(18,4) NOT NULL DEFAULT 0,
    free_margin     DECIMAL(18,4) NOT NULL DEFAULT 0,
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(tenant_id, broker, account_number)
);

CREATE INDEX idx_accounts_user ON {schema}.accounts(user_id);
CREATE INDEX idx_accounts_broker ON {schema}.accounts(broker);
CREATE INDEX idx_accounts_master ON {schema}.accounts(is_master) WHERE is_master = true;
```

| Campo            | Tipo         | Descripción                                    |
|------------------|--------------|-------------------------------------------------|
| `broker`         | VARCHAR(50) | mt5, ctrader, binance, bybit, ibkr              |
| `account_number` | VARCHAR(100)| Número de cuenta en el broker                   |
| `is_master`      | BOOLEAN     | Si es cuenta master para copy trading            |
| `config`         | JSONB        | Config broker-specific (login, server, etc.)    |
| `balance`        | DECIMAL(18,4)| Balance actual (sincronizado)                   |
| `equity`         | DECIMAL(18,4)| Equity actual (balance + P&L unrealized)        |

---

## 3. Trading

### T-05: orders (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    account_id      UUID NOT NULL REFERENCES {schema}.accounts(id),
    signal_id       UUID REFERENCES {schema}.signals(id),
    broker_order_id VARCHAR(100),
    symbol          VARCHAR(20) NOT NULL,
    direction       VARCHAR(4) NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    order_type      VARCHAR(20) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT')),
    quantity         DECIMAL(18,8) NOT NULL,
    price           DECIMAL(18,8),
    stop_loss       DECIMAL(18,8),
    take_profit     DECIMAL(18,8),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'submitted', 'accepted', 'partial_fill',
                                      'filled', 'cancelled', 'rejected', 'expired')),
    filled_quantity DECIMAL(18,8) NOT NULL DEFAULT 0,
    filled_price    DECIMAL(18,8),
    commission      DECIMAL(18,4) NOT NULL DEFAULT 0,
    slippage        DECIMAL(18,8) NOT NULL DEFAULT 0,
    source          VARCHAR(50) NOT NULL DEFAULT 'manual'
                    CHECK (source IN ('manual', 'signal', 'copy', 'strategy', 'backtest')),
    copy_parent_id  UUID REFERENCES {schema}.orders(id),
    strategy_version VARCHAR(50),
    meta            JSONB NOT NULL DEFAULT '{}',
    submitted_at    TIMESTAMPTZ,
    filled_at       TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_orders_account ON {schema}.orders(account_id);
CREATE INDEX idx_orders_status ON {schema}.orders(status);
CREATE INDEX idx_orders_symbol ON {schema}.orders(symbol);
CREATE INDEX idx_orders_signal ON {schema}.orders(signal_id) WHERE signal_id IS NOT NULL;
CREATE INDEX idx_orders_broker_id ON {schema}.orders(broker_order_id);
CREATE INDEX idx_orders_created ON {schema}.orders(created_at DESC);
CREATE INDEX idx_orders_copy_parent ON {schema}.orders(copy_parent_id) WHERE copy_parent_id IS NOT NULL;
```

| Campo             | Tipo          | Descripción                                    |
|-------------------|---------------|-------------------------------------------------|
| `broker_order_id` | VARCHAR(100) | ID de la orden en el broker                     |
| `signal_id`       | UUID FK       | Señal que originó esta orden (nullable)         |
| `source`          | VARCHAR(50)   | manual (usuario), signal (AI), copy (follower), strategy (automático) |
| `copy_parent_id`  | UUID FK       | Si es copia, referencia a la orden del master   |
| `slippage`        | DECIMAL(18,8) | Diferencia entre precio esperado y ejecutado    |

---

### T-06: positions (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    account_id      UUID NOT NULL REFERENCES {schema}.accounts(id),
    broker_position_id VARCHAR(100),
    symbol          VARCHAR(20) NOT NULL,
    direction       VARCHAR(4) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    quantity         DECIMAL(18,8) NOT NULL,
    entry_price     DECIMAL(18,8) NOT NULL,
    current_price   DECIMAL(18,8) NOT NULL,
    stop_loss       DECIMAL(18,8),
    take_profit     DECIMAL(18,8),
    unrealized_pnl  DECIMAL(18,4) NOT NULL DEFAULT 0,
    realized_pnl    DECIMAL(18,4) NOT NULL DEFAULT 0,
    commission      DECIMAL(18,4) NOT NULL DEFAULT 0,
    swap            DECIMAL(18,4) NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'closing', 'closed')),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_positions_account ON {schema}.positions(account_id);
CREATE INDEX idx_positions_status ON {schema}.positions(status);
CREATE INDEX idx_positions_symbol ON {schema}.positions(symbol);
CREATE INDEX idx_positions_open ON {schema}.positions(status) WHERE status = 'open';
```

---

### T-07: signals (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    source          VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    direction       VARCHAR(4) NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    order_type      VARCHAR(20) NOT NULL DEFAULT 'MARKET',
    price_target    DECIMAL(18,8),
    stop_loss       DECIMAL(18,8),
    take_profit     DECIMAL(18,8),
    timeframe       VARCHAR(10),
    strategy        VARCHAR(100),
    confidence      DECIMAL(5,2),
    risk_reward     DECIMAL(5,2),
    score_quant     DECIMAL(5,2),
    score_llm       DECIMAL(5,2),
    score_combined  DECIMAL(5,2),
    explanation     TEXT,
    features        JSONB NOT NULL DEFAULT '{}',
    regime          VARCHAR(20),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'executed', 'expired', 'cancelled', 'rejected')),
    expires_at      TIMESTAMPTZ,
    executed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_signals_status ON {schema}.signals(status);
CREATE INDEX idx_signals_symbol ON {schema}.signals(symbol);
CREATE INDEX idx_signals_source ON {schema}.signals(source);
CREATE INDEX idx_signals_created ON {schema}.signals(created_at DESC);
CREATE INDEX idx_signals_confidence ON {schema}.signals(confidence DESC)
    WHERE status = 'active';
```

---

### T-08: copy_configs (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.copy_configs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES public.tenants(id),
    master_account_id   UUID NOT NULL REFERENCES {schema}.accounts(id),
    follower_account_id UUID NOT NULL REFERENCES {schema}.accounts(id),
    active              BOOLEAN NOT NULL DEFAULT true,
    lot_scaling         DECIMAL(10,4) NOT NULL DEFAULT 1.0,
    fixed_lot           DECIMAL(18,8),
    sl_pips             INT,
    tp_pips             INT,
    sl_multiplier       DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    tp_multiplier       DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    max_position_size   DECIMAL(18,8),
    filter_symbols      TEXT[] DEFAULT '{ALL}',
    filter_direction    VARCHAR(10) DEFAULT 'BOTH'
                        CHECK (filter_direction IN ('BOTH', 'BUY_ONLY', 'SELL_ONLY')),
    filter_max_risk     DECIMAL(5,2) DEFAULT 100,
    filter_min_confidence DECIMAL(5,2) DEFAULT 0,
    filter_order_types  TEXT[] DEFAULT '{MARKET,LIMIT,STOP}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(master_account_id, follower_account_id)
);

CREATE INDEX idx_copy_master ON {schema}.copy_configs(master_account_id);
CREATE INDEX idx_copy_follower ON {schema}.copy_configs(follower_account_id);
CREATE INDEX idx_copy_active ON {schema}.copy_configs(active) WHERE active = true;
```

---

### T-09: strategies (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.strategies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    type            VARCHAR(50) NOT NULL DEFAULT 'manual'
                    CHECK (type IN ('manual', 'technical', 'ai_assisted', 'fully_ai')),
    config          JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'inactive'
                    CHECK (status IN ('active', 'inactive', 'testing', 'archived')),
    backtest_sharpe DECIMAL(5,2),
    backtest_dd     DECIMAL(5,2),
    backtest_trades INT,
    version         VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 4. Risk

### T-10: risk_config (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.risk_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES public.tenants(id),
    account_id              UUID REFERENCES {schema}.accounts(id),
    max_exposure_symbol     DECIMAL(18,4) NOT NULL DEFAULT 50000,
    max_exposure_total      DECIMAL(18,4) NOT NULL DEFAULT 200000,
    max_daily_drawdown_pct  DECIMAL(5,2) NOT NULL DEFAULT 5.0,
    max_weekly_drawdown_pct DECIMAL(5,2) NOT NULL DEFAULT 10.0,
    max_monthly_drawdown_pct DECIMAL(5,2) NOT NULL DEFAULT 15.0,
    max_position_pct        DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    max_orders_hour         INT NOT NULL DEFAULT 20,
    max_orders_day          INT NOT NULL DEFAULT 100,
    min_risk_reward         DECIMAL(5,2) NOT NULL DEFAULT 1.5,
    max_correlated_pairs    INT NOT NULL DEFAULT 3,
    circuit_breaker_enabled BOOLEAN NOT NULL DEFAULT true,
    circuit_breaker_cooldown_min INT NOT NULL DEFAULT 5,
    circuit_breaker_force_close BOOLEAN NOT NULL DEFAULT false,
    blacklisted_symbols     TEXT[] DEFAULT '{}',
    trading_hours_start     TIME DEFAULT '00:00',
    trading_hours_end       TIME DEFAULT '23:59',
    trading_days            INT[] DEFAULT '{1,2,3,4,5}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_risk_config_account ON {schema}.risk_config(account_id)
    WHERE account_id IS NOT NULL;
CREATE INDEX idx_risk_config_tenant ON {schema}.risk_config(tenant_id);
```

---

## 5. Market Data

### T-11: symbols (Schema: public)

```sql
CREATE TABLE public.symbols (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    asset_class     VARCHAR(50) NOT NULL
                    CHECK (asset_class IN ('forex', 'crypto', 'stock', 'commodity',
                                           'index', 'etf', 'futures')),
    base_currency   VARCHAR(10),
    quote_currency  VARCHAR(10),
    exchange        VARCHAR(50),
    tick_size       DECIMAL(18,12) NOT NULL,
    lot_size        DECIMAL(18,8) NOT NULL,
    min_lot         DECIMAL(18,8) NOT NULL,
    max_lot         DECIMAL(18,8) NOT NULL,
    spread_typical  DECIMAL(18,8),
    commission      DECIMAL(18,4),
    swap_long       DECIMAL(18,8),
    swap_short      DECIMAL(18,8),
    trading_hours   JSONB,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_symbols_class ON public.symbols(asset_class);
CREATE INDEX idx_symbols_active ON public.symbols(is_active) WHERE is_active = true;
```

### T-12: broker_symbols (Schema: public)

```sql
CREATE TABLE public.broker_symbols (
    id              SERIAL PRIMARY KEY,
    broker          VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL REFERENCES public.symbols(symbol),
    broker_symbol   VARCHAR(50) NOT NULL,
    broker_config   JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(broker, symbol)
);
```

---

## 6. AI/ML

### T-13: ai_models (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.ai_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    name            VARCHAR(200) NOT NULL,
    type            VARCHAR(50) NOT NULL
                    CHECK (type IN ('scoring', 'regime', 'anomaly', 'rag', 'custom')),
    algorithm       VARCHAR(100) NOT NULL,
    version         VARCHAR(50) NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}',
    metrics         JSONB NOT NULL DEFAULT '{}',
    artifact_path   VARCHAR(500),
    status          VARCHAR(20) NOT NULL DEFAULT 'trained'
                    CHECK (status IN ('training', 'trained', 'active', 'archived', 'failed')),
    trained_at      TIMESTAMPTZ,
    deployed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, name, version)
);

-- metrics JSONB example:
-- {
--   "accuracy": 0.72,
--   "precision": 0.68,
--   "recall": 0.75,
--   "f1": 0.71,
--   "sharpe": 1.55,
--   "max_drawdown": -12.3,
--   "win_rate": 0.58,
--   "total_trades": 847,
--   "train_samples": 50000,
--   "test_samples": 12000
-- }
```

### T-14: ai_predictions (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.ai_predictions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    model_id        UUID NOT NULL REFERENCES {schema}.ai_models(id),
    symbol          VARCHAR(20) NOT NULL,
    prediction_type VARCHAR(50) NOT NULL,
    prediction      JSONB NOT NULL,
    confidence      DECIMAL(5,2) NOT NULL,
    features_used   JSONB NOT NULL DEFAULT '{}',
    actual_outcome  JSONB,
    correctness     DECIMAL(5,2),
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    evaluated_at    TIMESTAMPTZ
);

CREATE INDEX idx_predictions_model ON {schema}.ai_predictions(model_id);
CREATE INDEX idx_predictions_symbol ON {schema}.ai_predictions(symbol);
CREATE INDEX idx_predictions_confidence ON {schema}.ai_predictions(confidence DESC);
CREATE INDEX idx_predictions_time ON {schema}.ai_predictions(predicted_at DESC);
```

### T-15: ai_feature_store (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.ai_feature_store (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    symbol          VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    features        JSONB NOT NULL,
    calculated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_features_symbol_tf ON {schema}.ai_feature_store(symbol, timeframe, calculated_at DESC);
```

---

## 7. Billing

### T-16: subscriptions (Schema: public)

```sql
CREATE TABLE public.subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    plan_id         UUID NOT NULL REFERENCES public.plans(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'past_due', 'cancelled', 'paused', 'trialing')),
    billing_cycle   VARCHAR(20) NOT NULL DEFAULT 'monthly'
                    CHECK (billing_cycle IN ('monthly', 'yearly')),
    stripe_subscription_id VARCHAR(100),
    stripe_customer_id     VARCHAR(100),
    current_period_start   TIMESTAMPTZ NOT NULL,
    current_period_end     TIMESTAMPTZ NOT NULL,
    trial_start     TIMESTAMPTZ,
    trial_end       TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_subscriptions_tenant ON public.subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_status ON public.subscriptions(status);
CREATE INDEX idx_subscriptions_stripe ON public.subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
```

### T-17: invoices (Schema: public)

```sql
CREATE TABLE public.invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    subscription_id UUID NOT NULL REFERENCES public.subscriptions(id),
    invoice_number  VARCHAR(50) NOT NULL UNIQUE,
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'open', 'paid', 'void', 'uncollectible')),
    amount_subtotal DECIMAL(10,2) NOT NULL,
    amount_tax      DECIMAL(10,2) NOT NULL DEFAULT 0,
    amount_total    DECIMAL(10,2) NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
    line_items      JSONB NOT NULL DEFAULT '[]',
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    paid_at         TIMESTAMPTZ,
    stripe_invoice_id VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_invoices_tenant ON public.invoices(tenant_id);
CREATE INDEX idx_invoices_status ON public.invoices(status);
```

### T-18: usage_metering (Schema: public)

```sql
CREATE TABLE public.usage_metering (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id),
    metric_type     VARCHAR(50) NOT NULL,
    quantity        BIGINT NOT NULL DEFAULT 1,
    period_date     DATE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_usage_tenant_date ON public.usage_metering(tenant_id, period_date);
CREATE INDEX idx_usage_metric ON public.usage_metering(metric_type, period_date);
```

---

## 8. Audit / Event Sourcing

### T-19: events (Event Store — Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.events (
    id              BIGSERIAL PRIMARY KEY,
    event_id        UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    aggregate_type  VARCHAR(100) NOT NULL,
    aggregate_id    UUID NOT NULL,
    event_type      VARCHAR(200) NOT NULL,
    event_version   INT NOT NULL DEFAULT 1,
    event_data      JSONB NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    caused_by       VARCHAR(200),
    caused_by_user  UUID,
    correlation_id  UUID,
    causation_id    UUID,
    sequence_number BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_events_aggregate_seq
    ON {schema}.events(aggregate_type, aggregate_id, sequence_number);

CREATE INDEX idx_events_aggregate ON {schema}.events(aggregate_type, aggregate_id);
CREATE INDEX idx_events_type ON {schema}.events(event_type);
CREATE INDEX idx_events_time ON {schema}.events(created_at DESC);
CREATE INDEX idx_events_correlation ON {schema}.events(correlation_id)
    WHERE correlation_id IS NOT NULL;
```

| Campo            | Tipo          | Descripción                                    |
|------------------|---------------|-------------------------------------------------|
| `event_id`       | UUID          | ID único del evento (para exactly-once)        |
| `aggregate_type` | VARCHAR(100) | OrderAggregate, AccountAggregate, etc.         |
| `aggregate_id`   | UUID          | ID del aggregate al que pertenece              |
| `event_type`     | VARCHAR(200) | OrderPlaced, OrderFilled, RiskBreached, etc.   |
| `sequence_number`| BIGINT        | Secuencial por aggregate (para optimistic concurrency) |
| `correlation_id` | UUID          | Agrupa eventos relacionados (un request → múltiples eventos) |
| `causation_id`   | UUID          | Evento que causó este evento (chain)           |

---

### T-20: snapshots (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.snapshots (
    id              BIGSERIAL PRIMARY KEY,
    aggregate_type  VARCHAR(100) NOT NULL,
    aggregate_id    UUID NOT NULL,
    version         BIGINT NOT NULL,
    state           JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_snapshots_aggregate
    ON {schema}.snapshots(aggregate_type, aggregate_id, version);

CREATE INDEX idx_snapshots_aggregate_latest
    ON {schema}.snapshots(aggregate_type, aggregate_id, version DESC);
```

**Política de Snapshots:** Cada 100 eventos por aggregate, se crea un snapshot.
Al reconstruir el estado, se carga el snapshot más reciente y se replayan
los eventos posteriores.

---

### T-21: projections (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.projections (
    id              BIGSERIAL PRIMARY KEY,
    projection_name VARCHAR(200) NOT NULL,
    last_event_id   BIGINT NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'building', 'error')),
    error_message   TEXT,
    last_built_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_projections_name ON {schema}.projections(projection_name);
```

---

### T-22: read_models — daily_pnl (Schema: tenant_{slug})

```sql
CREATE TABLE {schema}.daily_pnl (
    id              BIGSERIAL PRIMARY KEY,
    account_id      UUID NOT NULL REFERENCES {schema}.accounts(id),
    date            DATE NOT NULL,
    realized_pnl    DECIMAL(18,4) NOT NULL DEFAULT 0,
    unrealized_pnl  DECIMAL(18,4) NOT NULL DEFAULT 0,
    total_pnl       DECIMAL(18,4) NOT NULL DEFAULT 0,
    trades_count    INT NOT NULL DEFAULT 0,
    winning_trades  INT NOT NULL DEFAULT 0,
    losing_trades   INT NOT NULL DEFAULT 0,
    commission      DECIMAL(18,4) NOT NULL DEFAULT 0,
    balance_eod     DECIMAL(18,4) NOT NULL,
    equity_eod      DECIMAL(18,4) NOT NULL,
    max_drawdown    DECIMAL(18,4) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(account_id, date)
);

CREATE INDEX idx_daily_pnl_account_date ON {schema}.daily_pnl(account_id, date DESC);
```

---

## 9. TimescaleDB Hypertables

### T-23: ohlc_data (TimescaleDB Hypertable)

```sql
CREATE TABLE market_data.ohlc_data (
    time            TIMESTAMPTZ NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    timeframe       VARCHAR(10) NOT NULL,
    open            DECIMAL(18,8) NOT NULL,
    high            DECIMAL(18,8) NOT NULL,
    low             DECIMAL(18,8) NOT NULL,
    close           DECIMAL(18,8) NOT NULL,
    volume          DECIMAL(18,4) NOT NULL DEFAULT 0,
    tick_count      INT NOT NULL DEFAULT 0,
    vwap            DECIMAL(18,8)
);

SELECT create_hypertable('market_data.ohlc_data', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Compression policy (after 7 days)
ALTER TABLE market_data.ohlc_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('market_data.ohlc_data', INTERVAL '7 days');

CREATE UNIQUE INDEX idx_ohlc_unique
    ON market_data.ohlc_data(symbol, timeframe, time DESC);

CREATE INDEX idx_ohlc_symbol_tf_time
    ON market_data.ohlc_data(symbol, timeframe, time DESC);
```

| Campo        | Tipo          | Descripción                                    |
|--------------|---------------|-------------------------------------------------|
| `time`       | TIMESTAMPTZ   | Timestamp de la candle                          |
| `symbol`     | VARCHAR(20)   | Par de divisas / activo                         |
| `timeframe`  | VARCHAR(10)   | M1, M5, M15, M30, H1, H4, D1, W1, MN          |
| `volume`     | DECIMAL(18,4) | Volumen negociado en la candle                  |
| `vwap`       | DECIMAL(18,8) | Volume Weighted Average Price                   |

---

### T-24: tick_data (TimescaleDB Hypertable)

```sql
CREATE TABLE market_data.tick_data (
    time            TIMESTAMPTZ NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    bid             DECIMAL(18,8) NOT NULL,
    ask             DECIMAL(18,8) NOT NULL,
    spread          DECIMAL(18,8) NOT NULL,
    last            DECIMAL(18,8),
    volume          DECIMAL(18,4) DEFAULT 0
);

SELECT create_hypertable('market_data.tick_data', 'time',
    chunk_time_interval => INTERVAL '1 hour');

-- Drop old ticks (retain 24 hours for real-time, aggregate to OHLC)
SELECT add_retention_policy('market_data.tick_data', INTERVAL '24 hours');

CREATE INDEX idx_ticks_symbol_time
    ON market_data.tick_data(symbol, time DESC);
```

---

### T-25: system_metrics (TimescaleDB Hypertable)

```sql
CREATE TABLE monitoring.system_metrics (
    time            TIMESTAMPTZ NOT NULL,
    service         VARCHAR(100) NOT NULL,
    metric_name     VARCHAR(200) NOT NULL,
    metric_value    DOUBLE PRECISION NOT NULL,
    labels          JSONB NOT NULL DEFAULT '{}'
);

SELECT create_hypertable('monitoring.system_metrics', 'time',
    chunk_time_interval => INTERVAL '1 hour');

-- Retain 90 days
SELECT add_retention_policy('monitoring.system_metrics', INTERVAL '90 days');

CREATE INDEX idx_metrics_service_name
    ON monitoring.system_metrics(service, metric_name, time DESC);
```

---

### T-26: equity_curves (TimescaleDB Hypertable)

```sql
CREATE TABLE market_data.equity_curves (
    time            TIMESTAMPTZ NOT NULL,
    account_id      UUID NOT NULL,
    tenant_id       UUID NOT NULL,
    equity          DECIMAL(18,4) NOT NULL,
    balance         DECIMAL(18,4) NOT NULL,
    margin_used     DECIMAL(18,4) NOT NULL DEFAULT 0,
    unrealized_pnl  DECIMAL(18,4) NOT NULL DEFAULT 0
);

SELECT create_hypertable('market_data.equity_curves', 'time',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_equity_account_time
    ON market_data.equity_curves(account_id, time DESC);

CREATE INDEX idx_equity_tenant_time
    ON market_data.equity_curves(tenant_id, time DESC);
```

---

## 10. Índices y Optimización

### 10.1 Estrategia de Índices

```
+=========================================================================+
|                    ESTRATEGIA DE ÍNDICES                                |
+=========================================================================+
|                                                                          |
|  1. B-Tree indexes (default):                                           |
|     - Primary keys (automático)                                         |
|     - Foreign keys                                                      |
|     - Columnas en WHERE frecuentes                                      |
|     - Columnas en ORDER BY                                              |
|                                                                          |
|  2. Partial indexes (para status filtrados):                            |
|     - WHERE status = 'active' (solo registros activos)                 |
|     - WHERE is_master = true (solo accounts master)                    |
|     - Reducen tamaño del índice 60-80%                                  |
|                                                                          |
|  3. Composite indexes (para queries multi-columna):                     |
|     - (account_id, symbol, status) para posiciones abiertas            |
|     - (tenant_id, period_date) para metering                           |
|     - (aggregate_type, aggregate_id, sequence_number) para events      |
|                                                                          |
|  4. Covering indexes (para queries frecuentes):                         |
|     - INCLUDE para evitar heap lookups                                  |
|     - Solo en queries de alto volumen                                   |
|                                                                          |
|  5. GIN indexes (para JSONB y arrays):                                  |
|     - features, metadata, config columns                               |
|     - Solo cuando se buscan keys específicas                           |
+=========================================================================+
```

### 10.2 Tabla de Índices Críticos

| Tabla              | Índice                                | Tipo     | Justificación                          |
|--------------------|---------------------------------------|----------|----------------------------------------|
| orders             | (account_id, created_at DESC)         | B-Tree   | Query: "últimas órdenes por cuenta"    |
| orders             | (status, created_at DESC)             | B-Tree   | Query: "órdenes pendientes"            |
| positions          | (account_id, symbol) WHERE open       | Partial  | Query: "posiciones abiertas por symbol"|
| events             | (aggregate_type, aggregate_id, seq)   | Unique   | Event Sourcing + optimistic concurrency|
| signals            | (confidence DESC) WHERE active        | Partial  | Query: "mejores señales activas"       |
| daily_pnl          | (account_id, date DESC)               | B-Tree   | Query: "P&L histórico por cuenta"      |
| ohlc_data          | (symbol, timeframe, time DESC)        | B-Tree   | Query: "candles para backtest"         |
| equity_curves      | (account_id, time DESC)               | B-Tree   | Query: "equity curve por cuenta"       |
| usage_metering     | (tenant_id, metric_type, period_date) | B-Tree   | Query: "usage por tenant/mes"          |
| ai_predictions     | (model_id, symbol, predicted_at DESC) | B-Tree   | Query: "predicciones recientes"        |

---

## 11. Estrategia de Migración

### 11.1 Herramientas

| Herramienta          | Uso                                           |
|----------------------|-----------------------------------------------|
| golang-migrate       | Migraciones SQL para Go services              |
| Alembic              | Migraciones Python (AI/ML schemas)            |
| Flyway               | Migraciones de emergency / hotfix             |
| pg_dump/pg_restore   | Backup y restore por schema                   |

### 11.2 Convención de Migraciones

```
migrations/
├── 000001_create_tenants.up.sql
├── 000001_create_tenants.down.sql
├── 000002_create_plans.up.sql
├── 000002_create_plans.down.sql
├── 000003_create_users.up.sql
├── 000003_create_users.down.sql
├── ...
├── 000020_create_events.up.sql
├── 000020_create_events.down.sql
└── 000021_add_indexes.up.sql
```

### 11.3 Reglas de Migración

| Regla                          | Descripción                                              |
|--------------------------------|----------------------------------------------------------|
| Nunca DROP column en producción| Usar soft delete o new column + backfill                 |
| Siempre incluir DOWN           | Cada migración debe ser reversible                      |
| Testing antes de apply         | Ejecutar en staging con datos de producción anonymizados|
| Zero-downtime migrations       | Usar ADD COLUMN DEFAULT, CREATE INDEX CONCURRENTLY      |
| Version lock                   | Cada migración tiene versión semántica                   |
| Schema-per-tenant migrations   | Ejecutar en todos los schemas de tenant activos         |

### 11.4 Flujo de Migración

```
+=========================================================================+
|                    FLUJO DE MIGRACIÓN                                   |
+=========================================================================+
|                                                                          |
|  [Developer]                                                             |
|       |                                                                  |
|       v                                                                  |
|  [Write migration SQL]                                                  |
|       |                                                                  |
|       v                                                                  |
|  [Git commit to /migrations]                                            |
|       |                                                                  |
|       v                                                                  |
|  [CI Pipeline]                                                          |
|       |                                                                  |
|       ├── migrate-dry-run (test DB)                                     |
|       ├── validate-down-migration                                       |
|       └── test-rollback                                                 |
|       |                                                                  |
|       v                                                                  |
|  [PR Review + Approval]                                                 |
|       |                                                                  |
|       v                                                                  |
|  [Staging: apply migration]                                             |
|       |                                                                  |
|       v                                                                  |
|  [Smoke tests pass]                                                     |
|       |                                                                  |
|       v                                                                  |
|  [Production: apply migration]                                          |
|       |                                                                  |
|       ├── For each tenant schema:                                       |
|       |   ├── SET search_path TO tenant_{slug};                         |
|       |   └── \i migration.sql                                          |
|       |                                                                  |
|       v                                                                  |
|  [Verify + Monitor]                                                     |
|       |                                                                  |
|       v                                                                  |
|  [Done]                                                                 |
+=========================================================================+
```

### 11.5 Diagrama Entity-Relationship (Simplificado)

```
+=========================================================================+
|                    ENTITY RELATIONSHIP DIAGRAM                          |
+=========================================================================+
|                                                                          |
|  public.tenants ─────┬──── public.plans                                  |
|       |              |                                                   |
|       |              └──── public.subscriptions ─── public.invoices      |
|       |                                                                  |
|       ├──── public.usage_metering                                        |
|       |                                                                  |
|  {schema}.users ───────────── {schema}.accounts                         |
|       |                            |                                     |
|       │                            ├──── {schema}.orders ──── signals   |
|       │                            │         |                          |
|       │                            │         └─── copy_configs          |
|       │                            │                                    |
|       │                            ├──── {schema}.positions             |
|       │                            │                                    |
|       │                            └──── {schema}.risk_config           |
|       │                                                                 |
|       └──── {schema}.strategies                                         |
|                                                                          |
|  {schema}.events ──── {schema}.snapshots                                |
|       |                                                                 |
|       └──── {schema}.projections                                         |
|                                                                          |
|  {schema}.ai_models ──── {schema}.ai_predictions                        |
|  {schema}.ai_feature_store                                               |
|  {schema}.daily_pnl                                                      |
|                                                                          |
|  market_data.ohlc_data (hypertable)                                     |
|  market_data.tick_data (hypertable)                                     |
|  market_data.equity_curves (hypertable)                                 |
|  monitoring.system_metrics (hypertable)                                 |
|                                                                          |
|  public.symbols ──── public.broker_symbols                              |
+=========================================================================+
```

---

## Resumen de Tablas por Dominio

| Dominio        | Tablas                                  | Total |
|----------------|-----------------------------------------|-------|
| Public/Shared  | tenants, plans, symbols, broker_symbols, subscriptions, invoices, usage_metering | 7     |
| Users/Platform | users, accounts                         | 2     |
| Trading        | orders, positions, signals, copy_configs, strategies | 5     |
| Risk           | risk_config                             | 1     |
| AI/ML          | ai_models, ai_predictions, ai_feature_store | 3     |
| Audit/ES       | events, snapshots, projections, daily_pnl | 4     |
| TimescaleDB    | ohlc_data, tick_data, system_metrics, equity_curves | 4     |
| **TOTAL**      |                                         | **26**|

> **Nota:** Cada tabla con prefijo `{schema}.` se replica por cada tenant,
> resultando en ~26 × N_tenant tablas activas en la base de datos.

---

## Aprobaciones

| Rol                  | Nombre           | Fecha       | Estado    |
|----------------------|------------------|-------------|-----------|
| CTO                  | ________________ | ____/__/__ | Pendiente |
| Lead Architect       | ________________ | ____/__/__ | Pendiente |
| DBA Lead             | ________________ | ____/__/__ | Pendiente |

---

*Documento generado como parte del proceso de arquitectura de TNSVT V2.*
*Documento anterior: [03-DATA-FLOWS.md](03-DATA-FLOWS.md)*
