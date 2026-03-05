import { Heart, Coffee, Sun, Moon, Cookie } from 'lucide-react';
import { useState } from 'react';
import { Button } from '@/components/ui/button';

interface RecipeData {
  name: string;
  meal_type: string;
  calories_per_serving: number;
  protein_g_per_serving: number;
  carbs_g_per_serving: number;
  fat_g_per_serving: number;
}

interface FavoriteWithRecipe {
  id: string;
  notes: string | null;
  created_at: string | null;
  recipes: RecipeData | null;
}

interface FavoriteCardProps {
  favorite: FavoriteWithRecipe;
  onRemove: (id: string) => void;
}

const MEAL_ICONS: Record<string, typeof Coffee> = {
  'petit-dejeuner': Coffee,
  dejeuner: Sun,
  diner: Moon,
  collation: Cookie,
};

const MEAL_LABELS: Record<string, string> = {
  'petit-dejeuner': 'Petit-déj',
  dejeuner: 'Déjeuner',
  diner: 'Dîner',
  collation: 'Collation',
};

export function FavoriteCard({ favorite, onRemove }: FavoriteCardProps) {
  const [removing, setRemoving] = useState(false);
  const recipe = favorite.recipes;
  if (!recipe) return null;

  const Icon = MEAL_ICONS[recipe.meal_type] ?? Coffee;

  const handleRemove = async () => {
    setRemoving(true);
    onRemove(favorite.id);
  };

  return (
    <div className={`rounded-xl glass-effect border border-white/5 p-4 transition-opacity ${removing ? 'opacity-30' : ''}`}>
      <div className="flex items-start gap-3">
        <Icon className="h-4 w-4 text-gray-500 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-gray-200 truncate">{recipe.name}</p>
            <span className="text-[10px] text-gray-500 bg-white/[0.04] rounded-full px-1.5 py-0.5 shrink-0">
              {MEAL_LABELS[recipe.meal_type] ?? recipe.meal_type}
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-500 tabular-nums">
            <span>{recipe.calories_per_serving} kcal</span>
            <span className="text-gray-600">|</span>
            <span>{recipe.protein_g_per_serving}g prot</span>
            <span className="text-gray-600">|</span>
            <span>{recipe.carbs_g_per_serving}g glu</span>
            <span className="text-gray-600">|</span>
            <span>{recipe.fat_g_per_serving}g lip</span>
          </div>
          {favorite.notes && (
            <p className="text-[11px] text-gray-500 italic mt-1 truncate">{favorite.notes}</p>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-red-400 hover:text-red-300 shrink-0"
          onClick={handleRemove}
          disabled={removing}
        >
          <Heart className="h-4 w-4 fill-current" />
        </Button>
      </div>
    </div>
  );
}

export type { FavoriteWithRecipe };
