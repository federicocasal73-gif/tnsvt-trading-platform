import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { AuthProvider, useAuth } from './lib/auth';
import { AppProvider } from './state/AppStateProvider';
import { BridgeProvider } from './state/BridgeProvider';
import { ThemeProvider } from './state/ThemeProvider';
import { Shell } from './components/Shell';
import { DashboardPage } from './pages/Dashboard';
import { PositionsPage } from './pages/Positions';
import { SignalsPage } from './pages/Signals';
import { HistoryPage } from './pages/History';
import { SettingsPage } from './pages/Settings';
import { LoginPage } from './pages/Login';
import { LivePage } from './pages/Live';
import { Mt5BotPage } from './pages/Mt5BotPage';
import { Mt5DashboardPage } from './pages/Mt5DashboardPage';
import { Mt5PositionsPage } from './pages/Mt5PositionsPage';
import { Mt5ChannelsPage } from './pages/Mt5ChannelsPage';
import { Mt5SettingsPage } from './pages/Mt5SettingsPage';
import { Mt5ControlPage } from './pages/Mt5ControlPage';
import { LandingPage } from './pages/LandingPage';
import { PricingPage } from './pages/PricingPage';
import { SignupWizard } from './pages/SignupWizard';
import { AdminPage } from './pages/AdminPage';

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
  { path: '/mt5-dashboard', name: 'mt5-dashboard', label: 'MT5 Dashboard', icon: 'dashboard' },
  { path: '/mt5-positions', name: 'mt5-positions', label: 'MT5 Positions', icon: 'positions' },
  { path: '/mt5-channels', name: 'mt5-channels', label: 'MT5 Channels', icon: 'live' },
  { path: '/mt5-settings', name: 'mt5-settings', label: 'MT5 Settings', icon: 'settings' },
  { path: '/mt5-control', name: 'mt5-control', label: 'MT5 Control', icon: 'bot' },
  { path: '/admin', name: 'admin', label: 'Admin', icon: 'settings' },
  { path: '/settings', name: 'settings', label: 'Settings', icon: 'settings' },
] as const;

const router = createBrowserRouter([
  // Public marketing & auth routes (sin Shell, sin login).
  { path: '/landing', element: <LandingPage /> },
  { path: '/pricing', element: <PricingPage /> },
  { path: '/signup', element: <SignupWizard /> },
  { path: '/login', element: <LoginPage /> },
  // Visitante en "/" → landing. Si está autenticado, el index de abajo
  // (dentro del ProtectedShell) renderiza DashboardPage.
  { path: '/', element: <Navigate to="/landing" replace /> },
  {
    path: '/',
    element: <ProtectedShell />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'positions', element: <PositionsPage /> },
      { path: 'signals', element: <SignalsPage /> },
      { path: 'live', element: <LivePage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'mt5-bot', element: <Navigate to="/mt5-dashboard" replace /> },
      { path: 'mt5-dashboard', element: <Mt5DashboardPage /> },
      { path: 'mt5-positions', element: <Mt5PositionsPage /> },
      { path: 'mt5-channels', element: <Mt5ChannelsPage /> },
      { path: 'mt5-settings', element: <Mt5SettingsPage /> },
      { path: 'mt5-control', element: <Mt5ControlPage /> },
      { path: 'admin', element: <AdminPage /> },
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
      <ThemeProvider>
        <BridgeProvider>
          <AppProvider>
            <RouterProvider router={router} />
          </AppProvider>
        </BridgeProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}