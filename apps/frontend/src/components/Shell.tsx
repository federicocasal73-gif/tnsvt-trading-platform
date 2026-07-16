import { useState, useCallback } from 'react';
import { useAuth } from '../lib/auth';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { LoginPage } from '../pages/Login';
import { DashboardPage } from '../pages/Dashboard';
import { PositionsPage } from '../pages/Positions';
import { SignalsPage } from '../pages/Signals';
import { HistoryPage } from '../pages/History';
import { SettingsPage } from '../pages/Settings';

type Page = 'dashboard' | 'positions' | 'signals' | 'history' | 'settings';

export function Shell() {
  const { isAuthenticated } = useAuth();
  const [page, setPage] = useState<Page>('dashboard');
  const handleSetPage = useCallback((p: string) => setPage(p as Page), []);

  if (!isAuthenticated) return <LoginPage />;

  const pages: Record<Page, React.ReactNode> = {
    dashboard: <DashboardPage />,
    positions: <PositionsPage />,
    signals: <SignalsPage />,
    history: <HistoryPage />,
    settings: <SettingsPage />,
  };

  return (
    <div className="flex h-full">
      <Sidebar page={page} setPage={handleSetPage} />
      <div className="flex flex-1 flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          {pages[page]}
        </main>
      </div>
    </div>
  );
}
