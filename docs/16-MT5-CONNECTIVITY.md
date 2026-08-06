# TNSVT V2 — MT5 Connectivity & Multi-Broker Architecture

> Estado real verificado en vivo (2026-08-03). Documenta cómo la plataforma
> se conecta a MetaTrader 5, cómo se asocian las cuentas a sus terminales y
> la estrategia multi-broker ("una terminal por broker, cuentas por login").

---

## 1. Resumen ejecutivo

TNSVT tiene **dos componentes que tocan MT5**, con filosofías distintas:

| Componente | Stack | Rol | Multi-cuenta | Usa credenciales |
|------------|-------|-----|--------------|------------------|
| **signal_copier** | Python (`MetaTrader5`) | Copia señales de Telegram y ejecuta trades | NO (1 sola sesión) | NO — usa la terminal ya abierta |
| **mt5-connector** | Go + Python bridge | Broker service, ejecución multi-cuenta | SÍ (via `mt5.login`) | SÍ — descifra del account-manager |

**Regla de oro**: el `signal_copier` se conecta a la terminal MT5 que esté
abierta y logueada en la máquina (`mt5.initialize()` sin parámetros). No lee
credenciales de la plataforma. El `mt5-connector` sí conecta con credenciales
explícitas contra una única terminal (`MT5_PATH`).

---

## 2. Estado verificado en vivo

### 2.1 Cuentas registradas en account-manager (PostgreSQL)

Endpoints en `apps/platform/account-manager` (puerto 8510).

> **Estado 2026-08-06: reinicio de cuentas ("empezar de 0").** Todas las cuentas
> se borraron del account-manager. La API confirma estado limpio:
> `GET /api/v1/accounts` y `GET /api/v1/accounts/replicators` → `{"accounts":[]}`.
> Las cuentas que existían (histórico, para re-registro):

| Login | Broker | Alias | UUID |
|-------|--------|-------|------|
| `98891135` | TopOneTrader-MT5 | LST-Trading | `a16028a2-b2f8-4aa0-9a88-43547129fb2d` |
| `130064507` | ZeroMarkets-1 | zeromarkets_main | `1fe3be0d-4e57-41e7-b9b1-46793407f867` |
| `10011629660` | MetaQuotes-Demo | demo_main | `bfee8ca9-794f-4341-8155-fb79708521a5` |

> El account-manager `:8510` **no exige JWT** (solo `X-Tenant-ID`); la ruta por
> el gateway `:8000` que usa el frontend sí está protegida con `RequireAuth`.

### 2.2 Terminales MT5 corriendo ahora

| PID | Login | Broker visible | Ruta ejecutable | Desde |
|-----|-------|----------------|-----------------|-------|
| 10020 | `10011629660` | MetaQuotes-Demo (XAUUSD) | `C:\Program Files\FTMO MetaTrader 5\terminal64.exe` | 29/7 |
| 30640 | `98891135` | TopOneTrader-MT5 (XAUUSD.l) | `C:\Program Files\MetaTrader 5\terminal64.exe` | 2/8 |

### 2.3 Instalaciones MT5 presentes en disco

```
C:\Program Files\FTMO MetaTrader 5\terminal64.exe
C:\Program Files\GNT Capital Terminal\terminal64.exe
C:\Program Files\MetaTrader\terminal64.exe
C:\Program Files\MetaTrader 5\terminal64.exe
C:\Program Files\MetaTrader 5 Terminal\terminal64.exe
```

> **Hallazgo**: la terminal MetaQuotes-Demo corre desde
> `FTMO MetaTrader 5\terminal64.exe`, NO desde `MetaTrader 5`. O sea que el
> `mt5-connector` con `MT5_PATH` default (`C:\Program Files\FTMO MetaTrader 5\...`)
> coincide con la terminal de MetaQuotes. Para TopOneTrader haría falta apuntar
> a `C:\Program Files\MetaTrader 5\terminal64.exe`.

---

## 3. Arquitectura de conexión (detalle)

### 3.1 signal_copier (ejecución de señales, single-terminal)

- `executor.py:68` → `mt5.initialize()` **sin path ni credenciales**.
- Se conecta a la terminal que esté abierta y logueada en el equipo.
- `mt5_status_writer()` (`main.py:976`) escribe cada 5s a `var/mt5_status.json`
  (balance, equity, posiciones, login, server).
- También escribe `account_snapshot.json` / `positions_snapshot.json` legacy en
  `D:\TradingBotMT5` que consume el frontend.
- **Limitación**: si hay 2 terminales abiertas, no hay mapeo explícito de a cuál
  se conecta. Elige la que `mt5.initialize()` resuelva por defecto.

### 3.2 mt5-connector (broker service, multi-cuenta)

- `main.go:48` → lee `MT5_PATH` (default `C:\Program Files\FTMO MetaTrader 5\terminal64.exe`).
- `session/manager.go` → en startup (y cada 5 min) llama a account-manager
  `GET /api/v1/accounts` con `X-Service-Token` + `X-Tenant-ID`.
- Para cada cuenta activa pide `GET /api/v1/accounts/:id/credentials`
  (devuelve login + password **descifrada**) y guarda el pool en memoria.
- Estrategia (comentario en `session/manager.go:2-6`): **un solo terminal64.exe**
  y switch de cuenta vía `mt5.login(login, password, server)` bajo demanda.
- El bridge Python (`mt5_bridge_daemon.py`) usa `initialize(path=...)` +
  `mt5.login(...)` con esas credenciales.

### 3.3 mt5_snapshot_pusher (snapshots a account-manager)

- `scripts/mt5_snapshot_pusher.py` → **NO abre MT5**.
- Lee `var/mt5_status.json` + `positions_snapshot.json` (escritos por signal_copier)
  y hace `POST /api/v1/accounts/:id/snapshot` al account-manager.
