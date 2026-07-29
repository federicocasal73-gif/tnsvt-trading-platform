import { memo, useEffect, useState } from 'react';
import {
  Star, ExternalLink, RefreshCw, Filter, ArrowUp, ArrowDown,
  AlertTriangle, Globe, TrendingUp, Newspaper,
} from 'lucide-react';
import { api, NewsItem, NewsSentimentSummary } from '../lib/api';
import { cls } from '../utils/format';

const CATEGORIES = ['all', 'markets', 'crypto', 'economy', 'stocks'];
const SENTIMENT_FILTERS = ['all', 'POSITIVE', 'NEGATIVE', 'NEUTRAL'];

function Stars({ n }: { n: number }) {
  return (
    <span className="inline-flex items-center gap-0.5 text-amber-400">
      {Array.from({ length: 4 }).map((_, i) => (
        <Star
          key={i}
          className={cls('h-3 w-3', i < n ? 'fill-amber-400 text-amber-400' : 'text-white/[0.08]')}
        />
      ))}
    </span>
  );
}

function CategoryBadge({ cat }: { cat: string }) {
  const cfg: Record<string, { bg: string; text: string }> = {
    Geopolitica: { bg: 'bg-amber-500/20', text: 'text-amber-300' },
    FED: { bg: 'bg-blue-500/20', text: 'text-blue-300' },
    Inflacion: { bg: 'bg-red-500/20', text: 'text-red-300' },
    Macro: { bg: 'bg-purple-500/20', text: 'text-purple-300' },
    Politica: { bg: 'bg-pink-500/20', text: 'text-pink-300' },
    Dolar: { bg: 'bg-emerald-500/20', text: 'text-emerald-300' },
    Commodities: { bg: 'bg-yellow-500/20', text: 'text-yellow-300' },
    Cripto: { bg: 'bg-orange-500/20', text: 'text-orange-300' },
    Acciones: { bg: 'bg-cyan-500/20', text: 'text-cyan-300' },
    Bancos: { bg: 'bg-indigo-500/20', text: 'text-indigo-300' },
  };
  const c = cfg[cat] || { bg: 'bg-white/[0.06]', text: 'text-tnvs-muted' };
  return (
    <span className={cls('inline-flex items-center text-[10px] font-semibold px-1.5 py-0.5 rounded', c.bg, c.text)}>
      {cat}
    </span>
  );
}

function SentimentBadge({ label, score }: { label: string; score: number }) {
  const isPos = label === 'POSITIVE';
  const isNeg = label === 'NEGATIVE';
  const cfg = isPos
    ? { bg: 'bg-emerald-500/20', text: 'text-emerald-300', icon: ArrowUp }
    : isNeg
    ? { bg: 'bg-red-500/20', text: 'text-red-300', icon: ArrowDown }
    : { bg: 'bg-white/[0.06]', text: 'text-tnvs-muted', icon: Globe };
  const Icon = cfg.icon;
  return (
    <span className={cls('inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded', cfg.bg, cfg.text)}>
      <Icon className="h-3 w-3" />
      {label} ({score >= 0 ? '+' : ''}{score.toFixed(2)})
    </span>
  );
}

