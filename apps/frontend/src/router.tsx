import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { AuthProvider, useAuth } from './lib/auth';
import { AppProvider } from './state/AppStateProvider';
import { Shell } from './components/Shell';
import { DashboardPage } from './pages/Dashboard';
import { PositionsPage } from './pages/Positions';
import { SignalsPage } from './pages/Signals';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { LoginPage } from './pages/Login';
import { LivePage } from './pages/Live';

// ─── Router setup ────────────────────────────────────────────────────────
// Each route has a name, path, icon, and component. The Shell reads the
// current route to render the sidebar/topbar, and the page component
// receives location data (params, search) as needed.

export const ROUTES = [
  { path: '/', name: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
  { path: '/positions', name: 'positions', label: 'Positions', icon: 'activity' },
  { path: '/signals', name: 'signals', label: 'Signals', icon: 'signals' },
  { path: '/live', name: 'live', label: 'Live Ticks', icon: 'live' },
  { path: '/history', name: 'history', label: 'History', icon: 'history' },
  { path: '/settings', name: 'settings', label: 'Settings', icon: 'settings' },
] as const;

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <ProtectedShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'positions', element: <PositionsPage /> },
      { path: 'signals', element: <SignalsPage /> },
      { path: 'live', element: <LivePage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);

// ProtectedShell renders the full app shell (sidebar+topbar+main) when
// authenticated; redirects to /login otherwise. Uses useAuth() so it
// stays in sync with login/logout events.
function ProtectedShell() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Shell />;
}

export function AppRouter() {
  return (
    <AuthProvider>
      <AppProvider>
        <RouterProvider router={router} />
      </AppProvider>
    </AuthProvider>
  );
}