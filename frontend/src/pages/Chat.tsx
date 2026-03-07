
import { useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { Message } from '@/types/database.types';
import { ChatLayout } from '@/components/chat/ChatLayout';
import { useConversationManagement } from '@/components/chat/ConversationManagement';
import { useMessageHandling } from '@/components/chat/MessageHandling';
import { useIsMobile } from '@/hooks/use-mobile';

const SESSION_MESSAGES_KEY = 'active_messages';
const SESSION_CONV_KEY = 'active_conversation';

const messageSchema = z.array(z.object({
  id: z.string(),
  session_id: z.string(),
  computed_session_user_id: z.string(),
  message: z.object({
    type: z.string(),
    content: z.string(),
  }).passthrough(),
  created_at: z.string(),
}).passthrough());

export const Chat = () => {
  const { user, session } = useAuth();
  const { toast } = useToast();
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(isMobile);
  const [messages, setMessages] = useState<Message[]>(() => {
    const savedConv = sessionStorage.getItem(SESSION_CONV_KEY);
    const savedMsgs = sessionStorage.getItem(SESSION_MESSAGES_KEY);
    if (savedConv && savedMsgs) {
      try {
        const conv = JSON.parse(savedConv);
        const msgs = messageSchema.parse(JSON.parse(savedMsgs));
        if (msgs.length > 0 && msgs[0].session_id === conv.session_id) {
          return msgs as Message[];
        }
      } catch { /* fall through */ }
    }
    return [];
  });
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
    handleSelectConversation,
    handleDeleteConversation,
  } = useConversationManagement({ user });

  // Persist messages to sessionStorage when loading completes
  useEffect(() => {
    if (messages.length > 0 && !loading && selectedConversation) {
      sessionStorage.setItem(SESSION_MESSAGES_KEY, JSON.stringify(messages));
    }
  }, [messages, loading, selectedConversation]);

  // Wrap handleNewChat to also clear cached messages
  const wrappedHandleNewChat = useCallback(() => {
    sessionStorage.removeItem(SESSION_MESSAGES_KEY);
    handleNewChat();
  }, [handleNewChat]);

  // Use our extracted message handling hook
  const {
    handleSendMessage,
    handleStopResponse,
    loadMessages
  } = useMessageHandling({
    setNewConversationId,
    user,
    session,
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
      // Seed from React Query cache for instant display on tab switch
      const cached = queryClient.getQueryData<Message[]>(
        ['messages', selectedConversation.session_id]
      );
      if (cached?.length) {
        setMessages(cached);
      }
      // Fetch fresh data (updates messages + writes to cache)
      loadMessages(selectedConversation);
    } else {
      setMessages([]);
    }
  }, [selectedConversation, loadMessages, queryClient]);

  return (
    <ChatLayout
      conversations={conversations}
      messages={messages}
      selectedConversation={selectedConversation}
      loading={loading}
      error={error}
      isSidebarCollapsed={isSidebarCollapsed}
      onSendMessage={handleSendMessage}
      onStopResponse={handleStopResponse}
      onNewChat={wrappedHandleNewChat}
      onSelectConversation={handleSelectConversation}
      onDeleteConversation={handleDeleteConversation}
      onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      newConversationId={newConversationId}
    />
  );
};

export default Chat;
