import { createContext, ReactNode, useContext, useState, useCallback, useRef } from 'react';
import { cls } from '../utils/format';

interface Toast { id: number; message: string; kind: 'success' | 'error' | 'info' | 'warn'; ttl: number; exiting?: boolean; }

interface ToastCtx { push: (m: string, k?: Toast['kind'], ttl?: number) => void; success: (m: string) => void; error: (m: string) => void; info: (m: string) => void; warn: (m: string) => void; }

const Ctx = createContext<ToastCtx | null>(null);

export function useToast() { const c = useContext(Ctx); if (!c) throw new Error('useToast outside ToastProvider'); return c; }

let _id = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: number) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 200);
  }, []);

  const push = useCallback((message: string, kind: Toast['kind'] = 'info', ttl = 4500) => {
    const id = ++_id;
    setToasts(prev => [...prev, { id, message, kind, ttl }]);
    if (ttl > 0) {
      const timer = setTimeout(() => remove(id), ttl);
      timers.current.set(id, timer);
    }
  }, [remove]);

  const api: ToastCtx = {
    push,
    success: useCallback((m: string) => push(m, 'success'), [push]),
    error: useCallback((m: string) => push(m, 'error'), [push]),
    info: useCallback((m: string) => push(m, 'info'), [push]),
    warn: useCallback((m: string) => push(m, 'warn'), [push]),
  };

  const iconMap: Record<string, string> = { success: '✓', error: '✕', info: 'ℹ', warn: '⚠' };

  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 top-14 z-50 flex w-[360px] flex-col gap-2">
        {toasts.map(t => (
          <div
            key={t.id}
            className={cls(
              'pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-tnvs-soft transition-all duration-200',
              t.exiting ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0',
              t.kind === 'success' ? 'border-tnvs-win/30 bg-tnvs-win/10 text-tnvs-win' : '',
              t.kind === 'error' ? 'border-tnvs-loss/30 bg-tnvs-loss/10 text-tnvs-loss' : '',
              t.kind === 'info' ? 'border-tnvs-blue/30 bg-tnvs-blue/10 text-tnvs-blue' : '',
              t.kind === 'warn' ? 'border-tnvs-warn/30 bg-tnvs-warn/10 text-tnvs-warn' : '',
            )}
            onClick={() => remove(t.id)}
          >
            <span className="mt-0.5 shrink-0">{iconMap[t.kind]}</span>
            <span className="flex-1">{t.message}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
