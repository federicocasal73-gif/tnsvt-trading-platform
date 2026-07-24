import { useEffect, useRef } from 'react';

interface Options {
  intervalMs?: number;
  idleIntervalMs?: number;
  pauseOnHidden?: boolean;
}

const DEFAULT_OPTIONS: Required<Options> = {
  intervalMs: 5000,
  idleIntervalMs: 30000,
  pauseOnHidden: true,
};

export function useAdaptivePolling(callback: () => void, options: Options = {}): void {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  const cbRef = useRef(callback);
  const lastActiveRef = useRef(Date.now());

  // Mantener la ref actualizada para no re-crear el interval en cada render.
  cbRef.current = callback;

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let isHidden = false;
    let isIdle = false;

    const tick = (): void => {
      cbRef.current();
      scheduleNext();
    };

    const scheduleNext = (): void => {
      if (opts.pauseOnHidden && isHidden) {
        // Pausado mientras tab esta oculta - reactivar al volver
        return;
      }
      const interval = isIdle ? opts.idleIntervalMs : opts.intervalMs;
      timeoutId = setTimeout(tick, interval);
    };

    const onVisibility = (): void => {
      isHidden = document.hidden;
      if (!isHidden) {
        // Al volver, refrescar inmediatamente
        if (timeoutId) clearTimeout(timeoutId);
        tick();
      } else if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    };

    const onActivity = (): void => {
      const now = Date.now();
      const wasIdle = isIdle;
      isIdle = now - lastActiveRef.current > 60000;
      if (wasIdle && !isIdle) {
        // Volvimos de idle - refrescar inmediatamente
        if (timeoutId) clearTimeout(timeoutId);
        tick();
      }
      lastActiveRef.current = now;
    };

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility);
    }
    if (typeof window !== 'undefined') {
      ['mousemove', 'keydown', 'scroll', 'touchstart'].forEach(ev => {
        window.addEventListener(ev, onActivity, { passive: true });
      });
    }

    tick();

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility);
      }
      if (typeof window !== 'undefined') {
        ['mousemove', 'keydown', 'scroll', 'touchstart'].forEach(ev => {
          window.removeEventListener(ev, onActivity);
        });
      }
    };
  }, [opts.intervalMs, opts.idleIntervalMs, opts.pauseOnHidden]);
}