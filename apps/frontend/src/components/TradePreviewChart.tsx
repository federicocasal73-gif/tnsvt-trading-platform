import { useCallback, useEffect, useRef, useState } from 'react';
import { createChart, CandlestickSeries, LineStyle } from 'lightweight-charts';
import { api, BridgeCandle, LivePosition } from '../lib/api';

interface Props {
  trade: LivePosition;
  candles?: BridgeCandle[];
  onClose?: () => void;
}

function toCandleData(raw: BridgeCandle[]) {
  return raw.map(c => ({
    time: c.time as any,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }));
}

export function TradePreviewChart({ trade, candles: preCandles, onClose }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);

  const symbol = trade.symbol;
  const entry = trade.open_price;
  const sl = trade.sl;
  const tp = trade.tp;
  const isBuy = trade.action === 'BUY';

  const fetchCandles = useCallback(async () => {
    if (!symbol) return null;

    const openedAt = new Date(trade.opened_at);
    const from = new Date(openedAt.getTime() - 30 * 60 * 1000).toISOString();
    const to = trade.closed_at
      ? new Date(new Date(trade.closed_at).getTime() + 5 * 60 * 1000).toISOString()
      : new Date(Date.now() + 5 * 60 * 1000).toISOString();

    try {
      const res = await api.bridge.candles(symbol, 'M5', from, to, 100);
      if (res.ok && res.candles?.length > 0) {
        return res.candles;
      }
    } catch { /* fallback */ }

    return null;
  }, [symbol, trade.opened_at, trade.closed_at]);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: 400,
      height: 240,
      layout: {
        background: { color: '#0D0D1A' },
        textColor: '#71717A',
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.04)' },
        horzLines: { color: 'rgba(255,255,255,0.04)' },
      },
      timeScale: {
        borderColor: 'rgba(255,255,255,0.08)',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: 'rgba(255,255,255,0.08)',
      },
      crosshair: { mode: 0 },
      handleScroll: false,
      handleScale: false,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;

    const load = async () => {
      const series = seriesRef.current;
      const chart = chartRef.current;
      if (!series || !chart) return;

      let data: BridgeCandle[] | null = preCandles ?? null;
      if (!data) {
        try { data = await fetchCandles(); } catch { /* noop */ }
      }

      if (!data || data.length === 0) {
        setError('No hay velas disponibles');
        return;
      }

      const raw = toCandleData(data);
      series.setData(raw);
      chart.timeScale().fitContent();

      const dashed = 2;
      if (entry) {
        series.createPriceLine({
          price: entry,
          color: '#FFFFFF',
          lineWidth: 1,
          lineStyle: dashed,
          axisLabelVisible: true,
          title: 'Entry',
        });
      }

      if (sl) {
        series.createPriceLine({
          price: sl,
          color: '#ef4444',
          lineWidth: 1,
          lineStyle: dashed,
          axisLabelVisible: true,
          title: 'SL',
        });
      }

      if (tp) {
        series.createPriceLine({
          price: tp,
          color: '#22c55e',
          lineWidth: 1,
          lineStyle: dashed,
          axisLabelVisible: true,
          title: 'TP',
        });
      }

      setError(null);
    };

    load();
  }, [fetchCandles, entry, sl, tp, preCandles]);

  return (
    <div className="relative rounded-lg border border-tnvs-border bg-tnvs-surface shadow-tnvs-strong">
      <div className="flex items-center justify-between border-b border-tnvs-border px-3 py-2">
        <span className="text-xs font-medium text-white">
          {symbol} · M5
          <span className="ml-2 text-tnvs-dim">Preview</span>
        </span>
        {onClose && (
          <button onClick={onClose} className="text-tnvs-dim hover:text-white text-xs">✕</button>
        )}
      </div>
      <div className="flex items-center gap-2 border-b border-tnvs-border/30 px-3 py-1.5 text-[10px] text-tnvs-dim font-mono">
        <span className={isBuy ? 'text-tnvs-win' : 'text-tnvs-loss'}>{isBuy ? '▲ BUY' : '▼ SELL'}</span>
        <span>Entry: {entry}</span>
        {sl && <span className="text-red-400">SL: {sl}</span>}
        {tp && <span className="text-green-400">TP: {tp}</span>}
      </div>
      <div ref={containerRef} className="h-[240px]" />
      {error && (
        <div className="flex items-center justify-center py-4 text-xs text-tnvs-dim">
          {error}
        </div>
      )}
    </div>
  );
}