
import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchConversations, deleteConversation } from '@/lib/api';
import { Conversation } from '@/types/database.types';
import { useToast } from '@/hooks/use-toast';
import type { User } from '@supabase/supabase-js';
import { logger } from '@/lib/logger';
import { safeGetItem, safeSetItem, safeRemoveItem } from '@/lib/storage';
import { SESSION_KEY, SESSION_CONV_KEY } from '@/lib/constants';

interface ConversationManagementProps {
  user: User | null;
}

export const useConversationManagement = ({
  user,
}: ConversationManagementProps) => {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // React Query: conversations survive component unmount/remount (cached 30s)
  const { data: conversations = [], error: queryError } = useQuery({
    queryKey: ['conversations', user?.id],
    queryFn: () => fetchConversations(user!.id),
    enabled: !!user,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (queryError) {
      logger.error('Error loading conversations:', queryError);
      toast({
        title: 'Erreur de chargement',
        description: 'Impossible de charger vos conversations. Veuillez réessayer.',
        variant: 'destructive',
      });
    }
  }, [queryError, toast]);

  // Synchronous restore: read full conversation object from sessionStorage (no cache dependency)
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(() => {
    const savedJson = safeGetItem(sessionStorage, SESSION_CONV_KEY);
    if (savedJson) {
      try { return JSON.parse(savedJson); } catch { /* fall through */ }
    }
    return null;
  });

  // Fallback: if cache was empty on init but conversations arrive from network, restore
  useEffect(() => {
    if (selectedConversation || conversations.length === 0) return;
    const savedId = safeGetItem(sessionStorage, SESSION_KEY);
    if (savedId) {
      const match = conversations.find(c => c.session_id === savedId);
      if (match) setSelectedConversation(match);
    }
  }, [conversations, selectedConversation]);

  // Persist session_id + full object to sessionStorage
  useEffect(() => {
    if (selectedConversation) {
      safeSetItem(sessionStorage, SESSION_KEY, selectedConversation.session_id);
      safeSetItem(sessionStorage, SESSION_CONV_KEY, JSON.stringify(selectedConversation));
    }
  }, [selectedConversation]);

  // Force-refresh conversations via React Query (used by MessageHandling after sending)
  const loadConversations = useCallback(async (): Promise<Conversation[]> => {
    if (!user) return [];
    try {
      return await queryClient.fetchQuery({
        queryKey: ['conversations', user.id],
        queryFn: () => fetchConversations(user.id),
        staleTime: 0,
      });
    } catch (err) {
      logger.error('Error loading conversations:', err);
      return [];
    }
  }, [user, queryClient]);

  // Update React Query cache directly (same API as useState setter)
  const setConversations = useCallback(
    (updater: Conversation[] | ((prev: Conversation[]) => Conversation[])) => {
      queryClient.setQueryData<Conversation[]>(
        ['conversations', user?.id],
        typeof updater === 'function' ? (old) => updater(old ?? []) : updater,
      );
    },
    [user?.id, queryClient],
  );

  const handleNewChat = useCallback(() => {
    safeRemoveItem(sessionStorage, SESSION_KEY);
    safeRemoveItem(sessionStorage, SESSION_CONV_KEY);
    setSelectedConversation(null);
  }, [setSelectedConversation]);

  const handleSelectConversation = (conversation: Conversation) => {
    safeSetItem(sessionStorage, SESSION_KEY, conversation.session_id);
    safeSetItem(sessionStorage, SESSION_CONV_KEY, JSON.stringify(conversation));
    setSelectedConversation(conversation);
  };

  const handleDeleteConversation = useCallback(async (sessionId: string) => {
    try {
      await deleteConversation(sessionId);
      queryClient.invalidateQueries({ queryKey: ['conversations', user?.id] });
      if (selectedConversation?.session_id === sessionId) {
        handleNewChat();
      }
    } catch (err) {
      logger.error('Error deleting conversation:', err);
      toast({
        title: 'Erreur',
        description: 'Impossible de supprimer la conversation.',
        variant: 'destructive',
      });
    }
  }, [user?.id, queryClient, selectedConversation, handleNewChat, toast]);

  return {
    conversations,
    selectedConversation,
    setSelectedConversation,
    setConversations,
    loadConversations,
    handleNewChat,
    handleSelectConversation,
    handleDeleteConversation,
  };
};
