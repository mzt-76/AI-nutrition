import { useState, useRef } from 'react';
import { Trash2, Coffee, Sun, Moon, Cookie, Plus, Loader2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { DailyFoodLog } from '@/types/database.types';
import type { MealType } from '@/hooks/useDailyTracking';
import { MEAL_TYPE_LABELS } from '@/hooks/useDailyTracking';

interface MealSectionProps {
  mealType: MealType;
  entries: DailyFoodLog[];
  onDelete: (id: string) => void;
  onUpdateQuantity: (id: string, quantity: number) => void;
  onUpdateFood: (id: string, newName: string) => void;
  onAddEntry: (mealType: MealType, foodName: string) => Promise<void>;
}

const MEAL_ICONS: Record<MealType, typeof Coffee> = {
  'petit-dejeuner': Coffee,
  dejeuner: Sun,
  diner: Moon,
  collation: Cookie,
};

const MEAL_ACCENT: Record<MealType, string> = {
  'petit-dejeuner': 'text-amber-400/70',
  dejeuner: 'text-orange-400/70',
  diner: 'text-indigo-400/70',
  collation: 'text-emerald-400/70',
};

export function MealSection({ mealType, entries, onDelete, onUpdateQuantity, onUpdateFood, onAddEntry }: MealSectionProps) {
  const { toast } = useToast();
  const totalKcal = entries.reduce((sum, e) => sum + (e.calories ?? 0), 0);
  const Icon = MEAL_ICONS[mealType];

  const [adding, setAdding] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = async () => {
    const trimmed = nameDraft.trim();
    if (!trimmed || submitting) return;

    setSubmitting(true);
    try {
      await onAddEntry(mealType, trimmed);
      setAdding(false);
      setNameDraft('');
    } catch (err: unknown) {
      const msg =
        err instanceof Error && err.message?.includes('404')
          ? 'Aliment non trouvé dans la base.'
          : "Impossible d'ajouter l'aliment.";
      toast({ variant: 'destructive', title: 'Erreur', description: msg });
      // Keep the row open so the user can retry or correct
      inputRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    setAdding(false);
    setNameDraft('');
  };

  return (
    <div className="px-4 py-1.5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className={`h-3.5 w-3.5 ${MEAL_ACCENT[mealType]}`} />
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">
          {MEAL_TYPE_LABELS[mealType]}
        </span>
        <button
          type="button"
          onClick={() => {
            setAdding(true);
            // Focus happens via autoFocus on the input
          }}
          className={`h-5 w-5 rounded-md flex items-center justify-center transition-all
            border border-emerald-500/40 text-emerald-400/70 hover:text-emerald-300 hover:border-emerald-400/60 hover:bg-emerald-500/10
            ${adding ? 'opacity-0 pointer-events-none' : 'opacity-80 hover:opacity-100'}
          `}
          title="Ajouter un aliment"
        >
          <Plus className="h-3 w-3" />
        </button>
        <span className="flex-1" />
        {entries.length > 0 && (
          <span className="text-[11px] text-gray-500 tabular-nums font-medium">
            {Math.round(totalKcal)} kcal
          </span>
        )}
      </div>

      {/* Entries */}
      {entries.length === 0 && !adding ? (
        <div className="py-2 pl-5.5">
          <span className="text-xs text-gray-600 italic">Aucun aliment</span>
        </div>
      ) : (
        <div className="space-y-0.5">
          {entries.map((entry) => (
            <EntryRow
              key={entry.id}
              entry={entry}
              onDelete={onDelete}
              onUpdateQuantity={onUpdateQuantity}
              onUpdateFood={onUpdateFood}
            />
          ))}
        </div>
      )}

      {/* Inline add row */}
      {adding && (
        <div className="flex items-center gap-1.5 py-1.5 px-2 -mx-1 rounded-lg bg-white/[0.02]">
          {submitting ? (
            <Loader2 className="w-3 h-3 text-emerald-400 animate-spin shrink-0" />
          ) : (
            <div className="w-1 h-1 rounded-full bg-emerald-500/50 shrink-0" />
          )}
          <input
            ref={inputRef}
            type="text"
            maxLength={100}
            className="text-sm text-gray-300 bg-white/10 border border-emerald-500/30 rounded px-1.5 py-0.5 flex-1 min-w-0
              placeholder:text-gray-600 outline-none focus:border-emerald-500/50 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed"
            value={nameDraft}
            autoFocus
            disabled={submitting}
            placeholder="Nom de l'aliment..."
            onChange={(e) => setNameDraft(e.target.value)}
            onBlur={() => {
              // Only cancel on blur if empty and not submitting
              if (!nameDraft.trim() && !submitting) handleCancel();
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSubmit();
              if (e.key === 'Escape') handleCancel();
            }}
          />
          {submitting && (
            <span className="text-[10px] text-gray-500 shrink-0">Recherche...</span>
          )}
        </div>
      )}
    </div>
  );
}

function EntryRow({
  entry,
  onDelete,
  onUpdateQuantity,
  onUpdateFood,
}: {
  entry: DailyFoodLog;
  onDelete: (id: string) => void;
  onUpdateQuantity: (id: string, quantity: number) => void;
  onUpdateFood: (id: string, newName: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(entry.quantity ?? ''));
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(entry.food_name ?? '');

  const commitEdit = () => {
    setEditing(false);
    const parsed = parseFloat(draft);
    if (!isNaN(parsed) && parsed > 0 && parsed !== entry.quantity) {
      onUpdateQuantity(entry.id, parsed);
    } else {
      setDraft(String(entry.quantity ?? ''));
    }
  };

  const commitNameEdit = () => {
    setEditingName(false);
    const trimmed = nameDraft.trim();
    if (trimmed && trimmed !== entry.food_name) {
      onUpdateFood(entry.id, trimmed);
    } else {
      setNameDraft(entry.food_name ?? '');
    }
  };

  return (
    <div className="flex items-center gap-1.5 py-1.5 px-2 -mx-1 rounded-lg hover:bg-white/[0.03] group transition-colors">
      <div className="w-1 h-1 rounded-full bg-gray-600 shrink-0" />
      {editingName ? (
        <input
          type="text"
          maxLength={100}
          className="text-sm text-gray-300 bg-white/10 border border-white/20 rounded px-1 py-0.5 flex-1 min-w-0"
          value={nameDraft}
          autoFocus
          onChange={(e) => setNameDraft(e.target.value)}
          onBlur={commitNameEdit}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commitNameEdit();
            if (e.key === 'Escape') {
              setNameDraft(entry.food_name ?? '');
              setEditingName(false);
            }
          }}
        />
      ) : (
        <button
          type="button"
          className="text-sm text-gray-300 truncate flex-1 min-w-0 text-left hover:text-gray-100 cursor-text transition-colors"
          onClick={() => {
            setNameDraft(entry.food_name ?? '');
            setEditingName(true);
          }}
          title="Modifier l'aliment"
        >
          {entry.food_name ? entry.food_name.charAt(0).toUpperCase() + entry.food_name.slice(1) : ''}
        </button>
      )}
      {/* Per-item macros */}
      <span className="text-[10px] tabular-nums shrink-0 flex gap-1.5">
        <span className="text-blue-400">{Math.round(entry.protein_g)}g</span>
        <span className="text-amber-400">{Math.round(entry.carbs_g)}g</span>
        <span className="text-rose-400">{Math.round(entry.fat_g)}g</span>
      </span>
      <span className="w-px h-3 bg-gray-700 shrink-0" />
      {/* Editable quantity */}
      {entry.quantity != null && entry.unit ? (
        editing ? (
          <input
            type="number"
            className="w-14 text-[10px] text-gray-300 bg-white/10 border border-white/20 rounded px-1 py-0.5 text-right shrink-0 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            value={draft}
            autoFocus
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitEdit();
              if (e.key === 'Escape') {
                setDraft(String(entry.quantity ?? ''));
                setEditing(false);
              }
            }}
          />
        ) : (
          <button
            type="button"
            className="text-[10px] text-gray-500 shrink-0 hover:text-gray-300 cursor-text tabular-nums transition-colors"
            onClick={() => {
              setDraft(String(entry.quantity ?? ''));
              setEditing(true);
            }}
            title="Modifier la quantité"
          >
            {entry.quantity}{entry.unit}
          </button>
        )
      ) : null}
      <span className="w-px h-3 bg-gray-700 shrink-0" />
      {/* Calories with unit */}
      <span className="text-xs text-gray-500 tabular-nums shrink-0 text-right flex items-baseline gap-0.5">
        {Math.round(entry.calories)}
        <span className="text-[8px] text-gray-600">kcal</span>
      </span>
      <button
        className="p-1 rounded-md hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors shrink-0"
        onClick={() => onDelete(entry.id)}
      >
        <Trash2 className="h-3 w-3" />
        <span className="sr-only">Supprimer {entry.food_name}</span>
      </button>
    </div>
  );
}
