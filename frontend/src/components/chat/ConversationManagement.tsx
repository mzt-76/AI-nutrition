
import { useState, useEffect, useCallback } from 'react';
import { fetchConversations } from '@/lib/api';
import { Conversation } from '@/types/database.types';
import { useToast } from '@/hooks/use-toast';

interface ConversationManagementProps {
  user: any;
  isMounted: React.MutableRefObject<boolean>;
}

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
    setSelectedConversation(null);
  };

  const handleSelectConversation = (conversation: Conversation) => {
    setSelectedConversation(conversation);
  };

  // Initial load of conversations
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

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
