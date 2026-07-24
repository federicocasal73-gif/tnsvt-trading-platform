import { CSSProperties } from 'react';

interface SkeletonProps {
  className?: string;
  style?: CSSProperties;
  rounded?: 'sm' | 'md' | 'lg' | 'full';
}

export function Skeleton({ className = '', style, rounded = 'md' }: SkeletonProps) {
  const roundedCls = rounded === 'full' ? 'rounded-full' : rounded === 'lg' ? 'rounded-lg' : rounded === 'sm' ? 'rounded-sm' : 'rounded-md';
  return (
    <div
      className={`t-skeleton ${roundedCls} ${className}`}
      style={style}
    />
  );
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface p-4">
      <Skeleton className="h-4 w-32 mb-3" />
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
}

export function SkeletonGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} rows={2} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="rounded-lg border border-tnvs-border bg-tnvs-surface">
      <Skeleton className="h-10 w-full rounded-none border-b border-tnvs-border" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-2 border-b border-tnvs-border/40 px-4 py-3">
          {Array.from({ length: cols }).map((__, j) => (
            <Skeleton
              key={j}
              className="h-3"
              style={{ width: `${100 / cols}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}