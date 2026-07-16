// k6 load test: price-feed HTTP endpoints (snapshot + symbols list).
//
// k6's default http.get() buffers responses, so it CANNOT be used to test
// the SSE streaming endpoint. This file tests the simpler HTTP endpoints
// (/api/v1/prices and /api/v1/prices/snapshot) that don't stream.
//
// For true SSE load testing, use tests/load/sse_load_test.py (Python
// script using asyncio + httpx) which handles streaming properly.
//
// Run:
//   k6 run tests/load/http-endpoints.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const BASE = __ENV.BASE || 'http://localhost:8300';

const reqErrors = new Rate('http_errors');
const snapshotLatency = new Trend('snapshot_latency_ms');

export const options = {
  stages: [
    { duration: '5s',  target: 20 },
    { duration: '10s', target: 100 },
    { duration: '10s', target: 100 },
    { duration: '5s',  target: 0 },
  ],
  thresholds: {
    'http_errors': ['rate<0.01'],
    'http_req_duration': ['p(95)<200'],
    'snapshot_latency_ms': ['p(95)<150'],
  },
  tags: { testid: 'http-endpoints-load' },
};

export default function () {
  // GET /api/v1/prices
  const listRes = http.get(`${BASE}/api/v1/prices`);
  const listOk = check(listRes, {
    'list status 200': (r) => r.status === 200,
    'list has symbols': (r) => {
      let data;
      try { data = JSON.parse(r.body); } catch (e) { return false; }
      return data && data.symbols && data.symbols.length > 0;
    },
  });

  // GET /api/v1/prices/snapshot
  const t0 = Date.now();
  const snapRes = http.get(`${BASE}/api/v1/prices/snapshot`);
  snapshotLatency.add(Date.now() - t0);
  const snapOk = check(snapRes, {
    'snapshot status 200': (r) => r.status === 200,
    'snapshot has items': (r) => {
      let data;
      try { data = JSON.parse(r.body); } catch (e) { return false; }
      return data && data.items && Array.isArray(data.items);
    },
  });

  reqErrors.add(!(listOk && snapOk) ? 1 : 0);

  sleep(0.5);
}
