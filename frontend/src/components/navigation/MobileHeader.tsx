import React from 'react';
import { Menu, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

interface MobileHeaderProps {
  title: string;
  onMenuClick?: () => void;
  onProfileClick?: () => void;
  showMenu?: boolean;
}

export const MobileHeader: React.FC<MobileHeaderProps> = ({
  title,
  onMenuClick,
  onProfileClick,
  showMenu = false,
}) => {
  return (
    <div className="flex items-center h-14 border-b border-border/50 px-4 glass-effect shrink-0">
      {showMenu && onMenuClick ? (
        <Button variant="ghost" size="icon" className="mr-2" onClick={onMenuClick}>
          <Menu className="h-5 w-5" />
          <span className="sr-only">Ouvrir le menu</span>
        </Button>
      ) : (
        <div className="w-10" />
      )}
      <div className="flex-1 text-center font-semibold truncate" title={title}>{title}</div>
      {onProfileClick ? (
        <Button variant="ghost" size="icon" className="ml-2" onClick={onProfileClick}>
          <Avatar className="h-7 w-7">
            <AvatarFallback className="bg-primary/20 text-primary text-xs">
              <User className="h-4 w-4" />
            </AvatarFallback>
          </Avatar>
        </Button>
      ) : (
        <div className="w-10" />
      )}
    </div>
  );
};
