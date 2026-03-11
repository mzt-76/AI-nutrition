
import { useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabase';
import { useToast } from '@/components/ui/use-toast';
import { Conversation, Message } from '@/types/database.types';
import { fetchMessages } from '@/lib/api';
import { logger } from '@/lib/logger';
import { safeWriteClipboard } from '@/lib/clipboard';

export interface ConversationDetails extends Conversation {
  messages?: Message[];
}

type SortOrder = 'asc' | 'desc';

export const useConversations = () => {
  const [conversations, setConversations] = useState<ConversationDetails[]>([]);
  const [filteredConversations, setFilteredConversations] = useState<ConversationDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedConversation, setSelectedConversation] = useState<ConversationDetails | null>(null);
  const [openDialog, setOpenDialog] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const { toast } = useToast();

  const fetchConversations = useCallback(async () => {
    try {
      setLoading(true);
      const { data, error } = await supabase
        .from('conversations')
        .select('*')
        .order('created_at', { ascending: sortOrder === 'asc' });

      if (error) throw error;
      setConversations(data || []);
      setFilteredConversations(data || []);
    } catch (error) {
      logger.error('Error fetching conversations:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les conversations',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [sortOrder, toast]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Filter conversations based on search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredConversations(conversations);
      return;
    }

    const query = searchQuery.toLowerCase().trim();
    const filtered = conversations.filter(
      (conversation) =>
        (conversation.title && conversation.title.toLowerCase().includes(query)) ||
        conversation.user_id.toLowerCase().includes(query) ||
        conversation.session_id.toLowerCase().includes(query)
    );
    setFilteredConversations(filtered);
  }, [searchQuery, conversations]);

  const toggleSortOrder = () => {
    setSortOrder(prevOrder => prevOrder === 'desc' ? 'asc' : 'desc');
  };

  const copyToClipboard = async (text: string) => {
    await safeWriteClipboard(text);
    toast({
      title: 'Copié',
      description: 'ID copié dans le presse-papiers',
    });
  };

  const viewConversation = async (conversation: Conversation) => {
    try {
      // Reset any previous state
      setLoadingMessages(true);
      
      // Clone the conversation object to prevent reference issues
      const conversationClone = { ...conversation };
      setSelectedConversation(conversationClone);
      setOpenDialog(true);
      
      const messages = await fetchMessages(conversation.session_id);
      
      // Use the functional update to ensure we're working with the most current state
      setSelectedConversation((prev) => {
        if (!prev) return null;
        return { ...prev, messages };
      });
    } catch (error) {
      logger.error('Error fetching messages:', error);
      toast({
        title: 'Erreur',
        description: 'Impossible de charger les messages',
        variant: 'destructive',
      });
    } finally {
      // Always ensure loading state is reset regardless of success/failure
      setLoadingMessages(false);
    }
  };

  // Handle dialog open/close state
  const handleDialogChange = (open: boolean) => {
    setOpenDialog(open);
    if (!open) {
      // Only reset selected conversation when dialog is explicitly closed
      setSelectedConversation(null);
    }
  };

  return {
    conversations,
    filteredConversations,
    loading,
    selectedConversation,
    openDialog,
    loadingMessages,
    searchQuery,
    setSearchQuery,
    copyToClipboard,
    viewConversation,
    handleDialogChange,
    sortOrder,
    toggleSortOrder,
  };
};
