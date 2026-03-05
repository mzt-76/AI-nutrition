import { useEffect, useState } from 'react';
import { CalendarDays, Heart, ShoppingCart } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAuth } from '@/hooks/useAuth';
import { useToast } from '@/hooks/use-toast';
import { MobileHeader } from '@/components/navigation/MobileHeader';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { fetchMealPlans, fetchFavorites, removeFavorite, fetchShoppingLists, deleteShoppingList } from '@/lib/api';
import type { MealPlanSummary } from '@/lib/api';
import type { ShoppingList, FavoriteWithRecipe } from '@/types/database.types';
import { PlanCard } from '@/components/plans/PlanCard';
import { FavoriteCard } from '@/components/plans/FavoriteCard';
import { RecipeDetailDrawer } from '@/components/recipes/RecipeDetailDrawer';
import { ShoppingListCard } from '@/components/plans/ShoppingListCard';

type Tab = 'plans' | 'favoris' | 'courses';

const TABS: { key: Tab; label: string; icon: typeof CalendarDays }[] = [
  { key: 'plans', label: 'Plans', icon: CalendarDays },
  { key: 'favoris', label: 'Favoris', icon: Heart },
  { key: 'courses', label: 'Courses', icon: ShoppingCart },
];

const MyPlans = () => {
  const isMobile = useIsMobile();
  const { user } = useAuth();
  const { toast } = useToast();
  const userId = user?.id ?? '';

  const [tab, setTab] = useState<Tab>('plans');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRecipeId, setSelectedRecipeId] = useState<string | null>(null);

  // Data
  const [plans, setPlans] = useState<MealPlanSummary[]>([]);
  const [favorites, setFavorites] = useState<FavoriteWithRecipe[]>([]);
  const [shoppingLists, setShoppingLists] = useState<ShoppingList[]>([]);

  // Fetch when tab changes or userId changes
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      setError(false);
      try {
        if (tab === 'plans') {
          const data = await fetchMealPlans(userId);
          if (!cancelled) setPlans(data);
        } else if (tab === 'favoris') {
          const data = await fetchFavorites(userId);
          if (!cancelled) setFavorites(data);
        } else {
          const data = await fetchShoppingLists(userId);
          if (!cancelled) setShoppingLists(data);
        }
      } catch (err) {
        console.error(`Error loading ${tab}:`, err);
        if (!cancelled) {
          setError(true);
          toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de charger les données.' });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [tab, userId]);

  const handleRemoveFavorite = async (id: string) => {
    setFavorites((prev) => prev.filter((f) => f.id !== id));
    try {
      await removeFavorite(id);
    } catch {
      toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de retirer le favori.' });
      if (userId) {
        const data = await fetchFavorites(userId);
        setFavorites(data as FavoriteWithRecipe[]);
      }
    }
  };

  const handleShoppingListUpdate = (updated: ShoppingList) => {
    setShoppingLists((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
  };

  const handleShoppingListDelete = async (listId: string) => {
    setShoppingLists((prev) => prev.filter((l) => l.id !== listId));
    try {
      await deleteShoppingList(listId);
      toast({ title: 'Liste supprimée' });
    } catch {
      toast({ variant: 'destructive', title: 'Erreur', description: 'Impossible de supprimer la liste.' });
      if (userId) {
        const data = await fetchShoppingLists(userId);
        setShoppingLists(data);
      }
    }
  };

  const emptyMessages: Record<Tab, string> = {
    plans: 'Génère ton premier plan dans le Chat',
    favoris: 'Ajoute des recettes en favoris depuis le chat',
    courses: 'Génère une liste de courses depuis un plan',
  };

  return (
    <div className="flex flex-col h-screen gradient-bg">
      {isMobile && <MobileHeader title="Mes Plans" />}
      {!isMobile && (
        <div className="flex items-center h-14 border-b border-border/50 px-6">
          <h1 className="text-lg font-semibold">Mes Plans</h1>
        </div>
      )}

      {/* Tab selector */}
      <div className="flex px-4 pt-3 pb-1 gap-1">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors
              ${tab === key
                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20'
                : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.04] border border-transparent'
              }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className={`px-4 py-3 space-y-2.5 ${isMobile ? 'pb-20' : 'pb-8'}`}>
          {loading ? (
            <div className="space-y-2.5">
              {[1, 2, 3].map((i) => (
                <div key={i} className="rounded-xl border border-white/5 p-4 space-y-3">
                  <Skeleton className="h-4 w-3/4 bg-white/[0.06]" />
                  <div className="flex gap-3">
                    <Skeleton className="h-3 w-16 bg-white/[0.04]" />
                    <Skeleton className="h-3 w-20 bg-white/[0.04]" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <>
              {/* Plans */}
              {tab === 'plans' && (
                plans.length > 0
                  ? plans.map((p) => <PlanCard key={p.id} plan={p} />)
                  : <EmptyState message={emptyMessages.plans} isError={error} />
              )}

              {/* Favoris */}
              {tab === 'favoris' && (
                favorites.length > 0
                  ? favorites.map((f) => (
                      <FavoriteCard
                        key={f.id}
                        favorite={f}
                        onRemove={handleRemoveFavorite}
                        onClick={() => {
                          setSelectedRecipeId(f.recipe_id);
                          setDrawerOpen(true);
                        }}
                      />
                    ))
                  : <EmptyState message={emptyMessages.favoris} isError={error} />
              )}

              {/* Courses */}
              {tab === 'courses' && (
                shoppingLists.length > 0
                  ? shoppingLists.map((sl) => (
                      <ShoppingListCard key={sl.id} list={sl} onUpdate={handleShoppingListUpdate} onDelete={handleShoppingListDelete} />
                    ))
                  : <EmptyState message={emptyMessages.courses} isError={error} />
              )}
            </>
          )}
        </div>
      </ScrollArea>

      <RecipeDetailDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        recipeId={selectedRecipeId ?? undefined}
        onFavoriteChange={() => {
          // Refresh favorites list when toggled from drawer
          if (userId && tab === 'favoris') {
            fetchFavorites(userId).then(setFavorites);
          }
        }}
      />
    </div>
  );
};

function EmptyState({ message, isError }: { message: string; isError?: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <p className={`text-sm ${isError ? 'text-red-400/70' : 'text-gray-500'}`}>
        {isError ? 'Erreur de chargement. Réessaie plus tard.' : message}
      </p>
    </div>
  );
}

export default MyPlans;
