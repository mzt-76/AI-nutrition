import { useLocation, Link } from 'react-router-dom';
import {
  MessageSquare,
  Activity,
  BookOpen,
  LogOut,
  Settings,
  Salad,
  User,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useAuth } from '@/hooks/useAuth';
import { SettingsModal } from '@/components/sidebar/SettingsModal';
import { useState } from 'react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { path: '/', label: 'Chat', icon: MessageSquare, exact: true },
  { path: '/tracking', label: 'Suivi', icon: Activity, exact: false },
  { path: '/plans', label: 'Plans', icon: BookOpen, exact: false },
] as const;

export const NavSidebar = () => {
  const location = useLocation();
  const { user, signOut } = useAuth();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const isActive = (path: string, exact: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <div className="h-full w-[4.5rem] flex flex-col items-center shrink-0 relative border-r border-white/[0.06]"
      style={{
        background: 'linear-gradient(180deg, hsl(220 15% 8% / 0.95) 0%, hsl(220 15% 6% / 0.98) 100%)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Logo */}
      <Link
        to="/"
        className="flex items-center justify-center w-full h-16 group"
      >
        <div className="relative">
          <Salad className="h-7 w-7 text-primary transition-transform duration-300 group-hover:scale-110" />
          <div
            className="absolute inset-0 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300"
            style={{ boxShadow: '0 0 16px hsl(160 84% 39% / 0.4)' }}
          />
        </div>
      </Link>

      {/* Separator with green gradient */}
      <div className="w-8 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />

      {/* Navigation */}
      <nav className="flex flex-col items-center gap-1 pt-4 flex-1">
        {NAV_ITEMS.map(({ path, label, icon: Icon, exact }) => {
          const active = isActive(path, exact);
          return (
            <Link
              key={path}
              to={path}
              className={cn(
                'group relative flex flex-col items-center justify-center w-14 h-14 rounded-xl transition-all duration-200',
                active
                  ? 'text-primary'
                  : 'text-muted-foreground hover:text-foreground/80'
              )}
            >
              {/* Active indicator bar */}
              {active && (
                <div
                  className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-primary"
                  style={{ boxShadow: '0 0 8px hsl(160 84% 39% / 0.6)' }}
                />
              )}

              {/* Hover / active background */}
              <div
                className={cn(
                  'absolute inset-1 rounded-lg transition-all duration-200',
                  active
                    ? 'bg-primary/[0.08]'
                    : 'bg-transparent group-hover:bg-white/[0.04]'
                )}
              />

              <Icon className="h-5 w-5 relative z-10 transition-transform duration-200 group-hover:scale-105" />
              <span className={cn(
                'text-[10px] font-medium mt-1 relative z-10 transition-colors duration-200',
                active ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground/70'
              )}>
                {label}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom separator */}
      <div className="w-8 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

      {/* User section */}
      <div className="flex flex-col items-center gap-2 py-4">
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 rounded-xl hover:bg-white/[0.04]"
          onClick={() => setIsSettingsOpen(true)}
        >
          <Avatar className="h-8 w-8">
            {user?.app_metadata?.provider === 'google' && user?.user_metadata?.avatar_url ? (
              <AvatarImage
                src={user.user_metadata.avatar_url}
                alt={user.user_metadata.full_name || user.email || 'User'}
              />
            ) : null}
            <AvatarFallback className="bg-primary/10 text-primary text-xs">
              <User className="h-4 w-4" />
            </AvatarFallback>
          </Avatar>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-lg text-muted-foreground hover:text-foreground hover:bg-white/[0.04]"
          onClick={() => setIsSettingsOpen(true)}
        >
          <Settings className="h-4 w-4" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 rounded-lg text-muted-foreground hover:text-red-400 hover:bg-red-400/[0.06]"
          onClick={() => signOut()}
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentFullName={user?.user_metadata?.full_name || null}
      />
    </div>
  );
};
