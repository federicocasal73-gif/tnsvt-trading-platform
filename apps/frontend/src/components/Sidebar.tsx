import { memo } from 'react';
import { Activity, BarChart3, Bot, History, LayoutDashboard, ListChecks, Radio, Settings, LogOut } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { cls } from '../utils/format';

export interface NavItem {
  id: string;
  label: string;
  icon: string; // lucide-react icon name (mapped below)
}

interface SidebarProps {
  page: string;
  setPage: (id: string) => void;
  items: NavItem[];
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  dashboard: LayoutDashboard,
  activity: Activity,
  positions: Activity,
  signals: BarChart3,
  live: Radio,
  history: ListChecks,
  bot: Bot,
  settings: Settings,
};

export const Sidebar = memo(function Sidebar({ page, setPage, items }: SidebarProps) {
  const { logout } = useAuth();

  return (
    <aside className="flex h-full w-56 shrink-0 flex-col border-r border-tnvs-border bg-tnvs-void/40">
      <div className="px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-tnvs-glow text-white shadow-tnvs-soft">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <div className="font-pixel text-[10px] uppercase tracking-[0.18em] text-white/90">TNSVT</div>
            <div className="text-xs text-tnvs-muted">Terminal Financiera</div>
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 px-2">
        {items.map(({ id, label, icon }) => {
          const Icon = ICON_MAP[icon] ?? Activity;
          const active = page === id;
          return (
            <button
              key={id}
              onClick={() => setPage(id)}
              data-testid={`nav-${id}`}
              className={cls(
                'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-white/[0.06] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]'
                  : 'text-tnvs-muted hover:bg-white/[0.03] hover:text-white',
              )}
            >
              <Icon className={cls('h-4 w-4', active && 'text-tnvs-purple')} />
              <span>{label}</span>
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-tnvs-purple shadow-[0_0_8px_currentColor]" />}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-tnvs-border px-3 py-3">
        <button
          onClick={logout}
          data-testid="nav-logout"
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-tnvs-muted hover:bg-white/[0.03] hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4" />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
});