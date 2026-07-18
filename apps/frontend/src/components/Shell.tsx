import { useCallback } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Sidebar, NavItem } from './Sidebar';
import { TopBar } from './TopBar';
import { ROUTES } from '../router';

export function Shell() {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleSetPage = useCallback((id: string) => {
    const route = ROUTES.find(r => r.name === id);
    if (route) navigate(route.path);
  }, [navigate]);

  // ProtectedShell in router.tsx already redirects unauthenticated users.
  // This guard is for the brief moment after logout but before the route
  // transitions; showing nothing is cleaner than running a navigate() in
  // the render body (which can cause loops).
  if (!isAuthenticated) {
    return null;
  }

  // Map current pathname to a sidebar "page id"
  const currentRoute = ROUTES.find(r => r.path === location.pathname) ?? ROUTES[0];
  const navItems: NavItem[] = ROUTES.map(r => ({
    id: r.name,
    label: r.label,
    icon: r.icon,
  }));

  return (
    <div className="flex h-full">
      <Sidebar page={currentRoute.name} setPage={handleSetPage} items={navItems} />
      <div className="flex flex-1 flex-col min-w-0">
        <TopBar />
        <main className={['mt5-dashboard','mt5-positions','mt5-channels','mt5-settings','mt5-control','admin'].includes(currentRoute.name) ? 'flex-1 overflow-hidden' : 'flex-1 overflow-auto p-6'}>
          {/* React Router renders the matched child route here. */}
          <Outlet />
        </main>
      </div>
    </div>
  );
}