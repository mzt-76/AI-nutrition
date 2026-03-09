
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Login from "./pages/Login";
import { lazy, Suspense, useState, useEffect } from "react";
import { AuthCallback } from "./components/auth/AuthCallback";
import { PasswordRecoveryModal } from "./components/auth/PasswordRecoveryModal";
import { BottomTabs } from "./components/navigation/BottomTabs";
import { ThemeProvider } from "@/components/theme-provider";
import { useIsMobile } from "@/hooks/use-mobile";
import { supabase } from "@/lib/supabase";

const Chat = lazy(() => import("./pages/Chat"));
const Admin = lazy(() => import("./pages/Admin"));
const MealPlanView = lazy(() => import("./pages/MealPlanView"));
const DailyTracking = lazy(() => import("./pages/DailyTracking"));
const MyPlans = lazy(() => import("./pages/MyPlans"));
const NotFound = lazy(() => import("./pages/NotFound"));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
});

// Protected route component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
};

// Admin-only route — checks user_profiles.is_admin (TTL: 5 min)
const ADMIN_CACHE_TTL_MS = 5 * 60 * 1000;
const adminCache = new Map<string, { value: boolean; expiresAt: number }>();

const AdminRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(() => {
    if (user) {
      const cached = adminCache.get(user.id);
      if (cached && Date.now() < cached.expiresAt) return cached.value;
      // Expired — clear it
      if (cached) adminCache.delete(user.id);
    }
    return null;
  });

  useEffect(() => {
    if (!user) return;
    const cached = adminCache.get(user.id);
    if (cached && Date.now() < cached.expiresAt) {
      setIsAdmin(cached.value);
      return;
    }
    // Expired or missing — re-fetch
    adminCache.delete(user.id);
    supabase
      .from('user_profiles')
      .select('is_admin')
      .eq('id', user.id)
      .limit(1)
      .then(({ data }) => {
        const val = data?.[0]?.is_admin === true;
        adminCache.set(user.id, { value: val, expiresAt: Date.now() + ADMIN_CACHE_TTL_MS });
        setIsAdmin(val);
      })
      .catch(() => setIsAdmin(false));
  }, [user]);

  if (loading || isAdmin === null) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="animate-pulse">Loading...</div>
      </div>
    );
  }

  if (!user || !isAdmin) {
    return <Navigate to="/" />;
  }

  return <>{children}</>;
};

const AppRoutes = () => {
  const { user, isRecovery } = useAuth();
  const isMobile = useIsMobile();

  return (
    <>
      {isRecovery && <PasswordRecoveryModal />}
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-background"><div className="animate-pulse">Loading...</div></div>}>
      <Routes>
        <Route
          path="/login"
          element={user ? <Navigate to="/" /> : <Login />}
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <Admin />
            </AdminRoute>
          }
        />
        <Route
          path="/tracking"
          element={
            <ProtectedRoute>
              <DailyTracking />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans"
          element={
            <ProtectedRoute>
              <MyPlans />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans/:id"
          element={
            <ProtectedRoute>
              <MealPlanView />
            </ProtectedRoute>
          }
        />
        {/* OAuth callback route for handling authentication redirects */}
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      {isMobile && user && <BottomTabs />}
    </Suspense>
    </>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider defaultTheme="dark" forcedTheme="dark">
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <ErrorBoundary>
              <AppRoutes />
            </ErrorBoundary>
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
