
import { useState, useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';
import { Message, Conversation } from '@/types/database.types';
import { ChatLayout } from '@/components/chat/ChatLayout';
import { useConversationManagement } from '@/components/chat/ConversationManagement';
import { useMessageHandling } from '@/components/chat/MessageHandling';
import { useIsMobile } from '@/hooks/use-mobile';
import { safeGetItem, safeSetItem, safeRemoveItem } from '@/lib/storage';
import { SESSION_CONV_KEY, SESSION_MESSAGES_KEY, SESSION_STREAMING_KEY } from '@/lib/constants';

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
  const isMobile = useIsMobile();
  const queryClient = useQueryClient();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(isMobile);
  const [messages, setMessages] = useState<Message[]>(() => {
    const savedConv = safeGetItem(sessionStorage, SESSION_CONV_KEY);
    const savedMsgs = safeGetItem(sessionStorage, SESSION_MESSAGES_KEY);
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

  // Refs to capture latest loading/conversation state at unmount time
  const loadingRef = useRef(loading);
  const selectedConvRef = useRef<Conversation | null>(null);
  useEffect(() => { loadingRef.current = loading; }, [loading]);

  useEffect(() => {
    return () => {
      isMounted.current = false;
      // If we unmount while streaming is in progress, persist a flag so the next
      // Chat instance knows to re-fetch once the backend finishes saving.
      if (loadingRef.current && selectedConvRef.current?.session_id) {
        safeSetItem(sessionStorage, SESSION_STREAMING_KEY, selectedConvRef.current.session_id);
      }
    };
  }, []);

  // Use our extracted conversation management hook
  const {
    conversations,
    selectedConversation,
    setSelectedConversation,
    loadConversations,
    handleNewChat,
    handleSelectConversation,
    handleDeleteConversation,
  } = useConversationManagement({ user });

  // Keep selectedConvRef in sync for unmount cleanup
  useEffect(() => { selectedConvRef.current = selectedConversation; }, [selectedConversation]);

  // Persist messages to sessionStorage — also during loading so partial responses
  // survive a tab switch and are visible immediately on return.
  useEffect(() => {
    if (messages.length > 0 && selectedConversation) {
      safeSetItem(sessionStorage, SESSION_MESSAGES_KEY, JSON.stringify(messages));
    }
  }, [messages, selectedConversation]);

  // Wrap handleNewChat to also clear cached messages
  const wrappedHandleNewChat = useCallback(() => {
    safeRemoveItem(sessionStorage, SESSION_MESSAGES_KEY);
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
      void loadMessages(selectedConversation);

      // If we navigated away while streaming was in progress for this conversation,
      // schedule re-fetches so the completed AI response appears once the backend
      // finishes saving it to the database.
      const streamingSession = safeGetItem(sessionStorage, SESSION_STREAMING_KEY);
      if (streamingSession === selectedConversation.session_id) {
        safeRemoveItem(sessionStorage, SESSION_STREAMING_KEY);
        const t1 = setTimeout(() => { if (isMounted.current) void loadMessages(selectedConversation); }, 3_000);
        const t2 = setTimeout(() => { if (isMounted.current) void loadMessages(selectedConversation); }, 10_000);
        const t3 = setTimeout(() => { if (isMounted.current) void loadMessages(selectedConversation); }, 30_000);
        return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
      }
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
