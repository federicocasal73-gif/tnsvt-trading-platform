# k6 Load Tests

This directory contains load tests for the TNSVT V2 services.

## HTTP Endpoints (`http-endpoints.js`)

Tests the price-feed's non-streaming HTTP endpoints (`/api/v1/prices`
and `/api/v1/prices/snapshot`) under concurrent load using k6.

```bash
k6 run tests/load/http-endpoints.js

# Against a different host
k6 run -e BASE=http://my-price-feed:8300 tests/load/http-endpoints.js
```

### Stages

| Stage        | Duration | VUs       |
|--------------|----------|-----------|
| Ramp to 20   | 5s       | 0 → 20    |
| Ramp to 100  | 10s      | 20 → 100  |
| Hold 100     | 10s      | 100       |
| Cool-down    | 5s       | 100 → 0   |

### Thresholds

- `http_errors < 1%`
- `http_req_duration p(95) < 200ms`
- `snapshot_latency_ms p(95) < 150ms`

## SSE Tick Stream (`sse_load_test.py`)

k6's `http.get()` does NOT support true SSE streaming — it buffers the
response until the server closes the connection or the timeout fires. We
therefore use a **Python script with asyncio + httpx** for proper
streaming tests.

```bash
# Default: against http://localhost:8300
python tests/load/sse_load_test.py

# Against a different host
BASE=http://my-price-feed:8300 python tests/load/sse_load_test.py
```

### What it tests

For each peak level (10, 25, 50, 100, 300), the script opens `3 × peak`
concurrent SSE connections, each reading 4 seconds of ticks, then
measures:
- Connection success rate
- Connect latency (avg, p50, p95)
- Events received per connection
- Time-to-first-tick

### Observed results (with built-in mock, no NATS/Redis)

```
Peak   Success   Failed   Total events   Avg connect
  10        30        0           1200        19.7ms
  25        75        0           2938        29.5ms
  50       150        0           5803        66.3ms
 100       300        0          11608       143.6ms
```

300 concurrent connections, 0 failures, ~38 events per connection in 4s,
p95 connect latency 161ms.

## Notes

- The price-feed service includes a built-in mock source that emits
  synthetic ticks — no external feed required for either test.
- For production load testing, point `BASE` at the deployed service
  (e.g., `https://api.tnsvt.io`) and increase the duration.
- Real-time latency metrics require the experimental `open()` API in
  k6 (still beta); the Python script gives end-to-end streaming
  measurements instead.
