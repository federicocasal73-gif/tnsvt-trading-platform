# TNSVT V2 - Risk Engine

Evalúa el riesgo de cada señal antes de ejecutar. Consume signals de NATS, aplica reglas configurables, y publica decisiones (approved/rejected).

## 🎯 Responsabilidad

- **Consumir** `trading.signal.created` de NATS
- **Evaluar riesgo** contra límites configurables
- **Position sizing** basado en % de riesgo
- **Tracking de P&L** diario/semanal/mensual
- **Trailing stop** dinámico
- **Publicar** decisiones a NATS (`trading.signal.validated` / `.rejected`)

## 🛡️ Reglas de Riesgo (configurables por tenant)

| Regla | Default | Descripción |
|-------|---------|-------------|
| Daily Loss Limit | $500 | Si P&L diario ≤ -$500, rechaza todas |
| Weekly Loss Limit | $1500 | Si P&L semanal ≤ -$1500, rechaza todas |
| Daily Profit Target | $1000 | Si P&L diario ≥ $1000, deja de operar (preserve gains) |
| Max Open Positions | 5 | Límite de posiciones simultáneas |
| Max Exposure Per Symbol | $10,000 | Exposición máxima por instrumento |
| Min Confidence | 0.3 | Score mínimo de AI (si AI-scored) |
| Trailing Stop | enabled | Stop loss dinámico |
| Trailing Step | 10 pips | Cada cuántos pips se ajusta |
| Trailing Start | 20 pips | Activar trailing después de N pips profit |

## 📡 NATS Subscriptions

```
trading.signal.created     → evaluar riesgo
                              ↓
                            trading.signal.validated (approved)
                            trading.signal.rejected  (rejected)
```

## 📡 NATS Publishing

```
trading.signal.validated    → execution-engine consume
trading.signal.rejected     → audit-engine consume
trading.position.opened     → audit, dashboard
trading.position.closed     → audit, dashboard
```

## 📡 HTTP API

| Método | Path | Descripción |
|--------|------|-------------|
| POST | `/api/v1/risk/evaluate` | Evaluar señal manual |
| GET | `/api/v1/risk/exposure` | Exposición actual |
| GET | `/api/v1/risk/limits` | Límites del tenant |
| PUT | `/api/v1/risk/limits` | Update límites |
| GET | `/api/v1/risk/stats` | Estadísticas P&L |
| GET | `/api/v1/risk/positions` | Posiciones abiertas |
| POST | `/api/v1/risk/positions/update` | Update precio |
| POST | `/api/v1/risk/trade-opened` | Trade abierto |
| POST | `/api/v1/risk/trade-closed` | Trade cerrado |

## 💰 Position Sizing

Cálculo basado en % de riesgo:

```
lot = (balance * risk_percent) / (sl_distance_pips * pip_value)
```

- **balance**: account balance (Fase 1: $10k default; Fase 2: consultar broker)
- **risk_percent**: % del balance a arriesgar (default 1%)
- **sl_distance_pips**: distancia del SL en pips
- **pip_value**: $10 por standard lot (simplificado para Fase 1)

## 🛑 Trailing Stop

Activación y ajuste dinámico:
- **Start**: trailing se activa después de N pips a favor
- **Step**: cada cuántos pips se ajusta el SL
- Solo se mueve a favor (nunca atrás)

Ejemplo BUY con step=10, start=20:
1. Entry: 1.0850, SL: 1.0830
2. Price sube a 1.0870 (20 pips) → trailing activo
3. Price sube a 1.0880 → trailing SL = 1.0870
4. Price sube a 1.0890 → trailing SL = 1.0880
5. Price baja a 1.0880 → cierra en profit

## 🗄️ Schema PostgreSQL

- `risk.limits` - Límites por tenant (default si no existe)
- `risk.positions` - Posiciones abiertas/cerradas con trailing stop
- `risk.daily_stats` - P&L diario, trades won/lost

## 🚀 Desarrollo

```bash
cd apps/risk/risk-engine
go mod tidy
go run .
```

## 🔗 Integraciones

- **PostgreSQL**: persistencia (limits, positions, stats)
- **Redis**: cache de P&L diario
- **NATS**: consume signals, publica decisions
- **Próximos**: execution-engine consume `trading.signal.validated`

## 📋 Ver También

- [`docs/02-SERVICES-CATALOG.md`](../../../docs/02-SERVICES-CATALOG.md)
- [`docs/09-RESILIENCE.md`](../../../docs/09-RESILIENCE.md)