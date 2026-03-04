import { useEffect, useRef } from 'react';
import { Message } from '@/types/database.types';
import { MessageItem } from './MessageItem';
import { useIsMobile } from '@/hooks/use-mobile';
import { LoadingDots } from '@/components/ui/loading-dots';
import { Salad, Calculator, UtensilsCrossed, CalendarCheck, BookOpen } from 'lucide-react';

const SUGGESTED_QUESTIONS = [
  {
    icon: Calculator,
    text: "Calculer mes besoins caloriques",
  },
  {
    icon: UtensilsCrossed,
    text: "Créer un plan nutritionnel personnalisé",
  },
  {
    icon: CalendarCheck,
    text: "Procéder au suivi hebdomadaire",
  },
  {
    icon: BookOpen,
    text: "Faire une recherche de nutrition",
  },
];

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  isGeneratingResponse?: boolean;
  isLoadingMessages?: boolean;
  onSuggestedQuestion?: (question: string) => void;
  onAction?: (value: string) => void;
}

export const MessageList = ({
  messages,
  isLoading,
  isGeneratingResponse = false,
  isLoadingMessages = false,
  onSuggestedQuestion,
  onAction,
}: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();

  useEffect(() => {
    const scrollTimeout = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);

    return () => clearTimeout(scrollTimeout);
  }, [messages, isGeneratingResponse]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 h-full">
        <div className="max-w-lg text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 rounded-full gradient-green flex items-center justify-center glow-green">
              <Salad className="h-8 w-8 text-white" />
            </div>
          </div>
          <h3 className="text-2xl font-bold mb-2">Nutritionniste IA</h3>
          <p className="text-muted-foreground mb-6">
            Posez votre question ou choisissez un sujet ci-dessous
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {SUGGESTED_QUESTIONS.map((item) => (
              <button
                key={item.text}
                onClick={() => onSuggestedQuestion?.(item.text)}
                className="glass-effect rounded-lg p-4 text-left hover:border-primary/40 transition-all hover:shadow-glow cursor-pointer group"
              >
                <item.icon className="h-5 w-5 text-primary mb-2 group-hover:scale-110 transition-transform" />
                <p className="text-sm font-medium text-foreground">{item.text}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute inset-0 overflow-y-auto">
      <div className="py-6 min-h-full mx-auto w-full max-w-4xl">
        {messages.map((message, index) => (
          <div key={message.id} className="mb-6">
            <MessageItem
              message={message}
              isLastMessage={index === messages.length - 1}
              onAction={onAction}
            />
          </div>
        ))}

        {isGeneratingResponse && (
          <div id="loading-indicator" className="max-w-4xl mx-auto px-4 flex items-start gap-4 animate-fade-in mb-6">
            <div className="h-8 w-8 rounded-full gradient-green flex items-center justify-center text-white text-xs font-bold">
              NIA
            </div>
            <div className="flex items-center glass-effect py-3 px-4 rounded-lg max-w-[80%]">
              <LoadingDots className="text-current" />
            </div>
          </div>
        )}

        {isLoadingMessages && (
          <div id="loading-indicator" className="max-w-4xl mx-auto px-4 flex items-start gap-4 animate-fade-in mb-6">
            <div className="h-8 w-8 rounded-full gradient-green flex items-center justify-center text-white text-xs font-bold">
              NIA
            </div>
            <div className="flex items-center glass-effect py-3 px-4 rounded-lg max-w-[80%]">
              <LoadingDots className="text-current" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} className="h-10" />
      </div>
    </div>
  );
};
