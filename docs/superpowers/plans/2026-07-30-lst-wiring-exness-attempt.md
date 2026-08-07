# Plan de cableado LST / News / Macro / Risk Dashboard

Fecha: 2026-07-30
Estado: En ejecución (build mode)
Alcance: Cablear end-to-end zonas liquidez → señal → ejecución MT5 (independiente del copy), integrar news/macro/history/risk dashboard al frontend.

## Diagnóstico previo

Pipeline LST existente:

```
EA MQL5 (LiquidityZones) ──POST /zones──► liquidity-engine :8050 ──NATS tnsvt.lst.signal──►
orchestrator :8060 (filtro macro/corr, SL/TP/lot) ──NATS trading.signal.validated──►
execution-engine :8004 ──POST /api/v1/brokers/orders──► mt5-connector :8007 ──► MT5
```

Pipeline copy (independiente): Telegram → bridge-api :8522 → copier → MT5 directo.

Gaps detectados:

1. **Zonas desconectadas** (`apps/ai/liquidity-engine/main.py:30`): `_zones_store` solo guarda en memoria, no alimenta señal.
2. **News NATS huérfano**: news-analyzer publica `trading.signal.news_based`, signal-engine subscribe `trading.signal.>` solo para SSE.
3. **Gateway sin news/macro**: `/api/v1/news` y `/api/v1/macro` no registrados en `services.go`.
4. **Ejecución LST no aislada**: `DEFAULT_ACCOUNT_ID=default`, `SignalInput` no lleva `account_id`.
5. **EA no instalado**: requiere terminal MT5 con WebRequest a `http://localhost:8050`.

## Decisiones

- Zona → señal: zonas dan sesgo/dirección, LSTEngine valida y ajusta confianza.
- News → ejecución: vía signal-engine (puente NATS→HTTP ingest).
- Cuenta LST: nueva terminal/cuenta, credenciales `198595155 / Exness-MT5Trial11 / Prueba1234@`.

## Fase 1 — Registrar cuenta LST y aislar del copy

Tareas:

- Crear cuenta en account-manager `POST /api/v1/accounts` con login 198595155, server Exness-MT5Trial11, password Prueba1234@, broker Exness, alias "lst-main".
- Configurar `DEFAULT_ACCOUNT_ID` del execution-engine apuntando al UUID devuelto.
- mt5-connector: `MT5_PATH` apuntando a la terminal64.exe de la cuenta LST (pendiente confirmar ruta al usuario).
- `ACCOUNT_MANAGER_URL` + `ACCOUNT_MGR_SERVICE_TOKEN`.

## Fase 2 — Cablear zonas → señales LST

Archivo: `apps/ai/liquidity-engine/app/main.py`.

Reglas (matriz de 8 tipos de zona):

- `bos_bull` no-swept + precio acercándose/rompiendo → `liquidity_buy` (conf 0.55).
- `bos_bear` no-swept → `liquidity_sell`.
- `equal_high` no-swept + precio acercándose desde abajo → `liquidity_sell`.
- `equal_low` no-swept + precio acercándose desde arriba → `liquidity_buy`.
- `fvg_bull` activo + precio retrocede al midpoint → `liquidity_buy`.
- `fvg_bear` activo + precio retrocede al midpoint → `liquidity_sell`.
- `swing_high/low` solo contexto.

Confianza final: combinación zona + score LSTEngine (microestructura coherente sube; contradictoria baja). Publica en `tnsvt.lst.signal` (mismo subject/format LSTSignalIn).

Limpiar duplicado raíz (`apps/ai/liquidity-engine/main.py`) → dejar todo en `app/main.py` (Dockerfile corre `app.main:app`).

## Fase 3 — Cablear news al pipeline de ejecución

Crear `apps/integrations/news-bridge/` (nuevo microservicio Python):

- Suscribe NATS `trading.signal.news_based`.
- POST HTTP al signal-engine `/internal/ingest/news` (a crear) con `{tenant_id, source:"news-analyzer", symbol, action, sl, tps, lot_mode, comment, confidence}`.
- Cooldown 5 min por (symbol, action).

