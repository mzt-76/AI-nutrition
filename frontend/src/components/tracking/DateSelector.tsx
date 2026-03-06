import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface DateSelectorProps {
  selectedDate: Date;
  isToday: boolean;
  onPrevious: () => void;
  onNext: () => void;
  onToday: () => void;
}

export function DateSelector({ selectedDate, isToday, onPrevious, onNext, onToday }: DateSelectorProps) {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <Button
        variant="ghost"
        size="icon"
        onClick={onPrevious}
        className="h-10 w-10 rounded-full text-gray-400 hover:text-white hover:bg-white/5"
      >
        <ChevronLeft className="h-5 w-5" />
        <span className="sr-only">Jour précédent</span>
      </Button>

      <button
        onClick={isToday ? undefined : onToday}
        className={`flex flex-col items-center gap-0.5 transition-colors ${!isToday ? 'cursor-pointer active:scale-95' : 'cursor-default'}`}
      >
        <span className="text-sm font-medium text-gray-200 capitalize tracking-wide">
          {format(selectedDate, 'EEEE d MMMM', { locale: fr })}
        </span>
        {isToday ? (
          <span className="text-[10px] font-semibold text-emerald-400 uppercase tracking-widest">
            Aujourd&apos;hui
          </span>
        ) : (
          <span className="text-[10px] text-gray-500 hover:text-emerald-400/80 transition-colors">
            Revenir à aujourd&apos;hui
          </span>
        )}
      </button>

      <Button
        variant="ghost"
        size="icon"
        onClick={onNext}
        className="h-10 w-10 rounded-full text-gray-400 hover:text-white hover:bg-white/5"
      >
        <ChevronRight className="h-5 w-5" />
        <span className="sr-only">Jour suivant</span>
      </Button>
    </div>
  );
}
