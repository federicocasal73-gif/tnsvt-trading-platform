import { createContext, ReactNode, useContext, useEffect, useState, useCallback } from 'react';

export type ThemeMode = 'dark' | 'light' | 'sepia' | 'auto';

interface ThemeCtx {
  theme: ThemeMode;
  setTheme: (t: ThemeMode) => void;
  resolved: 'dark' | 'light' | 'sepia';
}

const Ctx = createContext<ThemeCtx | null>(null);

const STORAGE_KEY = 'tnsvt-theme';

function readStored(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'dark' || v === 'light' || v === 'sepia' || v === 'auto') return v;
  } catch {}
  return 'dark';
}

function resolve(m: ThemeMode): 'dark' | 'light' | 'sepia' {
  if (m !== 'auto') return m;
  if (typeof window === 'undefined') return 'dark';
  const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return prefers ? 'dark' : 'light';
}

function applyThemeClass(m: ThemeMode) {
  if (typeof document === 'undefined') return;
  const r = resolve(m);
  document.documentElement.dataset.theme = r;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>(() => readStored());

  const setTheme = useCallback((t: ThemeMode) => {
    setThemeState(t);
    try { localStorage.setItem(STORAGE_KEY, t); } catch {}
    applyThemeClass(t);
  }, []);

  useEffect(() => {
    applyThemeClass(theme);
    if (theme !== 'auto') return;
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const listener = () => applyThemeClass('auto');
    mq.addEventListener?.('change', listener);
    return () => mq.removeEventListener?.('change', listener);
  }, [theme]);

  return (
    <Ctx.Provider value={{ theme, setTheme, resolved: resolve(theme) }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useTheme outside ThemeProvider');
  return c;
}