En `signal-engine/internal/handlers/handlers.go`: añadir handler `IngestNews POST /internal/ingest/news` que reusa la lógica de dedup + validación + persistencia + publish `trading.signal.created`.

## Fase 4 — Gateway: exponer news y macro

Archivo: `apps/gateway/api-gateway/internal/config/services.go`.

Añadir:

- `news-analyzer` → `PathPrefix: /api/v1/news`, `http://news-analyzer:8051`.
- `macro-fetcher` → `PathPrefix: /api/v1/macro`, `http://macro-fetcher:8040`.

Verificar `apps/gateway/api-gateway/main.go` que matchea subpaths.

## Fase 5 — Ejecución LST independiente del copy

Opción B recomendada: instancia dedicada de execution-engine para LST en compose, otro puerto, otro `DEFAULT_ACCOUNT_ID`. Sin tocar lógica del engine.

Alternativa A: filtro por source en `ExecuteSignal` (mantener una sola instancia).

## Fase 6 — Frontend y terminal MT5

Validar:

- `News.tsx` (346 líneas, llama `/news/latest`).
- `Macro.tsx` (301, llama `/macro/indicators`, `/macro/market-state`, `/macro/radar`, `/macro/liquidity`).
- `History.tsx` (193, llama `/bridge/analytics/trades`).
- `Mt5RiskPage` (llama `/bridge/risk/state`, `/bridge/risk/config`, `/bridge/risk/history`).

Instalar EA en terminal LST:

1. Copiar `MQL5/LiquidityZones.mq5` + `MQL5/Includes/LiquidityStructures.mqh` a terminal destino.
2. MetaEditor → F7.
3. Tools → Options → Expert Advisors → Allow WebRequest `http://localhost:8050`.
4. Arrastrar al chart (XAUUSD por defecto).
5. Verificar log: `Published N zones to localhost:8050/zones (status=200)`.

## Fase 7 — Verificación end-to-end

- `curl http://localhost:8050/zones/latest?symbol=XAUUSD&timeframe=H1` → count > 0.
- NATS monitor `:8222`: mensajes en `tnsvt.lst.signal` y `trading.signal.validated`.
- Frontend: `/news`, `/macro`, `/signals`, `/positions` sin 5xx.
- LST paper-trade: `POST /api/v1/executions/execute` con SignalInput mínimo, verificar orden en cuenta 198595155 Exness.

## Tareas pendientes del usuario

- Confirmar `MT5_PATH` de la terminal MT5 LST (ruta absoluta a `terminal64.exe`).
- Decidir A vs B en Fase 5 (recomendado B).

## Archivos clave

- `apps/ai/liquidity-engine/app/{main.py,lst_engine.py,nats_client.py,config.py}` — generación señales.
- `apps/ai/orchestrator/app/multi_orchestrator.py` — recibe `tnsvt.lst.signal`.
- `apps/ai/news-analyzer/app/nats_publisher.py` — publica `trading.signal.news_based`.
- `apps/data/macro-fetcher/app/main.py` — :8040, sin NATS.
- `apps/broker/mt5-liquidity/MQL5/LiquidityZones.mq5` — EA.
- `apps/broker/mt5-connector/main.go` — multi-cuenta vía session manager.
- `apps/broker/mt5-connector/internal/session/manager.go` — pool de credenciales account-manager.
- `apps/platform/account-manager/internal/handlers/handlers.go` — POST `/api/v1/accounts`.
- `apps/trading/execution-engine/main.go` — `DEFAULT_ACCOUNT_ID` env.
- `apps/trading/execution-engine/internal/service/service.go` — `ExecuteSignal`.
- `apps/trading/signal-engine/internal/handlers/handlers.go` — añadir ingest news.
- `apps/gateway/api-gateway/internal/config/services.go` — registry.
- `apps/frontend/src/lib/api.ts` — `api.news.*` / `api.macro.*` clients.
- `apps/frontend/src/pages/{News,Macro,History,Mt5RiskPage}.tsx`.
- `docker-compose.dev.yml` — agregar news-bridge, LST execution-engine, news-analyzer, macro-fetcher.
