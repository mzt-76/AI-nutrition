---
name: nutrition-calculating
description: Calculs nutritionnels (BMR, TDEE, macros) avec inference automatique des objectifs. Utiliser quand l'utilisateur demande ses besoins caloriques ou nutritionnels.
---

# Nutrition Calculating - Calculs de Besoins

## Quand utiliser

- L'utilisateur demande un calcul de besoins nutritionnels
- L'utilisateur fournit des donnees biometriques (age, poids, taille)
- L'utilisateur mentionne un objectif (prise de muscle, perte de poids)
- Apres modification des objectifs dans le profil

## Workflow

1. Verifie si les donnees biometriques sont dans le profil (via `fetch_my_profile`)
2. Si donnees manquantes ET utilisateur les fournit dans son message : Appelle `update_my_profile` pour sauvegarder
3. **Gestion des Objectifs** :
   - Si objectifs definis dans le profil (champ `goals` non-null) : Utilise-les
   - Si l'utilisateur mentionne un objectif dans son message : Infere automatiquement (ex: "je veux prendre du muscle" -> muscle_gain)
   - **Si AUCUN objectif defini ET aucun contexte** : Utilise **"Sante/Maintenance"** (maintenance: 7) et explique :
     * "J'ai utilise un objectif de maintenance (sante generale) par defaut"
     * "Si tu as un objectif specifique (perte de poids, prise de muscle, performance), dis-le moi pour recalculer !"
4. Utilise `calculate_nutritional_needs` avec les donnees (profil OU message utilisateur)
5. Explique les resultats (BMR, TDEE, cible calorique, macros)
6. Fournis des conseils pratiques d'application
7. **APRES LE CALCUL** :
   - Propose TOUJOURS de generer un plan alimentaire : "Veux-tu que je genere un plan de repas hebdomadaire base sur ces cibles ?"
   - **SI l'utilisateur confirme** : NE RECALCULE PAS les macros, PASSE DIRECTEMENT a la generation du plan

**RAPPEL** : Quand l'utilisateur dit "23 ans, homme, 86kg, 191cm, sedentaire", tu DOIS extraire ces donnees et les sauvegarder avec `update_my_profile` avant de calculer.

## Outils de profil

- `fetch_my_profile` : Recuperer donnees existantes
- `update_my_profile` : Sauvegarder nouvelles donnees

## Exécution

```python
# Prise de masse
run_skill_script("nutrition-calculating", "calculate_nutritional_needs", {
    "age": 35, "gender": "male", "weight_kg": 87, "height_cm": 178,
    "activity_level": "moderate", "context": "objectif prise de masse"
})
# -> target_calories = TDEE + 300

# Perte de poids
run_skill_script("nutrition-calculating", "calculate_nutritional_needs", {
    "age": 28, "gender": "female", "weight_kg": 65, "height_cm": 165,
    "activity_level": "moderate", "context": "perdre du poids"
})
# -> target_calories = TDEE - 500
```

**Paramètres** :
- `age` (int, requis) : 18-100
- `gender` (str, requis) : "male" ou "female"
- `weight_kg` (float, requis)
- `height_cm` (int, requis)
- `activity_level` (str, requis) : sedentary, light, moderate, active, very_active
- `goals` (dict, optionnel) : Scores 0-10 → weight_loss, muscle_gain, performance, maintenance
- `activities` (list[str], optionnel) : Ex: ["musculation", "basket"]
- `context` (str, **CRITIQUE**) : Texte utilisateur pour inférence automatique des objectifs. Sans context → maintenance.

**Scripts disponibles** :
- `scripts/calculate_nutritional_needs.py` : BMR (Mifflin-St Jeor) → TDEE → inférence objectifs → macros

## References

- `references/formulas.md` : Detail des formules Mifflin-St Jeor et recommandations ISSN
