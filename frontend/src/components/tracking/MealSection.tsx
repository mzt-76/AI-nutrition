import { useState } from 'react';
import { Trash2, Coffee, Sun, Moon, Cookie } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { DailyFoodLog } from '@/types/database.types';
import type { MealType } from '@/hooks/useDailyTracking';
import { MEAL_TYPE_LABELS } from '@/hooks/useDailyTracking';

interface MealSectionProps {
  mealType: MealType;
  entries: DailyFoodLog[];
  onDelete: (id: string) => void;
  onUpdateQuantity: (id: string, quantity: number) => void;
  onUpdateFood: (id: string, newName: string) => void;
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

export function MealSection({ mealType, entries, onDelete, onUpdateQuantity, onUpdateFood }: MealSectionProps) {
  const totalKcal = entries.reduce((sum, e) => sum + (e.calories ?? 0), 0);
  const Icon = MEAL_ICONS[mealType];

  return (
    <div className="px-4 py-1.5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className={`h-3.5 w-3.5 ${MEAL_ACCENT[mealType]}`} />
        <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex-1">
          {MEAL_TYPE_LABELS[mealType]}
        </span>
        {entries.length > 0 && (
          <span className="text-[11px] text-gray-500 tabular-nums font-medium">
            {Math.round(totalKcal)} kcal
          </span>
        )}
      </div>

      {/* Entries */}
      {entries.length === 0 ? (
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
          {entry.food_name}
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
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 text-gray-600 hover:text-red-400 active:text-red-400 transition-colors shrink-0"
        onClick={() => onDelete(entry.id)}
      >
        <Trash2 className="h-3 w-3" />
        <span className="sr-only">Supprimer {entry.food_name}</span>
      </Button>
    </div>
  );
}
