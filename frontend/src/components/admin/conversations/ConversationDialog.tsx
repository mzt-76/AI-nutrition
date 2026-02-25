
import React from 'react';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Message } from '@/types/database.types';
import { Conversation } from '@/types/database.types';

interface ConversationDetails extends Conversation {
  messages?: Message[];
}

interface ConversationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedConversation: ConversationDetails | null;
  loadingMessages: boolean;
}

export const ConversationDialog = ({
  open,
  onOpenChange,
  selectedConversation,
  loadingMessages,
}: ConversationDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto bg-background">
        <DialogHeader>
          <DialogTitle className="text-foreground">
            {selectedConversation?.title || 'Conversation Details'}
          </DialogTitle>
        </DialogHeader>
        
        {loadingMessages ? (
          <div className="py-8 flex justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        ) : (
          <div className="space-y-6 mt-4">
            {selectedConversation?.messages?.length ? (
              selectedConversation.messages.map((message, index) => (
                <div 
                  key={message.id || index} 
                  className={`flex items-start gap-3 ${
                    message.message.type === 'human' 
                      ? 'justify-end' 
                      : 'justify-start'
                  }`}
                >
                  <div 
                    className={`rounded-lg px-4 py-3 max-w-[80%] ${
                      message.message.type === 'human' 
                        ? 'bg-gray-700 text-gray-50' 
                        : 'bg-gray-800 text-gray-50'
                    }`}
                  >
                    <div className="text-xs text-gray-400 mb-1">
                      {message.message.type === 'human' ? 'User' : 'AI'}
                    </div>
                    <div className="whitespace-pre-wrap">
                      {message.message.content}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-gray-500">
                No messages found in this conversation
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
