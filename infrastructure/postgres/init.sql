-- ═══════════════════════════════════════════════════════════════
-- TNSVT V2 - PostgreSQL + TimescaleDB initialization
-- ═══════════════════════════════════════════════════════════════

-- Habilitar TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ───────────────────────────────────────────────────────────────
-- ESQUEMAS POR DOMINIO (DDD Bounded Contexts)
-- ───────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS trading;
COMMENT ON SCHEMA trading IS 'Trading domain: signals, orders, trades, positions';

CREATE SCHEMA IF NOT EXISTS risk;
COMMENT ON SCHEMA risk IS 'Risk domain: limits, exposure, drawdown';

CREATE SCHEMA IF NOT EXISTS broker;
COMMENT ON SCHEMA broker IS 'Broker domain: connectors, accounts, executions';

CREATE SCHEMA IF NOT EXISTS ai;
COMMENT ON SCHEMA ai IS 'AI domain: models, predictions, scoring';

CREATE SCHEMA IF NOT EXISTS market_data;
COMMENT ON SCHEMA market_data IS 'Market data: prices, news, economic calendar';

CREATE SCHEMA IF NOT EXISTS platform;
COMMENT ON SCHEMA platform IS 'Platform: tenants, users, billing, licenses';

CREATE SCHEMA IF NOT EXISTS notification;
COMMENT ON SCHEMA notification IS 'Notification: messages, channels, preferences';

CREATE SCHEMA IF NOT EXISTS audit;
COMMENT ON SCHEMA audit IS 'Audit: event sourcing, immutable logs';

CREATE SCHEMA IF NOT EXISTS events;
COMMENT ON SCHEMA events IS 'Event store for event sourcing';

-- ───────────────────────────────────────────────────────────────
-- ESQUEMA PÚBLICO - Configuración global
-- ───────────────────────────────────────────────────────────────

-- Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS public.system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Sembrar configuración inicial
INSERT INTO public.system_config (key, value, description) VALUES
    ('system.version', '"0.1.0"', 'TNSVT V2 version'),
    ('system.phase', '"1-mvp"', 'Current development phase'),
    ('system.maintenance_mode', 'false', 'If true, system is in maintenance')
ON CONFLICT (key) DO NOTHING;

-- Mensaje de bienvenida
DO $$
BEGIN
    RAISE NOTICE '═══════════════════════════════════════════════════════════';
    RAISE NOTICE 'TNSVT V2 - PostgreSQL + TimescaleDB initialized';
    RAISE NOTICE 'Schemas created: trading, risk, broker, ai, market_data,';
    RAISE NOTICE '                 platform, notification, audit, events';
    RAISE NOTICE '═══════════════════════════════════════════════════════════';
END $$;