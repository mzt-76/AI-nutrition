
import { useState, useEffect, useCallback, KeyboardEvent } from 'react';
import { User, Ruler, Target, UtensilsCrossed, LogOut, RefreshCw, X } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/hooks/useAuth';
import { useIsMobile } from '@/hooks/use-mobile';
import { supabase } from '@/lib/supabase';
import { recalculateProfile } from '@/lib/api';
import type { UserProfile } from '@/types/database.types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentFullName: string | null;
}

const ACTIVITY_OPTIONS = [
  { value: 'sedentary', label: 'Sédentaire' },
  { value: 'light', label: 'Légèrement actif' },
  { value: 'moderate', label: 'Modérément actif' },
  { value: 'active', label: 'Actif' },
  { value: 'very_active', label: 'Très actif' },
];

const DIET_OPTIONS = [
  { value: 'omnivore', label: 'Omnivore' },
  { value: 'vegetarien', label: 'Végétarien' },
  { value: 'vegan', label: 'Végan' },
  { value: 'pescetarien', label: 'Pescétarien' },
  { value: 'sans_gluten', label: 'Sans gluten' },
];

const GENDER_OPTIONS = [
  { value: 'male', label: 'Homme' },
  { value: 'female', label: 'Femme' },
];

// ---------------------------------------------------------------------------
// TagInput — inline sub-component (single use)
// ---------------------------------------------------------------------------

