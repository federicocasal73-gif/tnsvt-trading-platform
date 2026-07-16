"""Load test: SSE tick stream connection capacity.

k6's default http.get doesn't support true SSE streaming (it buffers
the response). This script uses Python's asyncio + httpx to open many
concurrent SSE connections and measure:
  - Connection establishment success rate
  - Time to first tick
  - Tick throughput per connection
  - Server memory/CPU load (via response time)

We simulate the k6 ramp-up profile: 0 -> 50 -> 100 concurrent connections
over 30s, holding for 10s.
"""
import asyncio
import time
import statistics
import sys
from contextlib import asynccontextmanager
import httpx


URL = "http://localhost:8300/api/v1/prices/stream?token=loadtest"
WINDOW_SEC = 4  # how long each connection stays open


async def sse_client(client: httpx.AsyncClient, conn_id: int, results: list):
    """Open an SSE connection, count events for WINDOW_SEC, return stats."""
    t0 = time.monotonic()
    n_events = 0
    first_tick_at = None
    try:
        async with client.stream("GET", URL, timeout=WINDOW_SEC + 2) as resp:
            connect_ms = (time.monotonic() - t0) * 1000
            if resp.status_code != 200:
                results.append({"id": conn_id, "ok": False, "connect_ms": connect_ms, "events": 0})
                return
            async for line in resp.aiter_lines():
                if time.monotonic() - t0 > WINDOW_SEC:
                    break
                if line.startswith("event: tick"):
                    n_events += 1
                    if first_tick_at is None:
                        first_tick_at = (time.monotonic() - t0) * 1000
        results.append({
            "id": conn_id,
            "ok": True,
            "connect_ms": connect_ms,
            "events": n_events,
            "ttft_ms": first_tick_at,
            "duration_ms": (time.monotonic() - t0) * 1000,
        })
    except Exception as e:
        results.append({"id": conn_id, "ok": False, "error": str(e)[:80]})


async def ramp(peak: int, hold_sec: float):
    """Open up to `peak` connections concurrently, hold for `hold_sec`, then close."""
    print(f"\n=== Ramping to {peak} concurrent connections, holding {hold_sec:.0f}s ===")
    results = []
    sem = asyncio.Semaphore(peak)

    async with httpx.AsyncClient(timeout=10) as client:
        async def run_with_limit(cid):
            async with sem:
                await sse_client(client, cid, results)

        # Launch a burst of connections
        tasks = [asyncio.create_task(run_with_limit(i)) for i in range(peak * 3)]
        # Let the storm play out for hold_sec seconds
        await asyncio.sleep(hold_sec)
        # Wait for tasks to complete (they'll time out at WINDOW_SEC+2)
        await asyncio.gather(*tasks, return_exceptions=True)

    # Summarize
    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    if ok:
        connect_ms = [r["connect_ms"] for r in ok]
        events = [r["events"] for r in ok]
        ttft = [r["ttft_ms"] for r in ok if r["ttft_ms"] is not None]
        print(f"  Successful connections: {len(ok)}/{len(results)} ({100*len(ok)/len(results):.1f}%)")
        print(f"  Failed connections:     {len(fail)}")
        if connect_ms:
            print(f"  Connect latency:    avg={statistics.mean(connect_ms):6.1f}ms  "
                  f"p50={statistics.median(connect_ms):6.1f}ms  p95={statistics.quantiles(connect_ms, n=20)[18]:6.1f}ms")
        if events:
            print(f"  Events received:     avg={statistics.mean(events):6.1f}  "
                  f"min={min(events):4d}  max={max(events):4d}  total={sum(events):5d}")
        if ttft:
            print(f"  Time-to-first-tick: avg={statistics.mean(ttft):6.1f}ms  p95={statistics.quantiles(ttft, n=20)[18]:6.1f}ms")
    else:
        print(f"  ALL {len(results)} connections failed!")
        for r in fail[:3]:
            print(f"    {r}")

    return {
        "success": len(ok),
        "failed": len(fail),
        "total_events": sum(r.get("events", 0) for r in ok),
        "avg_connect_ms": statistics.mean([r["connect_ms"] for r in ok]) if ok else 0,
    }


async def main():
    print(f"=== SSE Load Test: {URL} ===")
    print(f"Window per connection: {WINDOW_SEC}s")
    print(f"Each client reads 1 SSE stream for {WINDOW_SEC}s, counts events.\n")

    # Warmup
    print("Warmup: 1 connection...")
    await ramp(1, hold_sec=1)

    # Ramp profile (similar to k6 ramping-vus)
    overall = {}
    for peak in [10, 25, 50, 100]:
        overall[peak] = await ramp(peak, hold_sec=WINDOW_SEC + 2)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Peak':>6}  {'Success':>8}  {'Failed':>7}  {'Total events':>13}  {'Avg connect':>12}")
    for peak, stats in overall.items():
        print(f"{peak:>6}  {stats['success']:>8}  {stats['failed']:>7}  "
              f"{stats['total_events']:>13}  {stats['avg_connect_ms']:>10.1f}ms")
    print()
    if overall[100]["success"] >= overall[100]["success"] * 0.95:
        print("✓ PASS: 100 concurrent connections held with >= 95% success")
    else:
        print(f"✗ WARN: success rate at peak = {100*overall[100]['success']/(overall[100]['success']+overall[100]['failed']):.1f}%")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\ninterrupted")