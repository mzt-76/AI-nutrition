
import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Plus,
  Search,
  LogOut,
  ChevronLeft,
  User,
  Menu,
  Settings,
  MessageSquare,
  Users,
  Salad,
  Activity,
  BookOpen,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useAdmin } from '@/hooks/useAdmin';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Conversation } from '@/types/database.types';
import { cn } from '@/lib/utils';
import { Link, useLocation } from 'react-router-dom';
import { SettingsModal } from './SettingsModal';
import { TypewriterText } from '@/components/ui/TypewriterText';

interface ChatSidebarProps {
  conversations: Conversation[];
  isCollapsed: boolean;
  onNewChat: () => void;
  onSelectConversation: (conversation: Conversation) => void;
  selectedConversationId: string | null;
  onToggleSidebar: () => void;
  newConversationId?: string | null;
}

export const ChatSidebar = ({
  conversations,
  isCollapsed,
  onNewChat,
  onSelectConversation,
  selectedConversationId,
  onToggleSidebar,
  newConversationId,
}: ChatSidebarProps) => {
  const { user, signOut } = useAuth();
  const { isAdmin } = useAdmin();
  const [search, setSearch] = useState('');
  const [filteredConversations, setFilteredConversations] = useState<Conversation[]>(conversations);
  const location = useLocation();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    if (!search.trim()) {
      setFilteredConversations(conversations);
    } else {
      const filtered = conversations.filter(
        (conversation) =>
          conversation.title?.toLowerCase().includes(search.toLowerCase())
      );
      setFilteredConversations(filtered);
    }
  }, [search, conversations]);

  if (isCollapsed) {
    return (
      <div className="glass-effect h-full w-16 border-r flex flex-col items-center py-4">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar} className="mb-6">
          <Menu className="h-5 w-5" />
        </Button>
        {isAdmin && (
          <Button
            variant="outline"
            size="icon"
            className="mb-2 text-primary border-primary"
            asChild
          >
            <Link to="/admin">
              <Users className="h-5 w-5" />
            </Link>
          </Button>
        )}
        <Button variant="outline" size="icon" onClick={onNewChat} className="mb-4">
          <Plus className="h-5 w-5" />
        </Button>
        <Button
          variant={location.pathname.startsWith('/tracking') ? 'secondary' : 'ghost'}
          size="icon"
          className="mb-2"
          asChild
        >
          <Link to="/tracking">
            <Activity className="h-5 w-5" />
          </Link>
        </Button>
        <Button
          variant={location.pathname === '/plans' ? 'secondary' : 'ghost'}
          size="icon"
          className="mb-2"
          asChild
        >
          <Link to="/plans">
            <BookOpen className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1" />
        <Button variant="ghost" size="icon" onClick={() => signOut()}>
          <LogOut className="h-5 w-5" />
        </Button>
      </div>
    );
  }

  return (
    <div className="glass-effect h-full w-72 border-r flex flex-col">
      <div className="flex items-center justify-between p-4">
        <div className="text-sidebar-foreground font-semibold flex items-center">
          <Salad className="mr-2 h-5 w-5 text-primary" />
          Nutritionniste IA
        </div>
        <Button variant="ghost" size="icon" onClick={onToggleSidebar}>
          <ChevronLeft className="h-5 w-5" />
        </Button>
      </div>

      <Separator />

      <div className="px-4 pt-4">
        {isAdmin && (
          <div className="mb-3">
            <Button
              variant="outline"
              className="w-full justify-start gradient-green text-white hover:opacity-90"
              asChild
            >
              <Link to="/admin">
                <Users className="mr-2 h-5 w-5" />
                Tableau de bord admin
              </Link>
            </Button>
          </div>
        )}

        <Button
          onClick={onNewChat}
          className="w-full justify-start gradient-green text-white hover:opacity-90"
        >
          <Plus className="mr-2 h-5 w-5" />
          Nouvelle conversation
        </Button>

        <div className="mt-3 space-y-1">
          <Button
            variant={location.pathname.startsWith('/tracking') ? 'secondary' : 'ghost'}
            className="w-full justify-start"
            asChild
          >
            <Link to="/tracking">
              <Activity className="mr-2 h-5 w-5" />
              Suivi du Jour
            </Link>
          </Button>
          <Button
            variant={location.pathname === '/plans' ? 'secondary' : 'ghost'}
            className="w-full justify-start"
            asChild
          >
            <Link to="/plans">
              <BookOpen className="mr-2 h-5 w-5" />
              Mes Plans
            </Link>
          </Button>
        </div>
      </div>

      <div className="px-4 pt-4 pb-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Rechercher..."
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <ScrollArea className="flex-1 px-2">
        <div className="space-y-1 p-2">
          {filteredConversations.length > 0 ? (
            filteredConversations.map((conversation) => (
              <Button
                key={conversation.session_id}
                variant="ghost"
                size="sm"
                className={cn(
                  "w-full justify-start font-normal text-sm",
                  selectedConversationId === conversation.session_id && "bg-sidebar-accent text-sidebar-accent-foreground"
                )}
                onClick={() => onSelectConversation(conversation)}
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                {newConversationId === conversation.session_id ? (
                  <TypewriterText
                    text={conversation.title || ''}
                    duration={300}
                    className="truncate"
                  />
                ) : (
                  <span className="truncate">{conversation.title}</span>
                )}
              </Button>
            ))
          ) : (
            <div className="py-4 text-center text-sm text-muted-foreground">
              {search ? 'Aucune conversation trouvée' : 'Aucune conversation'}
            </div>
          )}
        </div>
      </ScrollArea>

      <Separator />

      <div className="p-4">
        <div className="flex items-center gap-2">
          <Avatar className="h-8 w-8">
            {user?.app_metadata?.provider === 'google' && user?.user_metadata?.avatar_url ? (
              <AvatarImage src={user.user_metadata.avatar_url} alt={user.user_metadata.full_name || user.email || 'User'} />
            ) : null}
            <AvatarFallback>
              <User className="h-4 w-4" />
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 truncate">
            <div className="text-sm font-medium truncate">
              {user?.user_metadata?.full_name || user?.email || 'Utilisateur'}
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsSettingsOpen(true)}
          >
            <Settings className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => signOut()}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentFullName={user?.user_metadata?.full_name || null}
      />
    </div>
  );
};
