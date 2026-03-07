import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';
import { Loader } from 'lucide-react';
import { logger } from '@/lib/logger';

export const AuthCallback = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleAuthCallback = async () => {
      try {
        const hashParams = new URLSearchParams(window.location.hash.substring(1));
        const queryParams = new URLSearchParams(window.location.search);

        const errorParam = hashParams.get('error') || queryParams.get('error');
        if (errorParam) {
          const KNOWN_ERRORS: Record<string, string> = {
            'access_denied': "Accès refusé",
            'server_error': "Erreur serveur",
            'temporarily_unavailable': "Service temporairement indisponible",
          };
          setError(KNOWN_ERRORS[errorParam] ?? "Erreur d'authentification");
          return;
        }

        const { data, error } = await supabase.auth.getSession();

        if (error) {
          throw error;
        }

        if (data?.session) {
          navigate('/');
        } else {
          navigate('/login');
        }
      } catch (err) {
        logger.error('Error during auth callback:', err);
        setError("L'authentification a échoué. Veuillez réessayer.");
      }
    };

    handleAuthCallback();
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center gradient-bg">
      {error ? (
        <div className="text-center">
          <h2 className="text-xl font-semibold text-red-500 mb-2">Erreur d'authentification</h2>
          <p className="text-muted-foreground">{error}</p>
          <button
            className="mt-4 px-4 py-2 gradient-green text-white rounded hover:opacity-90"
            onClick={() => navigate('/login')}
          >
            Retour à la connexion
          </button>
        </div>
      ) : (
        <div className="text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Authentification en cours...</p>
        </div>
      )}
    </div>
  );
};

export default AuthCallback;
