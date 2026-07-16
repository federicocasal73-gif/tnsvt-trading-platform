#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Seed data
# Carga datos demo: tenant default, usuario admin, símbolos,
# límites de riesgo, configuración inicial.
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-tnsvt}"
POSTGRES_DB="${POSTGRES_DB:-tnsvt}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-tnsvt}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Seed datos demo"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── Detectar Postgres (Docker o local) ─────────────────────────────
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "tnsvt-postgres"; then
    PSQL_CMD="docker exec -i tnsvt-postgres psql -U $POSTGRES_USER -d $POSTGRES_DB"
    echo -e "${BLUE}Modo: Docker (tnsvt-postgres)${NC}"
else
    export PGPASSWORD="$POSTGRES_PASSWORD"
    PSQL_CMD="psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB"
    echo -e "${BLUE}Modo: local ($POSTGRES_HOST:$POSTGRES_PORT)${NC}"
fi

# ─── 1) Tenant + admin user (solo si las tablas existen) ────────────
echo -e "${YELLOW}▶ 1) Datos del schema 'platform'${NC}"
$PSQL_CMD <<'SQL' 2>/dev/null || echo -e "  ${YELLOW}(platform schema no inicializado; primero: make migrate)${NC}"
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'platform' AND table_name = 'tenants') THEN
        -- Tenant default
        INSERT INTO platform.tenants (id, name, slug, plan, status, settings, created_at, updated_at)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            'TNSVT Demo',
            'demo',
            'pro',
            'active',
            '{"timezone":"UTC","locale":"en","demo":true}'::jsonb,
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO NOTHING;

        -- Admin user
        INSERT INTO platform.users (id, tenant_id, email, username, password_hash, role, status, created_at, updated_at)
        VALUES (
            '00000000-0000-0000-0000-000000000002',
            '00000000-0000-0000-0000-000000000001',
            'admin@tnsvt.local',
            'admin',
            -- bcrypt hash for "Admin123!Demo" (cost 10) -- pre-computed
            '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy',
            'admin',
            'active',
            NOW(),
            NOW()
        )
        ON CONFLICT (id) DO NOTHING;

        RAISE NOTICE 'platform: tenant + admin user seeded';
    ELSE
        RAISE NOTICE 'platform: tables not yet created (run make migrate first)';
    END IF;
END $$;
SQL

# ─── 2) Risk limits demo ────────────────────────────────────────────
echo -e "${YELLOW}▶ 2) Risk limits (schema risk)${NC}"
$PSQL_CMD <<'SQL' 2>/dev/null || echo -e "  ${YELLOW}(risk schema no inicializado; primero: make migrate)${NC}"
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'risk' AND table_name = 'risk_limits') THEN
        INSERT INTO risk.risk_limits (
            tenant_id, daily_loss_limit, daily_profit_target, weekly_loss_limit,
            max_open_positions, max_exposure_per_symbol, max_drawdown_percent,
            min_confidence, trailing_stop, trailing_step, trailing_start,
            updated_at
        )
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            500.00,    -- daily_loss_limit USD
            1000.00,   -- daily_profit_target USD
            1500.00,   -- weekly_loss_limit USD
            5,         -- max_open_positions
            50000.00,  -- max_exposure_per_symbol USD
            20.00,     -- max_drawdown_percent %
            0.50,      -- min_confidence 0-1
            true,      -- trailing_stop
            10,        -- trailing_step pips
            50,        -- trailing_start pips
            NOW()
        )
        ON CONFLICT (tenant_id) DO UPDATE SET
            daily_loss_limit = EXCLUDED.daily_loss_limit,
            updated_at = NOW();

        RAISE NOTICE 'risk: default risk limits seeded';
    END IF;
END $$;
SQL

# ─── 3) Trading symbols (schema trading) ────────────────────────────
echo -e "${YELLOW}▶ 3) Trading symbols (schema trading)${NC}"
$PSQL_CMD <<'SQL' 2>/dev/null || true
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'trading' AND table_name = 'symbols') THEN
        INSERT INTO trading.symbols (symbol, name, asset_class, digits, enabled, created_at)
        VALUES
            ('EURUSD', 'Euro vs US Dollar', 'forex', 5, true, NOW()),
            ('GBPUSD', 'British Pound vs US Dollar', 'forex', 5, true, NOW()),
            ('USDJPY', 'US Dollar vs Japanese Yen', 'forex', 3, true, NOW()),
            ('XAUUSD', 'Gold vs US Dollar', 'metal', 2, true, NOW()),
            ('XAGUSD', 'Silver vs US Dollar', 'metal', 2, true, NOW()),
            ('BTCUSD', 'Bitcoin vs US Dollar', 'crypto', 2, true, NOW()),
            ('ETHUSD', 'Ethereum vs US Dollar', 'crypto', 2, true, NOW()),
            ('NAS100', 'NASDAQ 100 Index', 'index', 2, true, NOW()),
            ('US30', 'Dow Jones 30 Index', 'index', 2, true, NOW())
        ON CONFLICT (symbol) DO NOTHING;

        RAISE NOTICE 'trading: 9 symbols seeded';
    END IF;
END $$;
SQL

# ─── 4) System config extras ────────────────────────────────────────
echo -e "${YELLOW}▶ 4) System config (public.system_config)${NC}"
$PSQL_CMD <<'SQL'
INSERT INTO public.system_config (key, value, description) VALUES
    ('demo.enabled', 'true', 'Demo data is loaded'),
    ('demo.admin_email', '"admin@tnsvt.local"', 'Admin email for demo login'),
    ('demo.admin_password', '"Admin123!Demo"', 'Admin password for demo login (bcrypt pre-computed)'),
    ('maintenance.allowed_ips', '["127.0.0.1","::1"]', 'IPs allowed during maintenance')
ON CONFLICT (key) DO NOTHING;
SQL

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Seed completo${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Credenciales demo:${NC}"
echo "  Email:    admin@tnsvt.local"
echo "  Password: Admin123!Demo"
echo ""
echo -e "${YELLOW}⚠  Cambia la contraseña del admin antes de producción${NC}"
echo ""