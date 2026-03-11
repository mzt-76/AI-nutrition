
import React from 'react';
import { Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TableRow, TableCell } from '@/components/ui/table';
import { Conversation } from '@/types/database.types';
import { format, parseISO } from 'date-fns';
import { logger } from '@/lib/logger';

interface ConversationRowProps {
  conversation: Conversation;
  viewConversation: (conversation: Conversation) => void;
  copyToClipboard: (text: string) => void;
}

export const ConversationRow = ({
  conversation,
  viewConversation,
  copyToClipboard,
}: ConversationRowProps) => {
  // Parse the timestamp and format it with date-fns
  const formattedDate = React.useMemo(() => {
    try {
      return conversation.created_at
        ? format(parseISO(conversation.created_at), 'MMM d, yyyy h:mm a')
        : '—';
    } catch (error) {
      logger.error('Error formatting date:', error);
      return conversation.created_at ?? '—';
    }
  }, [conversation.created_at]);

  return (
    <TableRow key={conversation.session_id}>
      <TableCell width="25%" className="whitespace-nowrap">
        {formattedDate}
      </TableCell>
      <TableCell width="25%">
        <Button 
          variant="link" 
          className="p-0 h-auto text-blue-500 hover:text-blue-700 font-normal text-left truncate max-w-full"
          onClick={() => viewConversation(conversation)}
        >
          <span className="truncate block">{conversation.title || 'Conversation sans titre'}</span>
        </Button>
      </TableCell>
      <TableCell width="25%">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs truncate max-w-[150px]">{conversation.user_id}</span>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => copyToClipboard(conversation.user_id)}
            className="h-6 w-6 flex-shrink-0"
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>
      </TableCell>
      <TableCell width="25%">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs truncate max-w-[150px]">{conversation.session_id}</span>
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={() => copyToClipboard(conversation.session_id)}
            className="h-6 w-6 flex-shrink-0"
          >
            <Copy className="h-3 w-3" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
};
