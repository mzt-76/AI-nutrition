import { useEffect, useRef, useState, useCallback } from 'react';
import { Message } from '@/types/database.types';
import { MessageItem } from './MessageItem';
import type { MealDataFromPlan } from './MessageItem';
import { RecipeDetailDrawer } from '@/components/recipes/RecipeDetailDrawer';
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
  hasActiveConversation?: boolean;
  onSuggestedQuestion?: (question: string) => void;
  onAction?: (value: string) => void;
}

export const MessageList = ({
  messages,
  isLoading,
  isGeneratingResponse = false,
  isLoadingMessages = false,
  hasActiveConversation = false,
  onSuggestedQuestion,
  onAction,
}: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedMeal, setSelectedMeal] = useState<MealDataFromPlan | null>(null);

  const handleMealClick = useCallback((data: MealDataFromPlan) => {
    setSelectedMeal(data);
    setDrawerOpen(true);
  }, []);

  useEffect(() => {
    const scrollTimeout = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);

    return () => clearTimeout(scrollTimeout);
  }, [messages, isGeneratingResponse]);

  if (messages.length === 0 && !isLoading && !hasActiveConversation) {
    return (
      <div className="flex-1 overflow-y-auto overscroll-contain touch-pan-y p-6 h-full">
        <div className="max-w-lg mx-auto text-center flex flex-col items-center justify-center min-h-full">
          <div className="flex justify-center mb-3 md:mb-4">
            <div className={`${isMobile ? 'h-12 w-12' : 'h-16 w-16'} rounded-full gradient-green flex items-center justify-center glow-green`}>
              <Salad className={`${isMobile ? 'h-6 w-6' : 'h-8 w-8'} text-white`} />
            </div>
          </div>
          <h3 className={`${isMobile ? 'text-xl' : 'text-2xl'} font-bold mb-1 md:mb-2`}>Nutritionniste IA</h3>
          <p className="text-muted-foreground mb-4 md:mb-6 text-sm">
            Posez votre question ou choisissez un sujet ci-dessous
          </p>
          <div className="grid grid-cols-2 gap-2 w-full">
            {SUGGESTED_QUESTIONS.map((item) => (
              <button
                key={item.text}
                onClick={() => onSuggestedQuestion?.(item.text)}
                className="glass-effect rounded-lg py-3 px-2 md:p-4 hover:border-primary/40 transition-all hover:shadow-glow cursor-pointer group flex flex-col items-center justify-center text-center"
              >
                <item.icon className="h-4 w-4 md:h-5 md:w-5 text-primary mb-1.5 group-hover:scale-110 transition-transform" />
                <p className="text-[11px] md:text-sm font-medium text-foreground leading-tight">{item.text}</p>
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
              onMealClick={handleMealClick}
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

      <RecipeDetailDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        mealData={selectedMeal ?? undefined}
      />
    </div>
  );
};
