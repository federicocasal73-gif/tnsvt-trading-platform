# TNSVT LiquidityZones EA (MQL5)

Expert Advisor for **MetaTrader 5** that detects institutional liquidity
structures and publishes them to the TNSVT liquidity-engine Python service.

> Part of `F4 — MQL5 Liquidity EA` in the TNSVT roadmap.

## What it detects

| Type | Description |
|------|-------------|
| `swing_high` | Local maximum: highest high among ±N bars (default 5) |
| `swing_low` | Local minimum: lowest low among ±N bars |
| `equal_high` | Two swing highs within tolerance, separated 5–100 bars (liquidity pool) |
| `equal_low` | Two swing lows within tolerance, separated 5–100 bars |
| `fvg_bull` | 3-candle imbalance where middle candle leaves a gap up (Fair Value Gap) |
| `fvg_bear` | 3-candle imbalance where middle candle leaves a gap down |
| `bos_bull` | Close beyond a swing high (Break of Structure) |
| `bos_bear` | Close below a swing low |

Each zone is drawn on the chart as a semi-transparent rectangle and
also sent to the Python receiver every `InpPublishSeconds` (default 60s).

## Architecture

```
┌─────────────────┐    WebRequest     ┌─────────────────────────┐
│ MT5 Terminal    │ ────────────────► │ liquidity-engine (:8050)│
│  + LiquidityZones│   POST /zones   │                         │
│    EA           │    JSON          │  POST /zones (ingest)   │
│                 │ ◄─────────────── │  GET  /zones/latest    │
└─────────────────┘    200 OK          │  GET  /zones/summary   │
                                       └─────────────────────────┘
```

## Installation

### 1. Compile the EA

1. Open **MetaEditor** (F4 from MT5).
2. **File → Open Data Folder**.
3. Copy the contents of this `MQL5/` directory into your terminal's `MQL5/`:
   ```
   MQL5/
   ├── LiquidityZones.mq5
   └── Includes/
       └── LiquidityStructures.mqh
   ```
4. In MetaEditor, open `LiquidityZones.mq5` and press **F7** (Compile).
   If `LiquidityStructures.mqh` doesn't appear under `Includes/MQL5`, you
   need to copy the file there. It is referenced via `#include <LiquidityStructures.mqh>`.

### 2. Allow WebRequest in MT5

The EA uses `WebRequest()` to POST data to the Python service. By default
MT5 blocks HTTP. To allow:

1. **Tools → Options → Expert Advisors**.
2. Check **"Allow WebRequest for listed URL"**.
3. Add your liquidity-engine URL, e.g.:
   ```
   http://localhost:8050
   ```
   (Or whatever host/port you set in `InpWebhookURL`.)

### 3. Configure inputs

Drag `LiquidityZones` onto a chart. In the Inputs tab:

| Input | Default | Description |
|-------|---------|-------------|
| `InpWebhookURL` | `http://localhost:8050` | liquidity-engine base URL |
| `InpWebhookPort` | `8050` | (kept for legacy; WebRequest uses URL host) |
| `InpWebhookPath` | `/zones` | Endpoint path |
| `InpPublishSeconds` | `60` | How often to send zones |
| `InpSwingLookback` | `5` | Swing detection window |
| `InpEqualTolerancePts` | `5.0` | Points tolerance for equal highs/lows |
| `InpMinFVGSizePts` | `10.0` | Min FVG size in points |
| `InpMaxZonesPerCycle` | `30` | Max zones per publish |
| `InpDrawOnChart` | `true` | Draw rectangles on chart |
| `InpAccountID` | (empty) | Override the account identifier |

### 4. Attach to chart

Drag the EA onto the chart you want to monitor (any symbol, any timeframe
independently). Each instance runs for one symbol + timeframe.

The chart name in `Experts` tab will show:
```
[LiquidityZones] EA init on XAUUSD H1 | Account: 10011629660
[LiquidityZones] Initialized: webhook=localhost:8050, swing_lookback=5, ...
```

A successful publish looks like:
```
[LiquidityZones] Published 24 zones to localhost:8050/zones (status=200)
```

### 5. Verify in Python

```bash
curl http://localhost:8050/zones/latest?symbol=XAUUSD&timeframe=H1
curl http://localhost:8050/zones/summary
```

Or from Python:
```python
from app.main import _zones_store
print(_zones_store)
```

## Payload format

POST `http://localhost:8050/zones`:

```json
{
  "account_id": "10011629660",
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "ts": 1785300000,
  "count": 24,
  "zones": [
    {
      "symbol": "XAUUSD",
      "timeframe": "H1",
      "type": "swing_high",
      "price_high": 2410.50,
      "price_low": 2408.00,
      "midpoint": 2409.25,
      "time_start": 1785299000,
      "time_end": 1785300000,
      "strength": 1,
      "swept": false
    }
  ]
}
```

Response:
```json
{
  "accepted": 24,
  "rejected": 0,
  "total": 24,
  "stored_account_id": "10011629660",
  "stored_at": "2026-07-29T03:14:22.123456+00:00"
}
```

## Troubleshooting

### `WebRequest failed: res=-1 lastError=4060`
The URL is not in the **Allow WebRequest list** (Tools → Options → Expert Advisors).
Add the host. The default port is `8050` — change if you run the service elsewhere.

### No zones detected
- The chart needs at least `InpSwingLookback * 2 + 3` bars of history.
- Lower `InpEqualTolerancePts` if you have very small ticks (e.g. JPY pairs).

### Want to integrate with the orchestrator?
The stored zones in `liquidity-engine` are **separate** from the LST signal
pipeline that publishes to NATS. To wire them into the orchestrator:

1. Expose a NATS subject or add a polling loop in `lst_engine.py` that
   reads from `_zones_store` and emits `lst_signal` events.
2. Or add an HTTP endpoint that the orchestrator polls, similar to
   `/api/v1/orchestrator/analysis/{symbol}` from F5.

## Tested with

- MetaTrader 5 demo (MetaQuotes-Demo)
- EURUSD, XAUUSD on M15 / H1 / H4
- Python 3.12 with FastAPI 0.115 + pydantic 2.x

## Roadmap

- [ ] Auto-detect swept zones (when price breaks through)
- [ ] Publish to NATS directly from MQL5 (n librería cliente C++)
- [ ] Order Block detection (last opposite candle before BOS)
- [ ] Multi-timeframe zone confluence