function NewsCard({ item }: { item: NewsItem }) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 hover:bg-white/[0.05] transition">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 text-[10px] text-tnvs-muted">
          <span className="font-mono">{item.source || '—'}</span>
          <span>•</span>
          <span>{item.published_at ? new Date(item.published_at).toLocaleString() : '—'}</span>
        </div>
        <Stars n={item.star_rating} />
      </div>

      <h3 className="text-sm font-semibold text-white leading-snug mb-1">
        {item.title}
      </h3>
      {item.description && (
        <p className="text-xs text-tnvs-muted leading-relaxed line-clamp-3 mb-3">
          {item.description}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {item.categories.map((c) => (
          <CategoryBadge key={c} cat={c} />
        ))}
        <SentimentBadge label={item.sentiment_label} score={item.sentiment_score} />
      </div>

      {item.affected_symbols.length > 0 && (
        <div className="mb-2">
          <span className="text-[10px] text-tnvs-muted block mb-1">Afecta a:</span>
          <div className="flex flex-wrap gap-1">
            {item.affected_symbols.map((s) => (
              <span key={s} className="text-[10px] font-mono bg-white/[0.04] px-1.5 py-0.5 rounded text-tnvs-muted">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {item.reactions && Object.keys(item.reactions).length > 0 && (
        <div className="rounded bg-blue-500/[0.06] border border-blue-500/20 p-2 mt-2">
          <span className="text-[10px] text-blue-300 font-semibold flex items-center gap-1 mb-1.5">
            <TrendingUp className="h-3 w-3" />
            Cómo reacciona el oro / activos
          </span>
          <div className="space-y-1">
            {Object.entries(item.reactions)
              .filter(([sym]) => ['XAUUSD', 'BTCUSD', 'NAS100', 'EURUSD', 'DXY', 'WTI', 'BRENT', 'XAGUSD'].includes(sym))
              .map(([sym, reaction]) => (
                <div key={sym} className="flex items-start gap-2 text-[10px]">
                  <span className="font-mono font-semibold text-white min-w-[60px]">{sym}</span>
                  <span className="text-tnvs-muted">{reaction}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {item.url && (
        <div className="mt-3 pt-2 border-t border-white/[0.04]">
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-blue-300 hover:text-blue-200 inline-flex items-center gap-1"
          >
            <ExternalLink className="h-3 w-3" />
            Leer fuente
          </a>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ summary }: { summary: NewsSentimentSummary | null }) {
  if (!summary || summary.total_news === 0) {
    return (
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 text-xs text-tnvs-muted text-center">
        Sin noticias cargadas todavía. Refresh para actualizar.
      </div>
    );
  }
  const overall = summary.overall_score;
  const label = summary.overall_label;
  const isPos = label === 'POSITIVE';
  const isNeg = label === 'NEGATIVE';
  const barColor = isPos ? 'bg-emerald-500' : isNeg ? 'bg-red-500' : 'bg-amber-500';

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-white flex items-center gap-2">
        <Newspaper className="h-4 w-4" />
        Pulso de noticias ({summary.total_news})
      </h3>
      <div>
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-xs text-tnvs-muted">Sentiment general</span>
          <span
            className={cls(
              'text-sm font-bold tabular-nums',
              isPos ? 'text-emerald-300' : isNeg ? 'text-red-300' : 'text-amber-300',
            )}
          >
            {overall >= 0 ? '+' : ''}{overall.toFixed(2)} ({label})
          </span>
        </div>
        <div className="h-2 w-full bg-white/[0.04] rounded overflow-hidden">
          <div
            className={cls('h-full transition-all', barColor)}
            style={{
              width: `${Math.abs(overall) * 100}%`,
              marginLeft: overall < 0 ? `${(1 + overall) * 100}%` : '50%',
            }}
          />
        </div>
      </div>

      {summary.by_symbol.length > 0 && (
        <div>
          <span className="text-[10px] text-tnvs-muted block mb-1">Por símbolo</span>
          <div className="space-y-1">
            {summary.by_symbol.slice(0, 8).map((s) => (
              <div key={s.symbol} className="flex items-center gap-2 text-[10px]">
                <span className="font-mono text-white min-w-[60px]">{s.symbol}</span>
                <span className="text-tnvs-muted">{s.news_count} noticias</span>
                <span
                  className={cls(
                    'ml-auto font-mono',
                    s.sentiment_label === 'POSITIVE' ? 'text-emerald-300' :
                    s.sentiment_label === 'NEGATIVE' ? 'text-red-300' : 'text-tnvs-muted',
                  )}
                >
                  {s.sentiment_score >= 0 ? '+' : ''}{s.sentiment_score.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(summary.by_category).length > 0 && (
        <div>
          <span className="text-[10px] text-tnvs-muted block mb-1">Por categoría</span>
          <div className="flex flex-wrap gap-1">
            {Object.entries(summary.by_category).map(([cat, count]) => (
              <span
                key={cat}
                className="text-[10px] bg-white/[0.04] px-1.5 py-0.5 rounded text-tnvs-muted"
              >
                {cat} <span className="font-mono text-white">{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export const NewsPage = memo(function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [summary, setSummary] = useState<NewsSentimentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterSentiment, setFilterSentiment] = useState('all');
  const [filterStars, setFilterStars] = useState(0);

  const fetchAll = async () => {
    try {
      const [news, sum] = await Promise.allSettled([
        api.news.latest({
          category: filterCategory,
          limit: 50,
          minStars: filterStars,
          sentiment: filterSentiment,
        }),
        api.news.sentimentSummary(),
      ]);
      if (news.status === 'fulfilled') {
        setItems(news.value.items);
        setError(null);
      } else {
        setError(String((news as PromiseRejectedResult).reason?.message || 'error'));
      }
      if (sum.status === 'fulfilled') {
        setSummary(sum.value);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await api.news.refresh();
      await fetchAll();
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, [filterCategory, filterSentiment, filterStars]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Newspaper className="h-5 w-5" />
            News & Sentiment
          </h2>
          {error && (
            <span className="text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded">
              {error}
            </span>
          )}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded border border-white/[0.06] bg-white/[0.03] hover:bg-white/[0.06] text-white px-3 py-1.5 text-xs flex items-center gap-2 disabled:opacity-50"
        >
          <RefreshCw className={cls('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          {refreshing ? 'Actualizando…' : 'Refrescar RSS'}
        </button>
      </div>

      {/* Filters */}
      <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-3.5 w-3.5 text-tnvs-muted" />
            <span className="text-xs text-tnvs-muted">Categoría:</span>
            <select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              className="bg-black/30 border border-white/[0.08] rounded px-2 py-1 text-xs text-white"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-tnvs-muted">Sentiment:</span>
            <select
              value={filterSentiment}
              onChange={(e) => setFilterSentiment(e.target.value)}
              className="bg-black/30 border border-white/[0.08] rounded px-2 py-1 text-xs text-white"
            >
              {SENTIMENT_FILTERS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Stars n={filterStars} />
            <span className="text-xs text-tnvs-muted">≥</span>
            <input
              type="range"
              min={0}
              max={4}
              step={1}
              value={filterStars}
              onChange={(e) => setFilterStars(parseInt(e.target.value))}
              className="w-20 accent-amber-400"
            />
          </div>

          <span className="ml-auto text-xs text-tnvs-muted">
            {items.length} resultados
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* News feed */}
        <div className="lg:col-span-2 space-y-3">
          {loading && items.length === 0 && (
            <div className="text-sm text-tnvs-muted">Cargando noticias…</div>
          )}
          {items.length === 0 && !loading && (
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-8 text-center text-sm text-tnvs-muted">
              {error ? '⚠️ News-analyzer no responde.' : 'Sin noticias con esos filtros. Ajustá los filtros o refrescá.'}
            </div>
          )}
          {items.map((item) => (
            <NewsCard key={item.id} item={item} />
          ))}
        </div>

        {/* Summary sidebar */}
        <div className="space-y-4">
          <SummaryCard summary={summary} />
        </div>
      </div>
    </div>
  );
});