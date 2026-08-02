import { useCallback } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Sidebar, NavItem, SidebarSection } from './Sidebar';
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

  if (!isAuthenticated) {
    return null;
  }

  const currentRoute = ROUTES.find(r => r.path === location.pathname) ?? ROUTES[0];

  const monitorRoutes = ROUTES.filter(r => r.scope === 'monitor');
  const operateRoutes = ROUTES.filter(r => r.scope === 'operate');
  const communityRoutes = ROUTES.filter(r => r.scope === 'community');
  const adminRoutes = ROUTES.filter(r => r.scope === 'admin');

  const toNavItem = (r: typeof ROUTES[number]): NavItem => ({
    id: r.name,
    label: r.label,
    icon: r.icon,
  });

  const sections: SidebarSection[] = [
    { title: 'Monitor', items: monitorRoutes.map(toNavItem) },
    { title: 'Operación', items: operateRoutes.map(toNavItem) },
    { title: 'Comunidad', items: communityRoutes.map(toNavItem) },
    { title: 'Admin', items: adminRoutes.map(toNavItem) },
  ];

  return (
    <div className="flex h-full">
      <Sidebar page={currentRoute.name} setPage={handleSetPage} sections={sections} />
      <div className="flex flex-1 flex-col min-w-0">
        <TopBar />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}