#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Stop stack (alias amigable para make down)
# Detiene docker compose y opcionalmente elimina volúmenes
# ═══════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

VOLUMES=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --volumes|-v)  VOLUMES=true; shift ;;
        *) echo "Uso: $0 [--volumes]"; exit 1 ;;
    esac
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Stopping stack"
echo "═══════════════════════════════════════════════════════════════"

if [ "$VOLUMES" = true ]; then
    echo "▶ Deteniendo + eliminando VOLÚMENES (datos de Postgres/Redis/Ollama)... ⚠"
    docker compose -f docker-compose.dev.yml down -v
    echo "✓ Stack detenido + volúmenes eliminados"
else
    echo "▶ Deteniendo contenedores (volúmenes intactos)..."
    docker compose -f docker-compose.dev.yml down
    echo "✓ Stack detenido. Datos preservados."
    echo "  Para eliminar también los volúmenes: $0 --volumes"
fi
echo ""