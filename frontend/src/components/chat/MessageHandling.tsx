
import { useCallback, useRef } from 'react';
import { Message, FileAttachment } from '@/types/database.types';
import { UIComponentBlock, SemanticZone } from '@/types/generative-ui.types';
import { sendMessage, fetchMessages } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { Session } from '@supabase/supabase-js';

interface MessageHandlingProps {
  user: any;
  session: Session | null;
  selectedConversation: any;
  setMessages: (messages: Message[] | ((prev: Message[]) => Message[])) => void;
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  isMounted: React.MutableRefObject<boolean>;
  setSelectedConversation: (conversation: any) => void;
  setConversations: (conversations: any[] | ((prev: any[]) => any[])) => void;
  loadConversations: () => Promise<any[]>;
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

  const handleSendMessage = async (content: string, files?: FileAttachment[]) => {
    if (!user) return;
    
    setError(null);
    setLoading(true);
    
    try {
      // Get current session ID from selected conversation, if any
      const currentSessionId = selectedConversation?.session_id || '';
      
      // Create a temporary user message object for UI display only
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
      
      // Update UI with user message
      setMessages((prev) => [...prev, userMessage]);
      
      // Track if this is a new conversation
      const isNewConversation = !currentSessionId;
      
      // Create an ID for the AI message that will be created
      const aiMessageId = `temp-${Date.now()}-ai`;
      let aiMessageCreated = false;
      let completionReceived = false;
      const accumulatedComponents: UIComponentBlock[] = [];

      // Send to webhook API with streaming callback
      const response = await sendMessage(
        content, 
        user.id, 
        currentSessionId,
        session?.access_token,
        files,
        // Streaming callback function with enhanced completion handling
        (chunk) => {
          if (!isMounted.current) return;
          
          // Process text chunks
          if (chunk.text && chunk.text.trim() !== '') {
            if (!aiMessageCreated) {
              // First time we get text, create the AI message
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
              
              // Add the AI message to the UI
              setMessages((prev) => [...prev, aiMessage]);
              aiMessageCreated = true;
            } else {
              // Update existing message with new content
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
          
          // Handle UI component chunks
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

          // Check for completion flag
          if (chunk.complete === true && !completionReceived) {
            completionReceived = true;
            
            // If we have a session_id in the completion chunk, update the message
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
            
            // If this is a new conversation and we got a session_id, update UI immediately
            if (isNewConversation && chunk.session_id) {
              // Load conversations to get the latest data including the new conversation
              loadConversations().then(newConversations => {
                const newConversation = newConversations.find(
                  (conv) => conv.session_id === chunk.session_id
                );
                
                if (newConversation) {
                  // Update the selected conversation
                  setSelectedConversation(newConversation);
                  
                  // Set the new conversation ID for animation
                  if (setNewConversationId && chunk.session_id) {
                    setNewConversationId(chunk.session_id);
                    
                    // Clear the new conversation ID after 300ms
                    setTimeout(() => {
                      if (isMounted.current && setNewConversationId) {
                        setNewConversationId(null);
                      }
                    }, 300);
                  }
                }
              });
            }
            
            // End loading state immediately when we receive the complete flag
            setLoading(false);
          }
        }
      );
      
      if (isMounted.current && !completionReceived) {
        // Only process this section if we haven't already received a completion flag
        // This avoids redundant processing and UI updates
        
        // For non-streaming responses or if no AI message was created during streaming
        if (!aiMessageCreated) {
          // Create a new AI message with the final response
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
          
          // Add the new AI message to the UI
          setMessages((prev) => [...prev, newAiMessage]);
        } else {
          // For streaming responses, ensure the final content is set correctly
          // This ensures a smooth transition without flashing
          setTimeout(() => {
            if (isMounted.current && !completionReceived) {
              setMessages((prev) => {
                const updatedMessages = [...prev];
                const aiMessageIndex = updatedMessages.findIndex(msg => msg.id === aiMessageId);
                
                if (aiMessageIndex !== -1) {
                  // Always update with the final response to ensure we have the complete text
                  if (response.output) {
                    updatedMessages[aiMessageIndex] = {
                      ...updatedMessages[aiMessageIndex],
                      message: {
                        ...updatedMessages[aiMessageIndex].message,
                        content: response.output,
                      },
                    };
                  }
                }
                
                return updatedMessages;
              });
            }
          }, 100); // Small delay to ensure smooth transition
        }
        
        // If we got a session_id back and it's a new conversation, update the UI
        if (isNewConversation && response.session_id) {
          // First load the conversations to get the latest data
          const newConversations = await loadConversations();
          const newConversation = newConversations.find(
            (conv) => conv.session_id === response.session_id
          );
          
          // Batch our state updates to prevent multiple re-renders
          if (newConversation) {
            // Update messages and selected conversation in one render cycle
            setMessages((prev) => {
              const updatedMessages = [...prev];
              const aiMessageIndex = updatedMessages.findIndex(msg => msg.id === aiMessageId);
              
              if (aiMessageIndex !== -1) {
                updatedMessages[aiMessageIndex] = {
                  ...updatedMessages[aiMessageIndex],
                  session_id: response.session_id,
                };
              }
              
              return updatedMessages;
            });
            
            setSelectedConversation(newConversation);
            
            // Set the new conversation ID for animation
            if (setNewConversationId && response.session_id) {
              setNewConversationId(response.session_id);
              
              // Clear the new conversation ID after 300ms
              setTimeout(() => {
                if (isMounted.current && setNewConversationId) {
                  setNewConversationId(null);
                }
              }, 300);
            }
          }
        }
        
        // End loading state if it hasn't been ended by the completion flag
        setLoading(false);
      }
      
      // Only refresh conversations if this wasn't a new conversation
      // For new conversations, we already loaded them above
      if (!isNewConversation) {
        loadConversations();
      }
      
    } catch (err) {
      console.error('Error in chat flow:', err);
      if (isMounted.current) {
        // Create an error message for display
        const errorMessage = err instanceof Error ? err.message : 'Failed to process your message. Please try again.';
        
        // Add an error message to the chat
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
        
        // Add the error message to the UI
        setMessages((prev) => [...prev, aiErrorMessage]);
        
        setError(errorMessage);
        toast({
          title: 'Erreur',
          description: 'Une erreur est survenue. Veuillez réessayer.',
          variant: 'destructive',
        });
      }
    } finally {
      if (isMounted.current) {
        setLoading(false);
      }
    }
  };

  // Load messages for the selected conversation
  const loadMessages = useCallback(async (conversation: any) => {
    if (!user) return;
    
    try {
      // Don't set loading state when switching between existing conversations
      // This prevents the loading indicator from flashing
      
      // This just fetches messages from the database, it doesn't call the webhook API
      const data = await fetchMessages(conversation.session_id, user.id);
      if (isMounted.current) {
        // Set messages without showing loading state
        setMessages(data);
      }
    } catch (err) {
      console.error('Error loading messages:', err);
      if (isMounted.current) {
        toast({
          title: 'Erreur de chargement',
          description: 'Impossible de charger les messages. Veuillez réessayer.',
          variant: 'destructive',
        });
      }
    }
    // No need to set loading to false since we never set it to true
  }, [user, setMessages, toast, isMounted]);

  return {
    handleSendMessage,
    loadMessages
  };
};
