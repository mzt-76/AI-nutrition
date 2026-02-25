
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { Message } from '@/types/database.types';
import { ChatLayout } from '@/components/chat/ChatLayout';
import { useConversationManagement } from '@/components/chat/ConversationManagement';
import { useMessageHandling } from '@/components/chat/MessageHandling';
import { useIsMobile } from '@/hooks/use-mobile';

export const Chat = () => {
  const { user, session } = useAuth();
  const { toast } = useToast();
  const isMobile = useIsMobile();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(isMobile);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newConversationId, setNewConversationId] = useState<string | null>(null);
  
  // Update sidebar collapsed state when mobile status changes
  useEffect(() => {
    setIsSidebarCollapsed(isMobile);
  }, [isMobile]);
  
  // Ref to track if component is mounted
  const isMounted = useRef(true);
  
  useEffect(() => {
    return () => {
      // When component unmounts
      isMounted.current = false;
    };
  }, []);
  
  // Use our extracted conversation management hook
  const {
    conversations,
    selectedConversation,
    setSelectedConversation,
    setConversations,
    loadConversations,
    handleNewChat,
    handleSelectConversation
  } = useConversationManagement({ user, isMounted });
  
  // Use our extracted message handling hook
  const { 
    handleSendMessage,
    loadMessages
  } = useMessageHandling({
    setNewConversationId,
    user,
    session, // Pass the session from useAuth
    selectedConversation,
    setMessages,
    setLoading,
    setError,
    isMounted,
    setSelectedConversation,
    setConversations,
    loadConversations
  });

  // Load messages when a conversation is selected
  useEffect(() => {
    if (selectedConversation) {
      loadMessages(selectedConversation);
    } else {
      setMessages([]);
    }
  }, [selectedConversation, loadMessages]);

  // No longer needed since we're simplifying the UI to just disable the send button during loading

  return (
    <ChatLayout
      conversations={conversations}
      messages={messages}
      selectedConversation={selectedConversation}
      loading={loading}
      error={error}
      isSidebarCollapsed={isSidebarCollapsed}
      onSendMessage={handleSendMessage}
      onNewChat={handleNewChat}
      onSelectConversation={handleSelectConversation}
      onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      newConversationId={newConversationId}
    />
  );
};

export default Chat;
