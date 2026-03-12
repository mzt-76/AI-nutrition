import { useIsMobile } from '@/hooks/use-mobile';
import { MobileHeader } from '@/components/navigation/MobileHeader';
import { NavSidebar } from '@/components/navigation/NavSidebar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { useDailyTracking } from '@/hooks/useDailyTracking';
import { DateSelector } from '@/components/tracking/DateSelector';
import { CalorieGauge } from '@/components/tracking/CalorieGauge';
import { TrackingMacros } from '@/components/tracking/TrackingMacros';
import { MealSection } from '@/components/tracking/MealSection';
import { PlanValidation } from '@/components/tracking/PlanValidation';
import { TrackingInput } from '@/components/tracking/TrackingInput';
import type { MealType } from '@/hooks/useDailyTracking';

const MEAL_TYPES: MealType[] = ['petit-dejeuner', 'dejeuner', 'collation', 'diner'];

const DailyTracking = () => {
  const isMobile = useIsMobile();
  const {
    selectedDate,
    dateStr,
    isSelectedToday,
    goToPreviousDay,
    goToNextDay,
    goToToday,
    targets,
    totals,
    groupedEntries,
    planDayMeals,
    loading,
    profileIncomplete,
    deleteEntry,
    updateEntryQuantity,
    updateEntryFood,
    addManualEntry,
    logPlanMeal,
    isPlanMealLogged,
    refreshEntries,
  } = useDailyTracking();

  const pageContent = (
    <div className="flex flex-col flex-1 min-w-0 h-screen gradient-bg">
      {isMobile && <MobileHeader title="Suivi du Jour" />}
      {!isMobile && (
        <div className="flex items-center h-14 border-b border-border/50 px-6">
          <h1 className="text-lg font-semibold">Suivi du Jour</h1>
        </div>
      )}

      <ScrollArea className="flex-1">
        <div className="pb-24">
          <DateSelector
            selectedDate={selectedDate}
            isToday={isSelectedToday}
            onPrevious={goToPreviousDay}
            onNext={goToNextDay}
            onToday={goToToday}
          />

          {profileIncomplete && (
            <div className="mx-4 mt-3 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <p className="text-sm text-yellow-200/90">
                Veuillez d'abord renseigner votre profil (âge, poids, taille, objectifs) via le chat pour activer le suivi nutritionnel.
              </p>
            </div>
          )}

          {loading ? (
            <div className="px-4 pt-4 space-y-6">
              {/* CalorieGauge skeleton */}
              <div className="flex justify-center">
                <Skeleton className="h-40 w-40 rounded-full bg-white/[0.04]" />
              </div>
              {/* TrackingMacros skeleton */}
              <div className="space-y-3 px-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="space-y-1.5">
                    <Skeleton className="h-3 w-20 bg-white/[0.04]" />
                    <Skeleton className="h-2 w-full bg-white/[0.06] rounded-full" />
                  </div>
                ))}
              </div>
              {/* MealSection skeleton */}
              <div className="space-y-2">
                {[1, 2].map((i) => (
                  <div key={i} className="px-2 space-y-2">
                    <Skeleton className="h-3 w-24 bg-white/[0.04]" />
                    <Skeleton className="h-10 w-full bg-white/[0.03] rounded-lg" />
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              <CalorieGauge consumed={totals.calories} target={targets.calories} />

              <TrackingMacros
                consumed={{ protein_g: totals.protein_g, carbs_g: totals.carbs_g, fat_g: totals.fat_g }}
                targets={{ protein_g: targets.protein_g, carbs_g: targets.carbs_g, fat_g: targets.fat_g }}
              />

              {/* Separator */}
              <div className="mx-4 my-3 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />

              {/* Meal sections */}
              <div className="space-y-1">
                {MEAL_TYPES.map((mt) => (
                  <MealSection
                    key={mt}
                    mealType={mt}
                    entries={groupedEntries[mt]}
                    onDelete={deleteEntry}
                    onUpdateQuantity={updateEntryQuantity}
                    onUpdateFood={updateEntryFood}
                    onAddEntry={addManualEntry}
                  />
                ))}
              </div>

              {/* Plan validation */}
              {planDayMeals.length > 0 && (
                <>
                  <div className="mx-4 my-3 h-px bg-gradient-to-r from-transparent via-white/[0.06] to-transparent" />
                  <PlanValidation
                    meals={planDayMeals}
                    onLogMeal={logPlanMeal}
                    isMealLogged={isPlanMealLogged}
                  />
                </>
              )}
            </>
          )}
        </div>
      </ScrollArea>

      <TrackingInput dateStr={dateStr} onEntryCreated={refreshEntries} />
    </div>
  );

  if (isMobile) return pageContent;

  return (
    <div className="flex h-screen overflow-hidden">
      <NavSidebar />
      {pageContent}
    </div>
  );
};

export default DailyTracking;
