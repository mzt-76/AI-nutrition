import { QuickReplyChipsProps } from '@/types/generative-ui.types';

export function QuickReplyChips({ options, onAction }: QuickReplyChipsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onAction?.(option.value)}
          className="px-4 py-2 rounded-full text-sm font-medium border border-emerald-500/30 text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 hover:border-emerald-500/50 transition-all cursor-pointer"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
