# TNSVT V2 - Copy Trading Engine

Replica señales validadas a múltiples cuentas MT5 con configuración independiente por cuenta (lot, SL/TP, suffix, invert side, etc).

## 🎯 Responsabilidad

- **Fan-out**: 1 señal validada → N grupos → N cuentas por grupo
- **Config por cuenta**: lot_mode (fixed/proportional/risk_based), override SL/TP en pips, invert side, symbol suffix, lot multiplier
- **AppliedConfig**: cálculo de lot_size final, SL/TP convertido a precio, side invertido, suffix aplicado
- **Ejecución**: HTTP POST al execution-engine por cada cuenta destino
- **Tracking**: cada réplica queda registrada como CopyJob con status individual

## 📡 NATS Subscriptions

```
trading.signal.validated   → fan-out a todos los grupos habilitados del tenant
```

## 📡 NATS Publishing

```
trading.copy.completed   → todas las cuentas del grupo ejecutaron OK
trading.copy.partial     → algunas cuentas fallaron, otras OK
trading.copy.failed      → todas las cuentas fallaron
```

## 🔄 Flujo de Replicación

```
1. NATS: trading.signal.validated (signal_id, symbol, action, lot, entry, SL, TP, ...)
     ↓
2. Lookup: CopyGroups del tenant con enabled=true
     ↓
3. Por cada grupo:
   ├── ¿symbol coincide? (si group.symbols no está vacío)
   ├── ¿action coincide? (si group.actions no está vacío)
   ├── ¿confidence >= min_confidence?
     ↓
   4. Por cada cuenta habilitada en el grupo:
      ├── Aplicar config → AppliedConfig (lot, SL/TP, side, symbol)
      ├── Crear CopyJob (status=pending)
      ├── HTTP POST /api/v1/execution-engine/execute
      ├── ✅ 2xx → status=completed, guardar execution_id
      └── ❌ error → status=failed, guardar error_message
     ↓
5. Publicar NATS: trading.copy.completed / .partial / .failed
```

## ⚙️ Configuración por Cuenta

| Campo | Valores | Descripción |
|-------|---------|-------------|
| `lot_mode` | `fixed`, `proportional`, `risk_based` | Cómo se calcula el lote |
| `lot_size` | número | Lote fijo (fixed) |
| `lot_multiplier` | 0.1 - 10 | Escalar el lote de la señal (proportional) |
| `risk_percent` | 0.1 - 5.0 | % del balance a arriesgar (risk_based) |
| `override_sl` | bool | Si true, usa `sl_pips` en vez del SL de la señal |
| `override_tp` | bool | Si true, usa `tp_pips` en vez del TP de la señal |
| `invert_side` | bool | Invierte BUY ↔ SELL |
| `symbol_suffix` | string | Sufijo del símbolo (ej: ".m" para FTMO) |

## 🗄️ Schema PostgreSQL

3 tablas en el schema `trading`:
- **`trading.copy_groups`** — grupos de cuentas (tenant, nombre, enabled, filtros symbols/actions, min_confidence)
- **`trading.copy_accounts`** — cuentas destino (group, broker, account_id, lot config, SL/TP override, invert, suffix)
- **`trading.copy_jobs`** — historial de réplicas (signal, account, status, applied config, execution_id, error)

## ⚙️ Configuración

| Variable | Descripción | Default |
|----------|-------------|---------|
| `COPY_TRADING_PORT` | Puerto del servicio | `8005` |
| `COPY_TRADING_MAX_ACCOUNTS` | Máximo cuentas por grupo | `20` |
| `COPY_TRADING_TIMEOUT_SECONDS` | Timeout por ejecución | `60` |
| `EXECUTION_ENGINE_URL` | URL del execution-engine | `http://execution-engine:8004` |

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/v1/copy/groups` | Listar grupos |
| POST | `/api/v1/copy/groups` | Crear grupo |
| GET | `/api/v1/copy/groups/:id` | Get grupo |
| PUT | `/api/v1/copy/groups/:id` | Actualizar grupo |
| DELETE | `/api/v1/copy/groups/:id` | Eliminar grupo |
| GET | `/api/v1/copy/groups/:id/accounts` | Listar cuentas de un grupo |
| POST | `/api/v1/copy/groups/:id/accounts` | Agregar cuenta |
| GET | `/api/v1/copy/accounts/:id` | Get cuenta |
| PUT | `/api/v1/copy/accounts/:id` | Actualizar cuenta |
| DELETE | `/api/v1/copy/accounts/:id` | Eliminar cuenta |
| GET | `/api/v1/copy/jobs` | Listar jobs (filtro: group_id, account_id, status) |
| GET | `/api/v1/copy/jobs/:id` | Get job |
| GET | `/api/v1/copy/stats` | Estadísticas |
| POST | `/api/v1/copy/replicate/:signal_id` | Trigger manual de replicación |
| GET | `/health`, `/health/live`, `/health/ready`, `/metrics` | Health |

## 🚀 Desarrollo

```bash
cd apps/trading/copy-trading
go mod tidy
go run .
```

## 📋 Ver También

- [`docs/02-SERVICES-CATALOG.md`](../../../docs/02-SERVICES-CATALOG.md)
- [`docs/03-DATA-FLOWS.md`](../../../docs/03-DATA-FLOWS.md)
