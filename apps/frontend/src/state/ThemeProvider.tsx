import { createContext, ReactNode, useContext, useEffect, useState, useCallback } from 'react';

export type ThemeMode = 'dark' | 'light' | 'sepia' | 'gold';

interface ThemeCtx {
  theme: ThemeMode;
  setTheme: (t: ThemeMode) => void;
  resolved: ThemeMode;
}

const Ctx = createContext<ThemeCtx | null>(null);

const STORAGE_KEY = 'tnsvt-theme';

function readStored(): ThemeMode {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'dark' || v === 'light' || v === 'sepia' || v === 'gold') return v;
    // Retrocompat: usuarios que tenian 'auto' lo mapeamos a 'gold' (nuevo destacado)
    if (v === 'auto') return 'gold';
  } catch {}
  return 'dark';
}

function applyThemeClass(m: ThemeMode) {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = m;
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
  }, [theme]);

  return (
    <Ctx.Provider value={{ theme, setTheme, resolved: theme }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useTheme outside ThemeProvider');
  return c;
}

