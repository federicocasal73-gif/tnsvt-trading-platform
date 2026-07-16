import React from 'react';

interface State { error: Error | null; }

export class ErrorBoundary extends React.Component<{ scope: string; children: React.ReactNode; fallback?: React.ReactNode; onError?: (e: Error) => void }, State> {
  state: State = { error: null };
  static getDerivedStateFromError(e: Error) { return { error: e }; }
  componentDidCatch(e: Error) { this.props.onError?.(e); }
  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;
    const isApp = this.props.scope === 'app';
    return (
      <div className={cls('flex flex-col items-center justify-center gap-4', isApp ? 'h-screen' : 'h-full')}>
        <div className="text-3xl">⚠</div>
        <h2 className="text-lg font-semibold text-white">Something went wrong</h2>
        <pre className="max-w-md text-xs text-tnvs-dim text-center">{this.state.error.message}</pre>
        <button className="tnvs-btn-primary" onClick={() => this.setState({ error: null })}>Try Again</button>
      </div>
    );
  }
}

function cls(...parts: (string | false | null | undefined)[]) { return parts.filter(Boolean).join(' '); }