- Así el balance en vivo llega del signal_copier → archivos → account-manager →
  dashboard.

---

## 4. Flujo de datos (de MT5 al dashboard)

```
                    ┌──────────────────────────────────────────────┐
                    │  Terminal MT5 (abierta y logueada en el PC)  │
                    │  (ej. FTMO MetaTrader 5\terminal64.exe)      │
                    └───────────────────┬──────────────────────────┘
                                        │ mt5.initialize() (sin creds)
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │  signal_copier (Python)   ──►  mt5_status.json │
                    │  bot/main.py (PID 24712)     cada 5 segundos   │
                    └───────────────────┬──────────────────────────┘
                                        │ lectura
                    ┌───────────────────▼──────────────────────────┐
                    │  mt5_snapshot_pusher.py (snapshots)           │
                    └───────────────────┬──────────────────────────┘
                                        │ POST /api/v1/accounts/:id/snapshot
                                        ▼
                    ┌──────────────────────────────────────────────┐
                    │  account-manager (PostgreSQL)  ──►  UI        │
                    │  mt5-connector (exec, multi-cuenta)           │
                    └──────────────────────────────────────────────┘
```

---

## 5. Cómo agregar una cuenta nueva (flujo real)

1. **Frontend** `AccountsPage → Add Account`: login, password, server, alias.
2. `POST /api/v1/accounts` → account-manager guarda password encriptada (AES-GCM).
3. El `signal_copier` **NO se entera** — sigue usando la terminal ya abierta.
4. El `mt5-connector` la detecta en su próximo `RefreshCreds()` (≤5 min) y puede
   ejecutar en ella vía `mt5.login()` sobre `MT5_PATH`.

**Orden que importa**:

| Componente | Orden |
|------------|-------|
| signal_copier | La terminal MT5 debe estar abierta + logueada **ANTES** de arrancarlo |
| mt5-connector | No importa — usa credenciales explícitas, terminal solo debe estar instalada en `MT5_PATH` |

---

## 6. Estrategia multi-broker elegida: "una terminal por broker, cuentas por login"

- Cada **broker** = una instalación de `terminal64.exe` (path distinto).
- Cada **cuenta** = login/password/server en el account-manager.
- El `mt5-connector` apunta a UNA terminal (`MT5_PATH`), así que para operar con
  N brokers se necesitan **N instancias de mt5-connector**, cada una con su `MT5_PATH`.

### Instancias necesarias para los brokers actuales

| Broker | terminal64.exe | mt5-connector | MT5_PATH a configurar |
|--------|----------------|---------------|------------------------|
| MetaQuotes-Demo | `C:\Program Files\FTMO MetaTrader 5\terminal64.exe` | 1 | (default, ya coincide) |
| TopOneTrader-MT5 | `C:\Program Files\MetaTrader 5\terminal64.exe` | 2 | `C:\Program Files\MetaTrader 5\terminal64.exe` |
| ZeroMarkets | *(instalar si aplica)* | 3 | path propio |

### Opciones de implementación (a decidir)

1. **Múltiples instancias de mt5-connector** — un proceso por broker, cada uno
   con su `MT5_PATH` y su pool de cuentas. (recomendado, reusa el diseño actual)
2. **Agregar `terminal_path` por cuenta** — modificar account-manager + UI para
   que cada cuenta guarde la ruta de su terminal64.exe; el connector elige path
   según la cuenta objetivo. (requiere desarrollo)

---

## 7. Copy trading (el "plus configurable")

**Estado actual**:
- Ya existe el flag `copy_enabled` en account-manager + endpoint
  `GET /api/v1/accounts/replicators` (solo cuentas con `copy_enabled=true`).
- Página Copy Trading en el frontend. Nombre de gestión decidido (2026-08-06):
  **"MT5 Settings Copy"** — cubre tanto la config del bot (`/mt5-settings` →
  `Mt5SettingsPage`: lotes, riesgo diario/semanal/mensual, trailing, scale-out,
  break-even, correlation guard) como la gestión de copias (`/copy-trading` →
  `CopyTradingPage`: replicators, groups, accounts, jobs, stats).
- Pero el `signal_copier` actual es single-account: **no copia** operaciones
  entre cuentas por sí solo.

**Para copy real maestro→sub-cuentas** habría que:
1. Definir la cuenta maestra (fuente de señales).
2. Usar el `mt5-connector` multi-cuenta para replicar en N sub-cuentas.
3. Hacer pública la cuenta maestra via `/accounts/replicators`.

Es desarrollo nuevo, no config. Ver `13-ROADMAP.md` para prioridades.

---

## 8. Referencias de código

| Pieza | Ruta |
|-------|------|
| signal_copier connect | `apps/integrations/tnsvt-bot/signal_copier/executor.py:66` |
| status writer (5s) | `apps/integrations/tnsvt-bot/signal_copier/main.py:976` |
| bot main (PID 24712) | `apps/integrations/tnsvt-bot/bot/main.py` |
| snapshot pusher | `apps/integrations/tnsvt-bot/scripts/mt5_snapshot_pusher.py` |
| mt5-connector main (MT5_PATH) | `apps/broker/mt5-connector/main.go:48` |
| session manager (multi-cuenta) | `apps/broker/mt5-connector/internal/session/manager.go` |
| account-manager modelos | `apps/platform/account-manager/internal/models/models.go` |
| account-manager handlers | `apps/platform/account-manager/internal/handlers/handlers.go` |
| frontend accounts | `apps/frontend/src/pages/AccountsPage.tsx` |
| bridge proxies MT5 | `apps/bridge/bridge-api/main.py:1617,1644` |
