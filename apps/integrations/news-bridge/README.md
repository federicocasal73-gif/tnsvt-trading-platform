# news-bridge

Puente NATS → signal-engine.

## Que hace

- Suscribe al subject JetStream `trading.signal.news_based` con durable consumer `news-bridge`.
- ack en exito, nak en fallo (JetStream reintenta).
- Por cada mensaje, llama al endpoint HTTP `/api/v1/signals` del signal-engine para inyectar la senal en el pipeline de ejecucion.
- Cooldown de 5 minutos por `(symbol, action)` para evitar spam.

## Variables de entorno

| Variable | Default | Descripcion |
|---|---|---|
| `NATS_URL` | `nats://localhost:4222` | URL del cluster NATS |
| `NEWS_SUBJECT` | `trading.signal.news_based` | Subject a consumir |
| `NATS_STREAM` | `tnsvt` | Stream JetStream (lo crea si no existe) |
| `NEWS_BRIDGE_DURABLE` | `news-bridge` | Nombre del durable consumer |
| `SIGNAL_ENGINE_URL` | `http://localhost:8003` | URL del signal-engine |
| `DEFAULT_TENANT_ID` | (vacio) | X-Tenant-ID para el request |
| `SIGNAL_INGEST_API_KEY` | (vacio) | X-API-Key si el signal-engine requiere |

## Por que JetStream (no core NATS)

El news-analyzer publica con `js.publish` (JetStream). Los subscribers deben usar `js.subscribe` con `manual_ack=True` para que el broker no pierda mensajes si el bridge se reinicia.

## Tests

```bash
python -m pytest tests/
```

13 tests cubren: cooldown, forward OK, forward rechazado, payload invalido, ack/nak, suscripcion JetStream.
