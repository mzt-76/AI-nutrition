# Step 5.3 — UI Polish, Loading States, Error Handling

**Goal:** Production-quality UX — no blank screens, clear feedback, graceful errors.
**Depends on:** Step 5.2 (reveals actual issues to fix)

---

## Current State

### What already exists:
- **DailyTracking**: `loading` state with Loader2 spinner (centered, line 55-58)
- **MyPlans**: `loading` state with Loader2 spinner per tab (line 118-121)
- **MealPlanView**: simple "Chargement du plan..." text + red error display on failure
- **TrackingInput**: `sending` state with Loader2 in send button + toast feedback
- **useDailyTracking**: `loading` + `planLoading` states, toasts on all CRUD errors
- **ChatInput**: disabled state during loading, file size/count validation with toasts
- **MessageHandling**: sophisticated streaming with error messages in chat
- **Toast system**: shadcn toast (`useToast()`) wired throughout app, working well
- **Empty states**: MyPlans has per-tab empty messages
- **Error handling in api.ts**: `apiFetch` throws on non-200, pages catch + console.error
- **Unused components**: `Skeleton` (`ui/skeleton.tsx`) and `LoadingDots` (`ui/loading-dots.tsx`) both exist but are NEVER used

### What's MISSING:
- **MyPlans error handling**: catch block only console.errors (line 55), no toast/error UI
- **ShoppingListCard**: silent error revert on toggle failure (line 50-53), no toast
- **Skeleton screens**: `Skeleton` component exists but unused — all pages show blank + spinner
- **MealPlanView**: error text not user-friendly (raw error), no retry button
- **Chat retry**: no retry button on failed streaming messages
- **No error boundaries**: no React ErrorBoundary for page-level crashes
- **Pull-to-refresh**: no refresh gesture on mobile
- **Transition animations**: tab switches are instant

---

## Tasks (Priority Order)

### Task 1: Error toasts on MyPlans + ShoppingListCard
- [ ] Add `useToast()` to MyPlans, show toast when fetchMealPlans/fetchFavorites/fetchShoppingLists fail (line 55)
- [ ] Add toast in ShoppingListCard on toggle failure (line 50-53)
- [ ] Show "Erreur de chargement" in empty state if error occurred
- Scope: ~15 lines across 2 files

### Task 2: Loading skeletons for DailyTracking
Replace Loader2 spinner with skeleton screens using existing `@/components/ui/skeleton.tsx`:
- [ ] CalorieGauge skeleton (circle outline pulsing)
- [ ] TrackingMacros skeleton (3 gray bars pulsing)
- [ ] MealSection skeleton (2-3 placeholder rows)
- Scope: ~50 lines new `TrackingSkeleton` component

### Task 3: Loading skeletons for MyPlans
- [ ] PlanCard skeleton (glass card with pulsing lines)
- [ ] FavoriteCard skeleton
- [ ] ShoppingListCard skeleton
- Scope: ~40 lines new `PlansSkeleton` component

### Task 4: MealPlanView error + retry
- [ ] Make error message user-friendly (not raw error text)
- [ ] Add "Reessayer" button that re-fetches
- Scope: ~10 lines in MealPlanView.tsx

### Task 5: Chat retry on failed messages
- [ ] Check current behavior in MessageHandling.tsx (has error handling at line 307-319)
- [ ] Add "Reessayer" button on failed message bubbles
- Scope: ~20 lines in MessageItem.tsx or MessageHandling.tsx

### Task 6: Use LoadingDots component
- [ ] Replace "Chargement du plan..." text in MealPlanView with LoadingDots
- [ ] Consider using in chat "thinking" indicator
- Scope: ~5 lines, component already exists

### Task 7 (optional): Pull-to-refresh on mobile
- [ ] Add pull-to-refresh gesture on DailyTracking (calls refreshEntries)
- [ ] Add pull-to-refresh on MyPlans (re-fetches current tab)
- Scope: nice-to-have, CSS overscroll-behavior or lightweight hook

### Task 8 (optional): Subtle transition animations
- [ ] Tab switch: fade-in content (CSS transition, not framer-motion)
- [ ] Entry add/remove: simple opacity transition
- Scope: CSS only

---

## NOT in scope (defer to post-deploy):
- Offline-first with service worker (PWA step)
- Global error boundary (React ErrorBoundary)
- i18n system (already hardcoded French, fine for MVP)

---

## Success Criteria
- No blank/white screens during loading (skeletons everywhere)
- All API errors show user-friendly toast
- Failed chat messages show retry option
- Mobile UX feels responsive and polished
