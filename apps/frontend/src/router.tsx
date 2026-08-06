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
import { Mt5ControlPage } from './pages/Mt5ControlPage';
import { Mt5RiskPage } from './pages/Mt5RiskPage';
import { NewsPage } from './pages/News';
import { MacroPage } from './pages/Macro';
import { AnalysisPage } from './pages/Analysis';
import { LandingPage } from './pages/LandingPage';
import { PricingPage } from './pages/PricingPage';
import { SignupWizard } from './pages/SignupWizard';
import { AdminPage } from './pages/AdminPage';
import { AccountsPage } from './pages/AccountsPage';
import { Mt5SettingsPage } from './pages/Mt5SettingsPage';
import { CopyTradingPage } from './pages/CopyTradingPage';
import { CommunityPage } from './pages/Community';

// ─── Router setup ────────────────────────────────────────────────────────
// Each route has a name, path, icon, and component. The Shell reads the
// current route to render the sidebar/topbar, and the page component
// receives location data (params, search) as needed.

export const ROUTES = [
  { path: '/', name: 'dashboard', label: 'Dashboard', icon: 'dashboard', scope: 'monitor' as const },
  { path: '/positions', name: 'positions', label: 'Positions', icon: 'activity', scope: 'monitor' as const },
  { path: '/signals', name: 'signals', label: 'Signals', icon: 'signals', scope: 'monitor' as const },
  { path: '/live', name: 'live', label: 'Live Ticks', icon: 'live', scope: 'monitor' as const },
  { path: '/news', name: 'news', label: 'News', icon: 'news', scope: 'monitor' as const },
  { path: '/macro', name: 'macro', label: 'Macro', icon: 'macro', scope: 'monitor' as const },
  { path: '/history', name: 'history', label: 'History', icon: 'history', scope: 'monitor' as const },
  { path: '/mt5-dashboard', name: 'mt5-dashboard', label: 'MT5 Dashboard', icon: 'dashboard', scope: 'monitor' as const },
  { path: '/mt5-positions', name: 'mt5-positions', label: 'MT5 Positions', icon: 'positions', scope: 'monitor' as const },
  { path: '/mt5-channels', name: 'mt5-channels', label: 'MT5 Channels', icon: 'live', scope: 'operate' as const },
  { path: '/mt5-settings', name: 'mt5-settings', label: 'MT5 Settings', icon: 'settings', scope: 'operate' as const },
  { path: '/mt5-control', name: 'mt5-control', label: 'MT5 Control', icon: 'bot', scope: 'operate' as const },
  { path: '/mt5-risk', name: 'mt5-risk', label: 'Risk Dashboard', icon: 'shield', scope: 'monitor' as const },
  { path: '/accounts', name: 'accounts', label: 'Cuentas MT5', icon: 'wallet', scope: 'operate' as const },
  { path: '/copy-trading', name: 'copy-trading', label: 'MT5 Settings Copy', icon: 'copy', scope: 'operate' as const },
  { path: '/community', name: 'community', label: 'Comunidad', icon: 'community', scope: 'community' as const },
  { path: '/admin', name: 'admin', label: 'Admin', icon: 'settings', scope: 'admin' as const },
  { path: '/settings', name: 'settings', label: 'Settings', icon: 'settings', scope: 'admin' as const },
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
      { path: 'news', element: <NewsPage /> },
      { path: 'macro', element: <MacroPage /> },
      { path: 'analysis/:symbol', element: <AnalysisPage /> },
      { path: 'history', element: <HistoryPage /> },
      { path: 'mt5-bot', element: <Navigate to="/mt5-dashboard" replace /> },
      { path: 'mt5-dashboard', element: <Mt5DashboardPage /> },
      { path: 'mt5-positions', element: <Mt5PositionsPage /> },
      { path: 'mt5-channels', element: <Mt5ChannelsPage /> },
      { path: 'mt5-settings', element: <Mt5SettingsPage /> },
      { path: 'mt5-control', element: <Mt5ControlPage /> },
      { path: 'mt5-risk', element: <Mt5RiskPage /> },
      { path: 'accounts', element: <AccountsPage /> },
      { path: 'copy-trading', element: <CopyTradingPage /> },
      { path: 'community', element: <CommunityPage /> },
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