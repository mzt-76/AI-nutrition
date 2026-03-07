import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Salad, Loader } from 'lucide-react';

export const PasswordRecoveryModal = () => {
  const { updatePassword, clearRecovery } = useAuth();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);
    const { error: err } = await updatePassword(password);
    setLoading(false);
    if (err) {
      setError(err.message);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-[380px] mx-4 rounded-xl glass-effect border border-white/10 p-6">
        <div className="text-center mb-6">
          <div className="flex justify-center mb-3">
            <div className="h-12 w-12 rounded-full gradient-green flex items-center justify-center glow-green">
              <Salad className="h-6 w-6 text-white" />
            </div>
          </div>
          <h2 className="text-xl font-bold text-foreground">Nouveau mot de passe</h2>
          <p className="text-sm text-muted-foreground mt-1">Choisissez votre nouveau mot de passe</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="new-password" className="text-sm font-medium">
              Nouveau mot de passe
            </label>
            <Input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8 caractères minimum"
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="confirm-password" className="text-sm font-medium">
              Confirmer le mot de passe
            </label>
            <Input
              id="confirm-password"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <Button className="w-full gradient-green text-white" type="submit" disabled={loading}>
            {loading ? (
              <>
                <Loader className="mr-2 h-4 w-4 animate-spin" />
                Modification en cours...
              </>
            ) : (
              'Modifier le mot de passe'
            )}
          </Button>

          <button
            type="button"
            onClick={clearRecovery}
            className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Ignorer et continuer
          </button>
        </form>
      </div>
    </div>
  );
};
