import { useEffect, useState } from 'react';
import { CalendarDays, Heart, ShoppingCart, Loader2 } from 'lucide-react';
import { useIsMobile } from '@/hooks/use-mobile';
import { useAuth } from '@/hooks/useAuth';
import { MobileHeader } from '@/components/navigation/MobileHeader';
import { ScrollArea } from '@/components/ui/scroll-area';
import { fetchMealPlans, fetchFavorites, removeFavorite, fetchShoppingLists } from '@/lib/api';
import type { MealPlanSummary } from '@/lib/api';
import type { ShoppingList } from '@/types/database.types';
import { PlanCard } from '@/components/plans/PlanCard';
import { FavoriteCard } from '@/components/plans/FavoriteCard';
import type { FavoriteWithRecipe } from '@/components/plans/FavoriteCard';
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
  const userId = user?.id ?? '';

  const [tab, setTab] = useState<Tab>('plans');
  const [loading, setLoading] = useState(false);

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
      try {
        if (tab === 'plans') {
          const data = await fetchMealPlans(userId);
          if (!cancelled) setPlans(data);
        } else if (tab === 'favoris') {
          const data = await fetchFavorites(userId);
          if (!cancelled) setFavorites(data as unknown as FavoriteWithRecipe[]);
        } else {
          const data = await fetchShoppingLists(userId);
          if (!cancelled) setShoppingLists(data);
        }
      } catch (err) {
        console.error(`Error loading ${tab}:`, err);
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
      // Re-fetch on error
      if (userId) {
        const data = await fetchFavorites(userId);
        setFavorites(data as unknown as FavoriteWithRecipe[]);
      }
    }
  };

  const handleShoppingListUpdate = (updated: ShoppingList) => {
    setShoppingLists((prev) => prev.map((l) => (l.id === updated.id ? updated : l)));
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
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-emerald-500/60" />
            </div>
          ) : (
            <>
              {/* Plans */}
              {tab === 'plans' && (
                plans.length > 0
                  ? plans.map((p) => <PlanCard key={p.id} plan={p} />)
                  : <EmptyState message={emptyMessages.plans} />
              )}

              {/* Favoris */}
              {tab === 'favoris' && (
                favorites.length > 0
                  ? favorites.map((f) => (
                      <FavoriteCard key={f.id} favorite={f} onRemove={handleRemoveFavorite} />
                    ))
                  : <EmptyState message={emptyMessages.favoris} />
              )}

              {/* Courses */}
              {tab === 'courses' && (
                shoppingLists.length > 0
                  ? shoppingLists.map((sl) => (
                      <ShoppingListCard key={sl.id} list={sl} onUpdate={handleShoppingListUpdate} />
                    ))
                  : <EmptyState message={emptyMessages.courses} />
              )}
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <p className="text-sm text-gray-500">{message}</p>
    </div>
  );
}

export default MyPlans;