function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    }
  };

  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
            >
              {tag}
              <button
                type="button"
                onClick={() => onChange(value.filter((t) => t !== tag))}
                className="hover:text-emerald-300 transition-colors"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={addTag}
        placeholder={placeholder}
        className="bg-white/5 border-white/10 focus:border-emerald-500/40"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof User;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-300 uppercase tracking-wider">
        <Icon className="h-4 w-4 text-emerald-400" />
        {title}
      </div>
      <div className="rounded-xl bg-white/[0.03] border border-white/5 p-4 space-y-4">
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export const SettingsModal = ({ isOpen, onClose, currentFullName }: SettingsModalProps) => {
  const { toast } = useToast();
  const { user, signOut } = useAuth();
  const isMobile = useIsMobile();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);

  // Form state
  const [fullName, setFullName] = useState(currentFullName || '');
  const [age, setAge] = useState<number | ''>('');
  const [gender, setGender] = useState('');
  const [weightKg, setWeightKg] = useState<number | ''>('');
  const [heightCm, setHeightCm] = useState<number | ''>('');
  const [activityLevel, setActivityLevel] = useState('');
  const [dietType, setDietType] = useState('');
  const [allergies, setAllergies] = useState<string[]>([]);
  const [dislikedFoods, setDislikedFoods] = useState<string[]>([]);
  const [favoriteFoods, setFavoriteFoods] = useState<string[]>([]);
  const [preferredCuisines, setPreferredCuisines] = useState<string[]>([]);
  const [maxPrepTime, setMaxPrepTime] = useState<number | ''>('');

  // Read-only calculated values
  const [bmr, setBmr] = useState<number | null>(null);
  const [tdee, setTdee] = useState<number | null>(null);
  const [targetCalories, setTargetCalories] = useState<number | null>(null);
  const [targetProtein, setTargetProtein] = useState<number | null>(null);
  const [targetCarbs, setTargetCarbs] = useState<number | null>(null);
  const [targetFat, setTargetFat] = useState<number | null>(null);

  // Fetch profile on open
  const fetchProfile = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from('user_profiles')
        .select('*')
        .eq('id', user.id)
        .single();

      if (error) throw error;
      if (!data) return;

      const p = data as UserProfile;
      setFullName(p.full_name || '');
      setAge(p.age ?? '');
      setGender(p.gender || '');
      setWeightKg(p.weight_kg ?? '');
      setHeightCm(p.height_cm ?? '');
      setActivityLevel(p.activity_level || '');
      setDietType(p.diet_type || '');
      setAllergies(p.allergies || []);
      setDislikedFoods(p.disliked_foods || []);
      setFavoriteFoods(p.favorite_foods || []);
      setPreferredCuisines(p.preferred_cuisines || []);
      setMaxPrepTime(p.max_prep_time ?? '');
      setBmr(p.bmr);
      setTdee(p.tdee);
      setTargetCalories(p.target_calories);
      setTargetProtein(p.target_protein_g);
      setTargetCarbs(p.target_carbs_g);
      setTargetFat(p.target_fat_g);
    } catch (err) {
      console.error('Error fetching profile:', err);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (isOpen) fetchProfile();
  }, [isOpen, fetchProfile]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    try {
      const { error: profileError } = await supabase
        .from('user_profiles')
        .update({
          full_name: fullName || null,
          age: age || null,
          gender: gender || null,
          weight_kg: weightKg || null,
          height_cm: heightCm || null,
          activity_level: activityLevel || null,
          diet_type: dietType || null,
          allergies,
          disliked_foods: dislikedFoods,
          favorite_foods: favoriteFoods,
          preferred_cuisines: preferredCuisines,
          max_prep_time: maxPrepTime || null,
          updated_at: new Date().toISOString(),
        })
        .eq('id', user.id);

      if (profileError) throw profileError;

      // Also update auth metadata for full_name
      if (fullName !== currentFullName) {
        await supabase.auth.updateUser({ data: { full_name: fullName } });
      }

      toast({
        title: 'Profil mis à jour',
        description: 'Vos modifications ont été enregistrées.',
      });
      onClose();
    } catch (err) {
      toast({
        title: 'Erreur',
        description: (err as Error)?.message || 'Impossible de sauvegarder le profil',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleRecalculate = async () => {
    if (!age || !gender || !weightKg || !heightCm || !activityLevel) {
      toast({
        title: 'Informations manquantes',
        description: 'Renseigne ton âge, genre, poids, taille et niveau d\'activité.',
        variant: 'destructive',
      });
      return;
    }
    setRecalculating(true);
    try {
      const result = await recalculateProfile({
        age: Number(age),
        gender,
        weight_kg: Number(weightKg),
        height_cm: Number(heightCm),
        activity_level: activityLevel,
      });
      setBmr(result.bmr);
      setTdee(result.tdee);
      setTargetCalories(result.target_calories);
      setTargetProtein(result.target_protein_g);
      setTargetCarbs(result.target_carbs_g);
      setTargetFat(result.target_fat_g);
      toast({
        title: 'Besoins recalculés',
        description: `${result.target_calories} kcal/jour — ${result.primary_goal}`,
      });
    } catch (err) {
      toast({
        title: 'Erreur de calcul',
        description: (err as Error)?.message || 'Impossible de recalculer',
        variant: 'destructive',
      });
    } finally {
      setRecalculating(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    onClose();
  };

  const hasBiometrics = age && gender && weightKg && heightCm && activityLevel;

  // ---------------------------------------------------------------------------
  // Content shared between Drawer & Dialog
  // ---------------------------------------------------------------------------

  const formContent = loading ? (
    <div className="space-y-6 p-1">
      {[1, 2, 3].map((i) => (
        <div key={i} className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ))}
    </div>
  ) : (
    <div className="space-y-6">
      {/* Section 1 — Identité */}
      <Section icon={User} title="Identité">
        <div className="space-y-1.5">
          <Label htmlFor="fullName" className="text-xs text-gray-400">Nom complet</Label>
          <Input
            id="fullName"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="bg-white/5 border-white/10 focus:border-emerald-500/40"
          />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Email</Label>
          <Input
            value={user?.email || ''}
            disabled
            className="bg-white/5 border-white/10 text-gray-500 cursor-not-allowed"
          />
        </div>
      </Section>

      {/* Section 2 — Biométrie */}
      <Section icon={Ruler} title="Biométrie">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs text-gray-400">Âge</Label>
            <Input
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value ? Number(e.target.value) : '')}
              placeholder="25"
              min={18}
              max={100}
              className="bg-white/5 border-white/10 focus:border-emerald-500/40"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-gray-400">Genre</Label>
            <Select value={gender} onValueChange={setGender}>
              <SelectTrigger className="bg-white/5 border-white/10 focus:border-emerald-500/40">
                <SelectValue placeholder="Choisir" />
              </SelectTrigger>
              <SelectContent>
                {GENDER_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-gray-400">Poids (kg)</Label>
            <Input
              type="number"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value ? Number(e.target.value) : '')}
              placeholder="75"
              min={40}
              className="bg-white/5 border-white/10 focus:border-emerald-500/40"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-gray-400">Taille (cm)</Label>
            <Input
              type="number"
              value={heightCm}
              onChange={(e) => setHeightCm(e.target.value ? Number(e.target.value) : '')}
              placeholder="178"
              min={100}
              className="bg-white/5 border-white/10 focus:border-emerald-500/40"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Niveau d'activité</Label>
          <Select value={activityLevel} onValueChange={setActivityLevel}>
            <SelectTrigger className="bg-white/5 border-white/10 focus:border-emerald-500/40">
              <SelectValue placeholder="Choisir" />
            </SelectTrigger>
            <SelectContent>
              {ACTIVITY_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </Section>

      {/* Section 3 — Objectifs & Macros */}
      <Section icon={Target} title="Objectifs & Macros">
        {targetCalories != null ? (
          <>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-white/[0.04] border border-white/5 py-2.5 px-2">
                <div className="text-lg font-bold text-emerald-400">{bmr}</div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">BMR</div>
              </div>
              <div className="rounded-lg bg-white/[0.04] border border-white/5 py-2.5 px-2">
                <div className="text-lg font-bold text-emerald-400">{tdee}</div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">TDEE</div>
              </div>
              <div className="rounded-lg bg-white/[0.04] border border-white/5 py-2.5 px-2">
                <div className="text-lg font-bold text-emerald-400">{targetCalories}</div>
                <div className="text-[10px] text-gray-500 uppercase tracking-wider">Cible kcal</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-blue-500/10 border border-blue-500/15 py-2 px-2">
                <div className="text-sm font-bold text-blue-400">{targetProtein}g</div>
                <div className="text-[10px] text-gray-500">Protéines</div>
              </div>
              <div className="rounded-lg bg-amber-500/10 border border-amber-500/15 py-2 px-2">
                <div className="text-sm font-bold text-amber-400">{targetCarbs}g</div>
                <div className="text-[10px] text-gray-500">Glucides</div>
              </div>
              <div className="rounded-lg bg-rose-500/10 border border-rose-500/15 py-2 px-2">
                <div className="text-sm font-bold text-rose-400">{targetFat}g</div>
                <div className="text-[10px] text-gray-500">Lipides</div>
              </div>
            </div>
          </>
        ) : (
          <p className="text-sm text-gray-500 text-center py-2">
            Renseigne tes infos biométriques puis clique Recalculer.
          </p>
        )}
        <Button
          type="button"
          variant="outline"
          className="w-full border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
          disabled={!hasBiometrics || recalculating}
          onClick={handleRecalculate}
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${recalculating ? 'animate-spin' : ''}`} />
          {recalculating ? 'Calcul en cours...' : 'Recalculer mes besoins'}
        </Button>
      </Section>

      {/* Section 4 — Préférences */}
      <Section icon={UtensilsCrossed} title="Préférences">
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Régime alimentaire</Label>
          <Select value={dietType} onValueChange={setDietType}>
            <SelectTrigger className="bg-white/5 border-white/10 focus:border-emerald-500/40">
              <SelectValue placeholder="Choisir" />
            </SelectTrigger>
            <SelectContent>
              {DIET_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Allergies</Label>
          <TagInput value={allergies} onChange={setAllergies} placeholder="Ex: arachides, lait..." />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Aliments détestés</Label>
          <TagInput value={dislikedFoods} onChange={setDislikedFoods} placeholder="Ex: choux de Bruxelles..." />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Aliments favoris</Label>
          <TagInput value={favoriteFoods} onChange={setFavoriteFoods} placeholder="Ex: saumon, avocat..." />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Cuisines préférées</Label>
          <TagInput value={preferredCuisines} onChange={setPreferredCuisines} placeholder="Ex: japonaise, italienne..." />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs text-gray-400">Temps de préparation max</Label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              value={maxPrepTime}
              onChange={(e) => setMaxPrepTime(e.target.value ? Number(e.target.value) : '')}
              placeholder="30"
              min={5}
              max={180}
              className="bg-white/5 border-white/10 focus:border-emerald-500/40 w-24"
            />
            <span className="text-sm text-gray-500">min</span>
          </div>
        </div>
      </Section>

      {/* Save button */}
      <Button
        onClick={handleSave}
        disabled={saving}
        className="w-full gradient-green text-white font-medium"
      >
        {saving ? 'Enregistrement...' : 'Enregistrer'}
      </Button>

      {/* Section 5 — Déconnexion */}
      <div className="pt-2 border-t border-white/5">
        <Button
          variant="outline"
          className="w-full border-red-500/30 text-red-400 hover:bg-red-500/10 hover:text-red-300"
          onClick={handleSignOut}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Se déconnecter
        </Button>
      </div>
    </div>
  );

  // ---------------------------------------------------------------------------
  // Render: Drawer on mobile, Dialog on desktop
  // ---------------------------------------------------------------------------

  if (isMobile) {
    return (
      <Drawer open={isOpen} onOpenChange={(open) => !open && onClose()}>
        <DrawerContent className="max-h-[90vh] glass-effect border-emerald-500/20">
          <DrawerHeader className="text-left">
            <DrawerTitle className="text-lg font-semibold">Mon profil</DrawerTitle>
          </DrawerHeader>
          <div className="overflow-y-auto px-4 pb-6">
            {formContent}
          </div>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[480px] max-h-[85vh] overflow-y-auto glass-effect border-emerald-500/20">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold">Mon profil</DialogTitle>
        </DialogHeader>
        {formContent}
      </DialogContent>
    </Dialog>
  );
};
