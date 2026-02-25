
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import { supabase } from '@/lib/supabase';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentFullName: string | null;
}

interface FormData {
  fullName: string;
}

export const SettingsModal = ({ isOpen, onClose, currentFullName }: SettingsModalProps) => {
  const { toast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    defaultValues: {
      fullName: currentFullName || '',
    },
  });

  const onSubmit = async (data: FormData) => {
    setIsLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();

      if (!user) throw new Error("Aucun utilisateur authentifié trouvé");

      const { error: profileError } = await supabase
        .from('user_profiles')
        .update({ full_name: data.fullName, updated_at: new Date().toISOString() })
        .eq('id', user.id);

      if (profileError) throw profileError;

      const { error: userError } = await supabase.auth.updateUser({
        data: { full_name: data.fullName }
      });

      if (userError) throw userError;

      toast({
        title: "Profil mis à jour",
        description: "Votre nom a été modifié avec succès.",
      });

      onClose();
    } catch (error) {
      toast({
        title: "Erreur de mise à jour",
        description: (error as Error)?.message || "Impossible de mettre à jour le profil",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Paramètres du profil</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="fullName" className="text-right">
                Nom complet
              </Label>
              <Input
                id="fullName"
                {...register("fullName", { required: "Le nom complet est requis" })}
                className="col-span-3"
              />
              {errors.fullName && (
                <p className="col-span-3 col-start-2 text-sm text-destructive">
                  {errors.fullName.message}
                </p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
              Annuler
            </Button>
            <Button type="submit" disabled={isLoading} className="gradient-green text-white">
              {isLoading ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
