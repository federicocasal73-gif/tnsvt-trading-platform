#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Start stack (alias amigable para make up)
# Levanta docker compose + corre migraciones + seed opcional
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

# Parse flags
SEED=false
DETACHED=true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --seed)     SEED=true; shift ;;
        --attach)   DETACHED=false; shift ;;
        *) echo "Uso: $0 [--seed] [--attach]"; exit 1 ;;
    esac
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Starting stack"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ─── .env check ────────────────────────────────────────────────────
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "⚠  .env no encontrado. Copiando de .env.example..."
        cp .env.example .env
        echo "✓ .env creado. Edítalo con tus secretos antes de producción."
    else
        echo "✗  No existe .env.example"
        exit 1
    fi
fi

# ─── docker compose up ─────────────────────────────────────────────
COMPOSE_FILE="docker-compose.dev.yml"
if [ "$DETACHED" = true ]; then
    echo "▶ Levantando contenedores en background..."
    docker compose -f "$COMPOSE_FILE" up -d
else
    echo "▶ Levantando contenedores en foreground (Ctrl+C para detener)..."
    docker compose -f "$COMPOSE_FILE" up
    exit 0
fi

# ─── Esperar healthchecks básicos ──────────────────────────────────
echo ""
echo "▶ Esperando healthchecks (10s)..."
sleep 10

# ─── Migraciones ────────────────────────────────────────────────────
echo ""
echo "▶ Corriendo migraciones..."
bash scripts/migrate.sh

# ─── Seed opcional ─────────────────────────────────────────────────
if [ "$SEED" = true ]; then
    echo ""
    echo "▶ Cargando datos demo..."
    bash scripts/seed.sh
fi

# ─── Estado final ──────────────────────────────────────────────────
echo ""
bash scripts/status.sh