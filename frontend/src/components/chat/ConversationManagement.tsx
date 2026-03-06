
import { useState, useEffect, useCallback } from 'react';
import { fetchConversations } from '@/lib/api';
import { Conversation } from '@/types/database.types';
import { useToast } from '@/hooks/use-toast';

interface ConversationManagementProps {
  user: any;
  isMounted: React.MutableRefObject<boolean>;
}

const SESSION_KEY = 'active_conversation_id';

export const useConversationManagement = ({
  user,
  isMounted
}: ConversationManagementProps) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const { toast } = useToast();

  // Fetch user's conversations
  const loadConversations = useCallback(async () => {
    if (!user) return [];

    try {
      const data = await fetchConversations(user.id);
      if (isMounted.current) {
        setConversations(data);
      }
      return data;
    } catch (err) {
      console.error('Error loading conversations:', err);
      if (isMounted.current) {
        toast({
          title: 'Erreur de chargement',
          description: 'Impossible de charger vos conversations. Veuillez réessayer.',
          variant: 'destructive',
        });
      }
      return [];
    }
  }, [user, toast, isMounted]);

  const handleNewChat = () => {
    sessionStorage.removeItem(SESSION_KEY);
    setSelectedConversation(null);
  };

  const handleSelectConversation = (conversation: Conversation) => {
    sessionStorage.setItem(SESSION_KEY, conversation.session_id);
    setSelectedConversation(conversation);
  };

  // Persist selectedConversation session_id when it changes (e.g. after first message creates one)
  useEffect(() => {
    if (selectedConversation) {
      sessionStorage.setItem(SESSION_KEY, selectedConversation.session_id);
    }
  }, [selectedConversation]);

  // Initial load: fetch conversations and restore active conversation from sessionStorage
  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    const init = async () => {
      try {
        const data = await fetchConversations(user.id);
        if (cancelled) return;
        setConversations(data);

        const savedId = sessionStorage.getItem(SESSION_KEY);
        if (savedId) {
          const match = data.find((c: Conversation) => c.session_id === savedId);
          if (match) {
            setSelectedConversation(match);
          }
        }
      } catch (err) {
        console.error('Error loading conversations:', err);
        if (!cancelled) {
          toast({
            title: 'Erreur de chargement',
            description: 'Impossible de charger vos conversations. Veuillez réessayer.',
            variant: 'destructive',
          });
        }
      }
    };
    init();
    return () => { cancelled = true; };
  }, [user, toast]);

  return {
    conversations,
    selectedConversation,
    setSelectedConversation,
    setConversations,
    loadConversations,
    handleNewChat,
    handleSelectConversation
  };
};
