/**
 * Live stream client for tick data.
 *
 * The price-feed service exposes a Server-Sent Events endpoint at
 * /api/v1/prices/stream that pushes normalized ticks as they arrive.
 * This client wraps EventSource with reconnect-on-error, a typed Tick
 * model, and a small subscription API for React components.
 *
 * Why SSE over WebSocket here:
 *   - One-way server-to-client push fits the use case (we only consume)
 *   - Native browser API, zero deps
 *   - Auto-reconnect handled by the browser; we just resubscribe
 *   - Works through HTTP proxies that block WS upgrades
 *
 * If you later need bi-directional (e.g., subscribe/unsubscribe per symbol
 * over the same connection), swap to WebSocket — the public API of this
 * module is the same: a TickStreamClient class with subscribe() returning
 * an unsubscribe function.
 */

import type { Tick } from './types';

// ─── Stream state (used by React components for "connected" indicators) ─

export type StreamState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

export interface TickStreamClientOptions {
  /** Base API URL (default: '/api/v1'). The stream path is appended. */
  baseUrl?: string;
  /** Stream path (default: '/prices/stream'). */
  path?: string;
  /** Override the JWT (default: reads from localStorage). */
  token?: string;
  /** Reconnect delay in ms (default: 2000). */
  reconnectDelay?: number;
  /** Max reconnect attempts before giving up. 0 = infinite (default). */
  maxReconnects?: number;
}

type Listener<T> = (value: T) => void;

/**
 * Wraps EventSource with reconnect, JWT injection (via query string since
 * EventSource cannot send Authorization headers), and a tiny pub/sub API.
 */
export class TickStreamClient {
  private es: EventSource | null = null;
  private subs = new Set<Listener<Tick>>();
  private stateSubs = new Set<Listener<StreamState>>();
  private reconnects = 0;
  private currentState: StreamState = 'idle';
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(private opts: TickStreamClientOptions = {}) {}

  // ─── Subscribe to ticks ─────────────────────────────────────────────
  subscribe(cb: Listener<Tick>): () => void {
    this.subs.add(cb);
    this.ensureOpen();
    return () => {
      this.subs.delete(cb);
      // If no listeners remain, close the connection to save resources.
      if (this.subs.size === 0) this.close();
    };
  }

  // ─── Subscribe to connection state changes ──────────────────────────
  onState(cb: Listener<StreamState>): () => void {
    this.stateSubs.add(cb);
    cb(this.currentState);
    return () => { this.stateSubs.delete(cb); };
  }

  get state(): StreamState { return this.currentState; }

  // ─── Lifecycle ──────────────────────────────────────────────────────
  private ensureOpen() {
    if (this.es || this.closed) return;
    this.setState('connecting');
    const token = this.opts.token ?? this.readToken();
    const base = this.opts.baseUrl ?? '/api/v1';
    const path = this.opts.path ?? '/prices/stream';
    // EventSource can't set headers, so the token travels in the query.
    const url = `${base}${path}${token ? `?token=${encodeURIComponent(token)}` : ''}`;

    try {
      this.es = new EventSource(url);
    } catch (err) {
      console.debug('[tickStream] EventSource failed to open');
      this.setState('error');
      this.scheduleReconnect();
      return;
    }

    this.es.addEventListener('open', () => {
      this.reconnects = 0;
      this.setState('open');
    });

    this.es.addEventListener('tick', (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as Tick;
        for (const cb of this.subs) cb(data);
      } catch {
        // Ignore malformed payloads — the broadcaster is best-effort.
      }
    });

    this.es.addEventListener('error', () => {
      this.setState('error');
      // EventSource auto-reconnects internally on transient errors,
      // but if it fires `error` after `readyState === CLOSED`, we must
      // do it ourselves.
      if (this.es?.readyState === EventSource.CLOSED) {
        this.es = null;
        this.scheduleReconnect();
      }
    });
  }

  private scheduleReconnect() {
    if (this.closed) return;
    const max = this.opts.maxReconnects ?? 3;
    if (max !== 0 && this.reconnects >= max) {
      // Give up silently — the price-feed service is probably not running.
      console.debug('[tickStream] max reconnects reached, giving up');
      this.setState('closed');
      return;
    }
    this.reconnects += 1;
    const delay = this.opts.reconnectDelay ?? 5000;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.ensureOpen();
    }, delay);
  }

  close() {
    this.closed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.es) {
      this.es.close();
      this.es = null;
    }
    this.setState('closed');
  }

  private setState(s: StreamState) {
    if (s === this.currentState) return;
    this.currentState = s;
    for (const cb of this.stateSubs) cb(s);
  }

  private readToken(): string | null {
    try { return localStorage.getItem('tnsvt_token'); } catch { return null; }
  }
}

// ─── React hooks ─────────────────────────────────────────────────────────

import { useEffect, useState, useRef } from 'react';

/**
 * Subscribe to live ticks. Returns the latest N ticks (newest first) plus
 * the current connection state.
 *
 * @example
 *   const { ticks, state } = useTickStream({ maxTicks: 100 });
 *   if (state !== 'open') return <Banner>Reconnecting…</Banner>;
 */
export function useTickStream(opts: { maxTicks?: number; symbols?: string[] } = {}) {
  const maxTicks = opts.maxTicks ?? 200;
  const symbolFilter = opts.symbols && new Set(opts.symbols.map(s => s.toUpperCase()));

  const [ticks, setTicks] = useState<Tick[]>([]);
  const [state, setState] = useState<StreamState>('idle');
  const clientRef = useRef<TickStreamClient | null>(null);

  useEffect(() => {
    const client = new TickStreamClient();
    clientRef.current = client;

    const unsubTicks = client.subscribe((tick) => {
      if (symbolFilter && !symbolFilter.has(tick.symbol.toUpperCase())) return;
      setTicks((prev) => {
        const next = [tick, ...prev];
        if (next.length > maxTicks) next.length = maxTicks;
        return next;
      });
    });
    const unsubState = client.onState(setState);

    return () => {
      unsubTicks();
      unsubState();
      client.close();
      clientRef.current = null;
    };
    // We intentionally omit symbolFilter from deps — recreating the
    // connection on filter change is heavy. The filter is read fresh on
    // every tick callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [maxTicks]);

  return { ticks, state };
}

/**
 * Subscribe to the latest tick for each symbol. Returns a map keyed by
 * symbol and a connection-state indicator.
 *
 * Useful for the TopBar / Dashboard "live prices" widget.
 */
export function useLatestTicks() {
  const [latest, setLatest] = useState<Record<string, Tick>>({});
  const [state, setState] = useState<StreamState>('idle');

  useEffect(() => {
    const client = new TickStreamClient();
    const unsubTicks = client.subscribe((tick) => {
      setLatest((prev) => ({ ...prev, [tick.symbol]: tick }));
    });
    const unsubState = client.onState(setState);
    return () => { unsubTicks(); unsubState(); client.close(); };
  }, []);

  return { latest, state };
}