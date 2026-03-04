import { useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, Activity, BookOpen } from 'lucide-react';

const tabs = [
  { path: '/', label: 'Chat', icon: MessageSquare, exact: true },
  { path: '/tracking', label: 'Suivi', icon: Activity, exact: false },
  { path: '/plans', label: 'Mes Plans', icon: BookOpen, exact: false },
] as const;

export const BottomTabs = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string, exact: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 glass-effect border-t border-border/50 h-14 safe-area-bottom">
      <div className="flex h-full items-center justify-around">
        {tabs.map(({ path, label, icon: Icon, exact }) => {
          const active = isActive(path, exact);
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              className={`flex flex-col items-center justify-center flex-1 h-full gap-0.5 transition-colors ${
                active ? 'text-primary' : 'text-muted-foreground'
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
