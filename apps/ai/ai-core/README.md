# AI Core Service

AI-powered signal scoring engine for the TNSVT V2 trading platform.

Combines quantitative heuristics (R/R ratio, risk %, presence of SL/TP, source confidence)
with qualitative analysis from a local LLM (Ollama) to produce a calibrated score
(0-100) and decision (EXECUTE / MONITOR / REJECT) for every incoming trading signal.

## Endpoints

| Method | Path                          | Description                                  |
|--------|-------------------------------|----------------------------------------------|
| GET    | `/health`                     | Liveness + dependency status                 |
| GET    | `/health/live`                | Liveness only                                |
| GET    | `/health/ready`               | Readiness (Redis + NATS required)            |
| GET    | `/metrics`                    | Prometheus metrics                           |
| POST   | `/api/v1/score`               | Score a single signal (sync)                 |
| POST   | `/api/v1/score/batch`         | Score up to 100 signals                      |
| GET    | `/api/v1/signals/scored`      | List recently scored signals (paginated)     |

## NATS

| Direction | Subject                  | Description                          |
|-----------|--------------------------|--------------------------------------|
| Consume   | `trading.signal.received`| Raw signals from signal-engine       |
| Publish   | `trading.signal.scored`  | Scored signals for downstream services|

Stream: `TRADING_SIGNALS` (subjects `trading.signal.>`)

## Configuration

All settings are loaded from environment variables with the `AI_CORE_` prefix
(see `app/services/config.py` for defaults).

Key vars:
- `AI_CORE_OLLAMA_URL` (default: `http://ollama:11434`)
- `AI_CORE_OLLAMA_MODEL` (default: `llama3.2:3b`)
- `AI_CORE_OLLAMA_ENABLED` (default: `true`)
- `AI_CORE_SCORE_EXECUTE_THRESHOLD` (default: `70.0`)
- `AI_CORE_SCORE_MONITOR_THRESHOLD` (default: `50.0`)
- `AI_CORE_SCORE_MIN_CONFIDENCE` (default: `0.40`)

## Running locally

```bash
cd apps/ai/ai-core
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8200 --reload
```

Then test:

```bash
curl -X POST http://localhost:8200/api/v1/score \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "EURUSD",
    "action": "buy",
    "entry_price": 1.1000,
    "stop_loss": 1.0950,
    "take_profit": 1.1150,
    "lot_size": 0.10,
    "confidence": 80,
    "source": "telegram"
  }'
```

Expected response:

```json
{
  "id": "...",
  "symbol": "EURUSD",
  "action": "buy",
  "score": 78.0,
  "confidence": 0.71,
  "decision": "EXECUTE",
  "llm_summary": "...",
  "features": { "rr_ratio": 3.0, "risk_pct": 0.455, ... },
  "model_version": "llama3.2:3b-scorer-v1",
  "scored_at": "2026-07-16T...",
  "scoring_ms": 423.4
}
```

## Tests

```bash
cd apps/ai/ai-core
PYTHONPATH=app pytest tests/ -v
```

Tests cover scoring heuristics (feature extraction, R/R logic, confidence
computation, decision boundaries, LLM-bonus keyword extraction).

## Docker

```bash
docker build -t tnsvt-ai-core .
docker run --rm -p 8200:8200 \
  -e AI_CORE_OLLAMA_URL=http://host.docker.internal:11434 \
  -e AI_CORE_NATS_URL=nats://host.docker.internal:4222 \
  tnsvt-ai-core
```

## Architecture notes

- **Graceful degradation**: if Ollama is unreachable, scoring continues with
  the technical score only. The decision still works.
- **Multi-tenant**: scored signals are stored with `tenant_id` and the same
  raw signal from different tenants is scored independently.
- **Idempotent persistence**: `INSERT ... ON CONFLICT DO NOTHING` on the
  scored-signal UUID prevents duplicate rows on subscriber retries.
- **At-least-once semantics**: NATS consumer uses pull subscription; on
  exception we `nak()` so the message goes back to the stream for retry.