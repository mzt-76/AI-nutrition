
import React, { useState } from 'react';
import { MessageList } from '@/components/chat/MessageList';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatSidebar } from '@/components/sidebar/ChatSidebar';
import { AlertCircle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Message, Conversation } from '@/types/database.types';
import { useIsMobile } from '@/hooks/use-mobile';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { MobileHeader } from '@/components/navigation/MobileHeader';
import { SettingsModal } from '@/components/sidebar/SettingsModal';
import { useAuth } from '@/hooks/useAuth';

interface ChatLayoutProps {
  conversations: Conversation[];
  messages: Message[];
  selectedConversation: Conversation | null;
  loading: boolean;
  error: string | null;
  isSidebarCollapsed: boolean;
  onSendMessage: (message: string) => void;
  onNewChat: () => void;
  onSelectConversation: (conversation: Conversation) => void;
  onToggleSidebar: () => void;
  newConversationId?: string | null;
}

export const ChatLayout: React.FC<ChatLayoutProps> = ({
  conversations,
  messages,
  selectedConversation,
  loading,
  error,
  isSidebarCollapsed,
  onSendMessage,
  onNewChat,
  onSelectConversation,
  onToggleSidebar,
  newConversationId
}) => {
  const isMobile = useIsMobile();
  const { user } = useAuth();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isGeneratingResponse, setIsGeneratingResponse] = useState(false);

  React.useEffect(() => {
    if (loading && messages.length > 0) {
      setIsGeneratingResponse(true);
    } else {
      setIsGeneratingResponse(false);
    }
  }, [loading, messages.length]);

  const handleSelectConversation = (conversation: Conversation) => {
    onSelectConversation(conversation);
    if (isMobile) {
      setSheetOpen(false);
    }
  };

  const handleNewChat = () => {
    onNewChat();
    if (isMobile) {
      setSheetOpen(false);
    }
  };

  const handleToggleSidebar = () => {
    if (isMobile) {
      setSheetOpen(false);
    } else {
      onToggleSidebar();
    }
  };

  const renderSidebar = () => (
    <ChatSidebar
      conversations={conversations}
      isCollapsed={isMobile ? false : isSidebarCollapsed}
      onNewChat={handleNewChat}
      onSelectConversation={handleSelectConversation}
      selectedConversationId={selectedConversation?.session_id || null}
      onToggleSidebar={handleToggleSidebar}
      newConversationId={newConversationId}
    />
  );

  const renderChatContent = () => (
    <div className="flex-1 flex flex-col overflow-hidden w-full">
      <main className="flex-1 flex flex-col overflow-hidden">
        {error && (
          <Alert variant="destructive" className="m-4">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Erreur</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="flex-1 overflow-hidden relative">
          <MessageList
            messages={messages}
            isLoading={loading}
            isGeneratingResponse={isGeneratingResponse}
            onSuggestedQuestion={onSendMessage}
            onAction={onSendMessage}
          />
        </div>

        <div className="border-t border-border/50">
          <div className="p-4 max-w-4xl mx-auto w-full">
            <div className="glass-effect rounded-lg">
              <ChatInput
                onSendMessage={onSendMessage}
                isLoading={loading}
              />
            </div>
            <div className="mt-2 text-xs text-center text-muted-foreground">
              Les réponses sont générées par l'IA. L'assistant peut produire des informations inexactes.
            </div>
          </div>
        </div>
      </main>
    </div>
  );

  if (isMobile) {
    return (
      <div className="flex h-screen gradient-bg flex-col overflow-hidden pb-14">
        <MobileHeader
          title={selectedConversation?.title || "Nouvelle conversation"}
          showMenu
          onMenuClick={() => setSheetOpen(true)}
          onProfileClick={() => setIsSettingsOpen(true)}
        />
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetContent side="left" className="p-0 w-[280px]" showCloseButton={false}>
            {renderSidebar()}
          </SheetContent>
        </Sheet>
        {renderChatContent()}
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          currentFullName={user?.user_metadata?.full_name || null}
        />
      </div>
    );
  }

  return (
    <div className="flex h-screen gradient-bg overflow-hidden">
      {renderSidebar()}
      {renderChatContent()}
    </div>
  );
};
