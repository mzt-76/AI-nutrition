
import { useCallback, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Message, FileAttachment } from '@/types/database.types';
import { UIComponentBlock, SemanticZone } from '@/types/generative-ui.types';
import { sendMessage, fetchMessages } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { Session, User } from '@supabase/supabase-js';
import { Conversation } from '@/types/database.types';
import { logger } from '@/lib/logger';

interface MessageHandlingProps {
  user: User | null;
  session: Session | null;
  selectedConversation: Conversation | null;
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  isMounted: React.MutableRefObject<boolean>;
  setSelectedConversation: (conversation: Conversation | null) => void;
  setConversations: React.Dispatch<React.SetStateAction<Conversation[]>>;
  loadConversations: () => Promise<Conversation[]>;
  setNewConversationId?: (id: string | null) => void;
}

export const useMessageHandling = ({
  user,
  session,
  selectedConversation,
  setMessages,
  setLoading,
  setError,
  isMounted,
  setSelectedConversation,
  setConversations,
  loadConversations,
  setNewConversationId,
}: MessageHandlingProps) => {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const abortControllerRef = useRef<AbortController | null>(null);
  const newConvTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (newConvTimerRef.current) clearTimeout(newConvTimerRef.current);
    };
  }, []);

  const handleStopResponse = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
  }, [setLoading]);

  const finalizeNewConversation = useCallback(async (sessionId: string, aiMessageId: string) => {
    const newConversations = await loadConversations();
    const newConversation = newConversations.find(
      (conv) => conv.session_id === sessionId
    );

    if (newConversation) {
      setMessages((prev) => {
        const updated = [...prev];
        const idx = updated.findIndex(msg => msg.id === aiMessageId);
        if (idx !== -1) {
          updated[idx] = { ...updated[idx], session_id: sessionId };
        }
        return updated;
      });

      setSelectedConversation(newConversation);

      if (setNewConversationId) {
        setNewConversationId(sessionId);
        const timerId = setTimeout(() => {
          if (isMounted.current && setNewConversationId) {
            setNewConversationId(null);
          }
        }, 300);
        newConvTimerRef.current = timerId;
      }
    }
  }, [loadConversations, setMessages, setSelectedConversation, setNewConversationId, isMounted]);

  const handleSendMessage = async (content: string, files?: FileAttachment[]) => {
    if (!user) return;

    setError(null);
    setLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const currentSessionId = selectedConversation?.session_id || '';

      const userMessage: Message = {
        id: `temp-${Date.now()}-user`,
        session_id: currentSessionId,
        computed_session_user_id: '',
        message: {
          type: 'human',
          content,
          files: files,
        },
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMessage]);

      const isNewConversation = !currentSessionId;
      const aiMessageId = `temp-${Date.now()}-ai`;
      let aiMessageCreated = false;
      let completionReceived = false;
      const accumulatedComponents: UIComponentBlock[] = [];

      const response = await sendMessage(
        content,
        user.id,
        currentSessionId,
        session?.access_token,
        files,
        (chunk) => {
          if (abortController.signal.aborted) return;
          if (!isMounted.current) return;

          if (chunk.text && chunk.text.trim() !== '') {
            if (!aiMessageCreated) {
              const aiMessage: Message = {
                id: aiMessageId,
                session_id: currentSessionId,
                computed_session_user_id: '',
                message: {
                  type: 'ai',
                  content: chunk.text,
                },
                created_at: new Date().toISOString(),
              };

              setMessages((prev) => [...prev, aiMessage]);
              aiMessageCreated = true;
            } else {
              setMessages((prev) => {
                const updatedMessages = [...prev];
                const aiMessageIndex = updatedMessages.findIndex(msg => msg.id === aiMessageId);

                if (aiMessageIndex !== -1) {
                  updatedMessages[aiMessageIndex] = {
                    ...updatedMessages[aiMessageIndex],
                    message: {
                      ...updatedMessages[aiMessageIndex].message,
                      content: chunk.text!,
                    },
                  };
                }

                return updatedMessages;
              });
            }
          }

          if (chunk.type === 'ui_component' && chunk.component) {
            accumulatedComponents.push({
              id: chunk.id || `${chunk.component}-${accumulatedComponents.length}`,
              component: chunk.component,
              props: chunk.props || {},
              zone: (chunk.zone as SemanticZone) || 'content',
            });
            setMessages((prev) => {
              const updated = [...prev];
              const idx = updated.findIndex(msg => msg.id === aiMessageId);
              if (idx !== -1) {
                updated[idx] = {
                  ...updated[idx],
                  message: {
                    ...updated[idx].message,
                    ui_components: [...accumulatedComponents],
                  },
                };
              }
              return updated;
            });
          }

          if (chunk.complete === true && !completionReceived) {
            completionReceived = true;

            if (chunk.session_id && chunk.session_id !== currentSessionId) {
              setMessages((prev) => {
                const updatedMessages = [...prev];
                const aiMessageIndex = updatedMessages.findIndex(msg => msg.id === aiMessageId);

                if (aiMessageIndex !== -1) {
                  updatedMessages[aiMessageIndex] = {
                    ...updatedMessages[aiMessageIndex],
                    session_id: chunk.session_id,
                  };
                }

                return updatedMessages;
              });
            }

            if (isNewConversation && chunk.session_id) {
              finalizeNewConversation(chunk.session_id, aiMessageId);
            }

            setLoading(false);
          }
        },
        abortController.signal
      );

      if (isMounted.current && !completionReceived) {
        if (!aiMessageCreated) {
          const newAiMessage: Message = {
            id: aiMessageId,
            session_id: response.session_id || currentSessionId,
            computed_session_user_id: '',
            message: {
              type: 'ai',
              content: response.output,
            },
            created_at: new Date().toISOString(),
          };

          setMessages((prev) => [...prev, newAiMessage]);
        } else {
          setTimeout(() => {
            if (isMounted.current && !completionReceived) {
              setMessages((prev) => {
                const updatedMessages = [...prev];
                const aiMessageIndex = updatedMessages.findIndex(msg => msg.id === aiMessageId);

                if (aiMessageIndex !== -1 && response.output) {
                  updatedMessages[aiMessageIndex] = {
                    ...updatedMessages[aiMessageIndex],
                    message: {
                      ...updatedMessages[aiMessageIndex].message,
                      content: response.output,
                    },
                  };
                }

                return updatedMessages;
              });
            }
          }, 100);
        }

        if (isNewConversation && response.session_id) {
          await finalizeNewConversation(response.session_id, aiMessageId);
        }

        setLoading(false);
      }

      if (!isNewConversation) {
        loadConversations();
      }

    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }

      logger.error('Error in chat flow:', err);
      if (isMounted.current) {
        const errorMessage = err instanceof Error ? err.message : 'Impossible de traiter votre message. Veuillez réessayer.';

        const aiErrorMessage: Message = {
          id: `error-${Date.now()}`,
          session_id: selectedConversation?.session_id || '',
          computed_session_user_id: '',
          message: {
            type: 'ai',
            content: `Error: ${errorMessage}`,
          },
          created_at: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, aiErrorMessage]);

        setError(errorMessage);
        toast({
          title: 'Erreur',
          description: 'Une erreur est survenue. Veuillez réessayer.',
          variant: 'destructive',
        });
      }
    } finally {
      abortControllerRef.current = null;
      if (isMounted.current) {
        setLoading(false);
      }
    }
  };

  // Load messages for the selected conversation
  const loadMessages = useCallback(async (conversation: Conversation) => {
    if (!user) return;
    
    try {
      // Don't set loading state when switching between existing conversations
      // This prevents the loading indicator from flashing
      
      // This just fetches messages from the database, it doesn't call the webhook API
      const data = await fetchMessages(conversation.session_id, user.id);
      if (isMounted.current) {
        setMessages(data);
        // Write to React Query cache so tab switches restore instantly
        queryClient.setQueryData(['messages', conversation.session_id], data);
      }
    } catch (err) {
      logger.error('Error loading messages:', err);
      if (isMounted.current) {
        toast({
          title: 'Erreur de chargement',
          description: 'Impossible de charger les messages. Veuillez réessayer.',
          variant: 'destructive',
        });
      }
    }
    // No need to set loading to false since we never set it to true
  }, [user, setMessages, toast, isMounted, queryClient]);

  return {
    handleSendMessage,
    handleStopResponse,
    loadMessages
  };
};
