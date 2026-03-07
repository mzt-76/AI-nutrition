import { useState } from 'react';
import { ChevronDown, ChevronUp, Apple, Beef, Wheat, Milk, ShoppingCart, Package, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import type { ShoppingList, ShoppingListItem } from '@/types/database.types';
import { updateShoppingList } from '@/lib/api';

interface ShoppingListCardProps {
  list: ShoppingList;
  onUpdate: (list: ShoppingList) => void;
  onDelete?: (listId: string) => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  produce: 'Fruits & Légumes',
  proteins: 'Protéines',
  grains: 'Féculents',
  dairy: 'Produits laitiers',
  pantry: 'Épicerie',
  other: 'Autres',
};

const CATEGORY_ICONS: Record<string, typeof Apple> = {
  produce: Apple,
  proteins: Beef,
  grains: Wheat,
  dairy: Milk,
  pantry: ShoppingCart,
  other: Package,
};

const CATEGORY_ORDER = ['produce', 'proteins', 'grains', 'dairy', 'pantry', 'other'];

function formatShoppingTitle(title: string): string {
  return title.replace(/(\d{4}-\d{2}-\d{2})/g, (iso) => {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
  });
}

export function ShoppingListCard({ list, onUpdate, onDelete }: ShoppingListCardProps) {
  const { toast } = useToast();
  const [expanded, setExpanded] = useState(false);
  const items = list.items ?? [];
  const checkedCount = items.filter((i) => i.checked).length;

  const grouped = items.reduce<Record<string, ShoppingListItem[]>>((acc, item) => {
    const cat = item.category && item.category in CATEGORY_LABELS ? item.category : 'other';
    (acc[cat] ??= []).push(item);
    return acc;
  }, {});

  const toggleItem = async (itemIndex: number) => {
    const newItems = items.map((item, i) =>
      i === itemIndex ? { ...item, checked: !item.checked } : item,
    );
    // Optimistic update
    onUpdate({ ...list, items: newItems });
    try {
      await updateShoppingList(list.id, { items: newItems });
    } catch {
      onUpdate(list);
      toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de mettre à jour la liste.' });
    }
  };

  const createdLabel = list.created_at
    ? new Date(list.created_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
    : '';

  // Build global index map for stable keys + toggle callbacks
  const itemGlobalIndex = new Map<ShoppingListItem, number>();
  let globalIdx = 0;
  for (const cat of CATEGORY_ORDER) {
    for (const item of grouped[cat] ?? []) {
      itemGlobalIndex.set(item, globalIdx++);
    }
  }

  return (
    <div className="rounded-xl glass-effect border border-white/5 overflow-hidden min-w-0 w-full">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded((v) => !v); } }}
        className="w-full text-left p-4 hover:bg-white/[0.03] active:bg-white/[0.05] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0">
          <ShoppingCart className="h-5 w-5 text-emerald-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">
              {formatShoppingTitle(list.title?.replace(/^(Courses|Liste de courses)\s*[-–—:]\s*/i, '') ?? '')}
            </p>
            <div className="flex items-center gap-2 mt-0.5">
              {createdLabel && <span className="text-[11px] text-gray-500">{createdLabel}</span>}
              <span className="text-[11px] text-gray-500">
                {checkedCount}/{items.length} articles
              </span>
            </div>
          </div>
          {/* Progress bar */}
          {items.length > 0 && (
            <div className="w-12 h-1.5 bg-white/[0.06] rounded-full overflow-hidden shrink-0">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all"
                style={{ width: `${(checkedCount / items.length) * 100}%` }}
              />
            </div>
          )}
          {onDelete && (
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(list.id); }}
              className="p-1 rounded-md hover:bg-red-500/10 text-gray-600 hover:text-red-400 transition-colors shrink-0"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-gray-600 shrink-0" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-600 shrink-0" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <div className="h-px bg-white/[0.04]" />
          {CATEGORY_ORDER.map((cat) => {
            const catItems = grouped[cat];
            if (!catItems?.length) return null;
            const CatIcon = CATEGORY_ICONS[cat] ?? Package;

            return (
              <div key={cat}>
                <div className="flex items-center gap-2 mb-1.5 min-w-0">
                  <CatIcon className="h-3 w-3 text-gray-500 shrink-0" />
                  <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider truncate">
                    {CATEGORY_LABELS[cat]}
                  </span>
                </div>
                <div className="space-y-0.5 pl-5 min-w-0">
                  {catItems.map((item) => {
                    const idx = itemGlobalIndex.get(item) ?? 0;
                    return (
                      <label
                        key={`${item.name}-${idx}`}
                        className="flex items-center gap-2.5 py-1 px-1.5 -mx-1 rounded-md hover:bg-white/[0.03] cursor-pointer min-w-0"
                      >
                        <input
                          type="checkbox"
                          checked={item.checked}
                          onChange={() => toggleItem(idx)}
                          className="h-4 w-4 rounded border-gray-600 bg-transparent text-emerald-500 focus:ring-0 focus:ring-offset-0 accent-emerald-500 shrink-0"
                        />
                        <span className={`text-sm flex-1 min-w-0 truncate ${item.checked ? 'line-through text-gray-600' : 'text-gray-300'}`}>
                          {item.name}
                        </span>
                        <span className="text-[10px] text-gray-600 shrink-0">
                          {item.quantity > 0 ? `${item.quantity} ${item.unit}` : (item.unit || '1 pce')}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
