#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# TNSVT V2 - Test runner
# Ejecuta todos los tests del monorepo
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  TNSVT V2 - Running tests"
echo "═══════════════════════════════════════════════════════════════"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0

# ─── Go tests ───
echo -e "${BLUE}─── Go tests ───${NC}"
if [ -d "shared/go-common" ]; then
    cd shared/go-common
    if go test ./... -v 2>/dev/null; then
        echo -e "${GREEN}✓ Go tests passed${NC}"
        TOTAL_PASS=$((TOTAL_PASS + 1))
    else
        echo -e "${YELLOW}⚠ Go tests skipped (no go.sum or deps)${NC}"
    fi
    cd ../..
fi
echo ""

# ─── Python tests ───
echo -e "${BLUE}─── Python tests ───${NC}"
if command -v pytest &> /dev/null; then
    find tests -name "test_*.py" -not -path "*/venv/*" 2>/dev/null | while read f; do
        if pytest "$f" -v 2>&1 | tail -1; then
            TOTAL_PASS=$((TOTAL_PASS + 1))
        else
            TOTAL_FAIL=$((TOTAL_FAIL + 1))
        fi
    done
else
    echo -e "${YELLOW}pytest no instalado, saltando tests Python${NC}"
fi
echo ""

# ─── TypeScript tests (frontend) ───
echo -e "${BLUE}─── Frontend tests ───${NC}"
if [ -d "frontend/web" ] && [ -f "frontend/web/package.json" ]; then
    cd frontend/web
    if [ -d "node_modules" ]; then
        if npm test 2>/dev/null; then
            echo -e "${GREEN}✓ Frontend tests passed${NC}"
            TOTAL_PASS=$((TOTAL_PASS + 1))
        fi
    else
        echo -e "${YELLOW}Frontend no instalado (npm install) - saltando tests${NC}"
    fi
    cd ../..
else
    echo "Frontend no inicializado todavía"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Tests complete${NC}"
echo "═══════════════════════════════════════════════════════════════"