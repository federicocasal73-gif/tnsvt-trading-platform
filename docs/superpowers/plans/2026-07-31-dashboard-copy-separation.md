# Separación Dashboard vs Copy Trading — plan ejecutado

Fecha: 2026-07-31
Estado: **Implementado y validado end-to-end (smoke test pasó)**.

## Resultado

El error **"upstream error. ¿Está corriendo el servicio copy-trading en :8005?"** está eliminado (Fase 1).

El sistema distingue:
- **Dashboard general** (`/api/v1/accounts` + `/bridge/mt5/accounts`): muestra TODAS las cuentas registradas con balance/equity/P&L.
- **Copy Trading** (`/api/v1/accounts/replicators` + `/bridge/replicators`): muestra solo las cuentas con `copy_enabled=true`.

Toggle desde `AccountsPage` (frontend) hace PATCH y refresca en tiempo real.

## Cambios ejecutados

### Fase 1 — Quick fix (el error upstream)
- `scripts/start-native.ps1` y `scripts/stop-native.ps1`: agregado `copy-trading` (Go, puerto 8005).
- `scripts/restart-copy-trading.ps1` (nuevo) — helper.
- `bin/copy-trading.exe` ya estaba compilado (24MB), solo faltaba arrancarlo.
- **Resultado**: `GET /api/v1/copy/groups` via gateway → 200 OK.

### Fase 0 — Backup de la DB
- `pg_dump -U tnsvt -h localhost tnsvt > backups/backup_pre_copy_20260731_133456.sql` (230KB, 2106 líneas).

### Fase 2 — Migración `copy_enabled` en account-manager
Archivos:
- `apps/platform/account-manager/internal/repository/repository.go`:
  - DDL: `ALTER TABLE accounts ADD COLUMN IF NOT EXISTS copy_enabled BOOLEAN NOT NULL DEFAULT false;`
  - DDL: `CREATE INDEX IF NOT EXISTS idx_accounts_replicators ON accounts(tenant_id, copy_enabled) WHERE copy_enabled = true;`
  - SELECT/INSERT/UPDATE: agregado `copy_enabled` en todas las queries.
  - Nuevo método: `ListReplicatorsByTenant(ctx, tenantID)`.
- `apps/platform/account-manager/internal/models/models.go`:
  - `Account.CopyEnabled bool`
  - `UpdateAccountRequest.CopyEnabled *bool`
- `apps/platform/account-manager/internal/handlers/handlers.go`:
  - `GET /api/v1/accounts/replicators` — nuevo endpoint.
  - `PUT /api/v1/accounts/:id` — acepta `copy_enabled` en el body.
- `apps/platform/account-manager/internal/service/service.go`:
  - `ListReplicators(ctx, tenantID) *AccountListResponse` — nuevo método.
  - **`UpdateAccount` FIX**: aplicado `req.CopyEnabled` al modelo antes de persistir (bug encontrado durante el smoke test).

### Fase 3 — bridge-api expone `copy_enabled` y `/bridge/replicators`
- `apps/bridge/bridge-api/main.py`:
  - `/api/v1/bridge/mt5/accounts`: el response incluye `copy_enabled` (vía account-manager).
  - Nuevo: `GET /api/v1/bridge/replicators` — filtra `copy_enabled=true` con datos live.

### Fase 4 — Frontend: separación menú + páginas
Archivos:
- `apps/frontend/src/router.tsx`: cada route tiene `scope: "monitor" | "operate" | "admin"`. `mt5-settings` marcada `deprecated: true` (redirect a `/copy-trading?tab=settings`).
- `apps/frontend/src/components/Shell.tsx`: agrupa navItems en secciones `Monitor` / `Operación` / `Admin`.
- `apps/frontend/src/components/Sidebar.tsx`: nueva prop `sections: SidebarSection[]` con headers por sección. Acepta `SidebarSection` como tipo exportado.
- `apps/frontend/src/lib/api.ts`:
  - `api.accounts.list()` ahora incluye `copy_enabled` en cada account.
  - `api.accounts.listReplicators()` nuevo.
  - `api.accounts.setCopyEnabled(id, enabled)` nuevo.
  - `api.bridgeReplicators.list(tenantId?)` nuevo.
  - `AccountManagerAccount` interface con `copy_enabled: boolean`.
- `apps/frontend/src/pages/AccountsPage.tsx`:
  - Nueva columna **"Copy"** con toggle ON/OFF.
  - `handleToggleCopy(a)` llama `api.accounts.setCopyEnabled(a.id, !a.copy_enabled)`.
  - `AccountRow` incluye `copy_enabled: boolean`.
