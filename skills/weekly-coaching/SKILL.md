---
name: weekly-coaching
description: Check-in hebdomadaire avec analyse de tendance, detection de patterns, et ajustements nutritionnels personnalises. Utiliser quand l'utilisateur fait un bilan de semaine ou rapporte son poids et adherence.
---

# Weekly Coaching - Check-in Hebdomadaire

## Quand utiliser

- L'utilisateur fait un bilan de semaine
- L'utilisateur rapporte son poids, adherence, ou bien-etre
- L'utilisateur mentionne fatigue, faim, stress, ou problemes de sommeil
- L'utilisateur demande des ajustements a son plan

## Workflow Complet

### 1. Collecte des donnees de feedback

**Essentielles** :
- Poids debut de semaine (kg) + Poids fin de semaine (kg)
- Pourcentage du plan suivi (0-100%)

**Facultatif mais recommande** :
- Faim : "low", "medium", "high"
- Energie : "low", "medium", "high"
- Sommeil : "poor", "fair", "good", "excellent"
- Envies/Cravings : Aliments particuliers recherches
- Notes libres : Observations qualitatives

### 2. Execute `calculate_weekly_adjustments`

Le script effectue l'analyse complete et retourne :
- **Analyse de tendance** : Poids change vs cible
- **Patterns detectes** : Adaptation metabolique, triggers d'adherence
- **Ajustements suggeres** : Calories (+/-), macros avec rationale
- **Alertes red flags** : Si fatigue intense, faim extreme, stress, perte trop rapide
- **Confiance** : Score base sur completude des donnees

### 3. Presente les resultats

- **Felicitations** si poids/adherence sur cible
- **Analyse honnete** si ecarts
- **Ajustements proposes** avec explications scientifiques
- **Red flags** selon severite (voir `references/red_flag_protocol.md`)

### 4. Adaptation personnalisee

- Si 4+ semaines de donnees : Utilise les patterns appris
- Si donnees incompletes : Explique que la confiance est plus basse
- Si red flags CRITICAL : **ARRETE tout** - Bien-etre mental > resultats physiques
- Si red flags WARNING : Ajustement petit et monitore

### 5. Demande confirmation

"Veux-tu que nous appliquions ces ajustements pour la semaine prochaine ?"

## Red Flag Protocol

Voir `references/red_flag_protocol.md` pour le protocole complet de severite.

## Outils de profil

- `fetch_my_profile` : Donnees du profil pour contexte

## Exécution

```python
# Bonne semaine
run_skill_script("weekly-coaching", "calculate_weekly_adjustments", {
    "weight_start_kg": 87.0, "weight_end_kg": 86.4,
    "adherence_percent": 85, "energy_level": "high", "sleep_quality": "good",
    "notes": "Bonne adherence, bien recupere"
})

# Semaine difficile
run_skill_script("weekly-coaching", "calculate_weekly_adjustments", {
    "weight_start_kg": 85.2, "weight_end_kg": 85.0,
    "adherence_percent": 60, "hunger_level": "high", "energy_level": "low",
    "notes": "Beaucoup de faim, difficile"
})
```

**Paramètres** :
- `weight_start_kg` (float, requis), `weight_end_kg` (float, requis)
- `adherence_percent` (int, requis) : 0-100
- `hunger_level` (str, défaut "medium") : "low", "medium", "high"
- `energy_level` (str, défaut "medium") : "low", "medium", "high"
- `sleep_quality` (str, défaut "good") : "poor", "fair", "good", "excellent"
- `cravings` (list[str], optionnel), `notes` (str, optionnel)

## Scripts disponibles

- `scripts/calculate_weekly_adjustments.py` : Validation → profil → historique → tendance poids → patterns → ajustements → red flags → stockage
