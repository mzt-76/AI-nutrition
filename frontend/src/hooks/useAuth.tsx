
import { useEffect, useState, useCallback, useMemo, createContext, useContext, ReactNode } from 'react';
import { supabase } from '../lib/supabase';
import { Session, User, AuthResponse } from '@supabase/supabase-js';
import { useToast } from '@/hooks/use-toast';

interface AuthProviderProps {
  children: ReactNode;
}

interface AuthContextType {
  session: Session | null;
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signInWithGoogle: () => Promise<{ error: Error | null }>;
  signUp: (email: string, password: string) => Promise<{ error: Error | null, data: AuthResponse['data'] | null }>;
  signOut: () => Promise<void>;
  resetPassword: (email: string) => Promise<{ error: Error | null }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    const setAuthData = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    };

    setAuthData();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      setUser(session?.user ?? null);
      setLoading(false);
    });

    return () => subscription?.unsubscribe();
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      return { error: null };
    } catch (error) {
      toast({
        title: "Erreur d'authentification",
        description: (error as Error)?.message || "Échec de la connexion",
        variant: "destructive",
      });
      return { error: error as Error };
    }
  }, [toast]);

  const signInWithGoogle = useCallback(async () => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`
        }
      });
      if (error) throw error;
      return { error: null };
    } catch (error) {
      toast({
        title: "Erreur Google",
        description: (error as Error)?.message || "Échec de la connexion avec Google",
        variant: "destructive",
      });
      return { error: error as Error };
    }
  }, [toast]);

  // Update user profile with Google information after successful authentication
  useEffect(() => {
    const updateProfileWithGoogleInfo = async () => {
      if (user && user.app_metadata.provider === 'google') {
        try {
          // Check if user profile has a full name already
          const { data: profile, error: profileError } = await supabase
            .from('user_profiles')
            .select('full_name')
            .eq('id', user.id)
            .single();

          if (profileError) throw profileError;

          // Only update if full_name is not set
          if (profile && !profile.full_name && user.user_metadata.full_name) {
            const { error: updateError } = await supabase
              .from('user_profiles')
              .update({ 
                full_name: user.user_metadata.full_name,
                updated_at: new Date().toISOString() 
              })
              .eq('id', user.id);

            if (updateError) throw updateError;
          }
        } catch (error) {
          console.error('Error updating profile with Google info:', error);
        }
      }
    };

    if (user) {
      updateProfileWithGoogleInfo().catch(err =>
        console.error('Failed to update Google profile:', err)
      );
    }
  }, [user]);

  const signUp = useCallback(async (email: string, password: string) => {
    try {
      const { data, error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;
      toast({
        title: "Compte créé",
        description: "Vérifiez votre e-mail pour le lien de confirmation.",
      });
      return { error: null, data };
    } catch (error) {
      toast({
        title: "Erreur d'inscription",
        description: (error as Error)?.message || "Échec de l'inscription",
        variant: "destructive",
      });
      return { error: error as Error, data: null };
    }
  }, [toast]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    toast({
      title: "Déconnexion",
      description: "Vous avez été déconnecté.",
    });
  }, [toast]);

  const resetPassword = useCallback(async (email: string) => {
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email);
      if (error) throw error;
      toast({
        title: "E-mail de réinitialisation envoyé",
        description: "Vérifiez votre e-mail pour le lien de réinitialisation.",
      });
      return { error: null };
    } catch (error) {
      toast({
        title: "Erreur de réinitialisation",
        description: (error as Error)?.message || "Échec de l'envoi de l'e-mail de réinitialisation",
        variant: "destructive",
      });
      return { error: error as Error };
    }
  }, [toast]);

  const value = useMemo(() => ({
    session,
    user,
    loading,
    signIn,
    signInWithGoogle,
    signUp,
    signOut,
    resetPassword,
  }), [session, user, loading, signIn, signInWithGoogle, signUp, signOut, resetPassword]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