- `apps/frontend/src/pages/CopyTradingPage.tsx`:
  - Tab default ahora es **"Replicators"** (antes: "groups").
  - Nuevo `ReplicatorsTab`: tabla de cuentas con `copy_enabled=true`, datos live de `bridgeReplicators.list()`.
  - Mensaje de error genérico (sin "upstream error" técnico que ya no aplica).
- `apps/frontend/src/pages/Mt5SettingsPage.tsx`: redirect a `/copy-trading?tab=settings` (legacy, deprecated).

### Fase 5 — Smoke test E2E
Script: `scripts/smoke-copy-separation.py`.

```
[1] GET /api/v1/accounts        → 3 cuentas (todas con copy_enabled=False)
[2] GET /bridge/mt5/accounts    → 3 cuentas, copy_enabled: [False, False, False]
[3] GET /accounts/replicators  → 0 cuentas
[4] PATCH copy_enabled=true    → 200 OK
[5] GET /accounts/replicators  → 1 cuenta (LST-Trading copy_enabled=True)  ← FUNCIONA
[6] GET /bridge/replicators     → 1 cuenta (live data)  ← FUNCIONA
[7] PATCH copy_enabled=false   → 200 OK (rollback)
[8] GET /accounts/replicators  → 0 cuentas  ← ROLLBACK OK
```

## Bug encontrado y corregido

Durante el smoke test, descubrí que `Service.UpdateAccount` no propagaba `req.CopyEnabled` al modelo antes del `repo.Update`. Sin este fix, el PATCH respondía 200 OK pero la columna no se persistía. Corregido en `apps/platform/account-manager/internal/service/service.go:194-196`.

## Frontend build
- `npx tsc --noEmit` → 0 errores
- `npx vite build` → ✓ built in 14.38s (648KB)
- TypeScript types sincronizados con la API

## Limitación encontrada (fuera de scope)
El gateway filtra por JWT tenant en `/api/v1/accounts`. Si el JWT pertenece a un tenant sin cuentas, devuelve 0. Esto afecta al Dashboard pero NO al refactor de copy-separation. Solución futura: el Dashboard debería mostrar todas las cuentas del usuario (cross-tenant) o el gateway debería soportar un header `X-User-Id` para admins que vean todo.

## Archivos modificados (resumen)
| Archivo | Cambio |
|---|---|
| `scripts/start-native.ps1` | +copy-trading |
| `scripts/stop-native.ps1` | +copy-trading |
| `scripts/restart-copy-trading.ps1` | nuevo |
| `scripts/restart-account-manager.ps1` | nuevo |
| `scripts/restart-bridge-api.ps1` | nuevo |
| `scripts/smoke-copy-separation.py` | nuevo |
| `scripts/integration-check.py` | (existente, sigue pasando) |
| `apps/platform/account-manager/internal/repository/repository.go` | DDL + columnas + ListReplicatorsByTenant |
| `apps/platform/account-manager/internal/models/models.go` | CopyEnabled field |
| `apps/platform/account-manager/internal/handlers/handlers.go` | GET replicators + PUT copy_enabled |
| `apps/platform/account-manager/internal/service/service.go` | ListReplicators + fix UpdateAccount |
| `apps/bridge/bridge-api/main.py` | copy_enabled en response + /bridge/replicators |
| `apps/frontend/src/router.tsx` | scope field por route |
| `apps/frontend/src/components/Shell.tsx` | sections (Monitor/Operación/Admin) |
| `apps/frontend/src/components/Sidebar.tsx` | SidebarSection[] prop |
| `apps/frontend/src/lib/api.ts` | accounts.listReplicators, setCopyEnabled, bridgeReplicators |
| `apps/frontend/src/pages/AccountsPage.tsx` | columna Copy + toggle |
| `apps/frontend/src/pages/CopyTradingPage.tsx` | tab Replicators + componente nuevo |
| `apps/frontend/src/pages/Mt5SettingsPage.tsx` | redirect legacy |

## Rollback

Si algo falla:
1. `psql -U tnsvt -h localhost -c "ALTER TABLE accounts DROP COLUMN copy_enabled; DROP INDEX idx_accounts_replicators;"`
2. `git checkout` los archivos modificados
3. Reiniciar servicios

## Próximos pasos (recomendado, fuera de scope)
- Dashboard: el gateway debería permitir que admins vean todas las cuentas (no solo las de su tenant). Actualmente filtra por JWT tenant.
- Copy Trading: integrar las settings de operativa/riesgo (BE, Correlation Guard, time exit) como tab "Settings" en `CopyTradingPage` con query param `?tab=settings`. Por ahora `/mt5-settings` redirige pero el tab aún no está implementado en CopyTradingPage.
- Persistir el `tenant_id` en la sesión del usuario para que el Dashboard multi-tenant funcione sin cambiar JWT.
