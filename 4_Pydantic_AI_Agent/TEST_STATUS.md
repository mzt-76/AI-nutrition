# État des Tests - AI Nutrition Assistant

**Dernière mise à jour:** 31 décembre 2025

---

## ✅ Tests Réussis

### Tool 7: Génération de Plan Alimentaire Hebdomadaire

**Tests passés:**
- ✅ **Présentation format** : Le plan s'affiche sous forme de résumé (1 ligne/jour) au lieu des détails complets
- ✅ **Génération 7 jours** : Les 7 jours sont générés complètement (validation ajoutée)
- ✅ **Sécurité allergènes** : Zéro violation détectée avec mapping explicite (arachides, fruits à coque)
- ✅ **Structure JSON** : Format validé, pas de commentaires, apostrophes échappées
- ✅ **Stockage BDD** : Les plans sont sauvegardés correctement dans Supabase

**Améliorations implémentées:**
1. **nutrition/meal_planning.py (lignes 125-170)** : Mapping explicite des allergènes avec alternatives sûres
2. **nutrition/meal_planning.py (lignes 222-250)** : Répartition protéines obligatoire par repas avec tableau détaillé
3. **nutrition/meal_planning.py (lignes 252-265)** : Répartition calories par repas (20% petit-déj, 35% déj, etc.)
4. **nutrition/meal_planning.py (lignes 274-293)** : Checklist de vérification finale avant génération JSON
5. **prompt.py (lignes 258-287)** : Instructions explicites DO/DON'T pour format de présentation
6. **tools.py (ligne 750)** : max_tokens augmenté de 4000 → 12000 pour plans complets
7. **tools.py (lignes 771-782)** : Validation rejette plans < 7 jours
8. **test_meal_plan_agent.py** : Script de test automatisé end-to-end

---

## ⚠️ Tests en Cours / Problèmes Identifiés

### Tool 7: Génération de Plan Alimentaire Hebdomadaire

**🔴 PROBLÈME CRITIQUE - Cohérence Macros avec Profil**

**Symptômes:**
- Calories générées : ~2080-2200 kcal vs cible 2474 kcal (écart -10% à -15%)
- Protéines générées : ~80-130g vs cible 156g (écart -16% à -48%)
- Lipides trop élevés : +47% à +72% au-dessus de la cible
- Glucides parfois trop élevés : +16% à +38% au-dessus de la cible

**Impact:**
- Plan inadapté pour prise de muscle (déficit protéique critique)
- Risque d'abandon utilisateur si objectifs non atteints
- Perte de confiance dans les recommandations IA

**Actions prises:**
- ✅ Ajout d'instructions explicites avec répartition macro par repas
- ✅ Tableau de distribution protéines (35-40g petit-déj, 45-50g déj, etc.)
- ✅ Liste d'aliments riches en protéines avec valeurs nutritionnelles
- ✅ Checklist de vérification finale avant génération

**Statut:** Améliorations déployées, **TESTS REQUIS** pour valider efficacité

**Prochaines étapes si problème persiste:**
1. **Option A - Post-processing:** Ajouter un système d'ajustement automatique après génération
   - Calculer déficit macro
   - Suggérer ajout d'aliments spécifiques (shaker protéine, portion viande)
   - Avantages : Garantit précision
   - Inconvénients : Complexité accrue

2. **Option B - Retry intelligent:** Régénérer avec instructions ajustées si validation échoue
   - Détecte macro déficient
   - Régénère avec instruction "AUGMENTE portions de [poulet/œufs/etc.]"
   - Avantages : Maintient réalisme recettes
   - Inconvénients : Augmente temps de réponse

3. **Option C - Modèle différent:** Tester GPT-4o-mini vs GPT-4o
   - GPT-4o peut être trop créatif, privilégie réalisme sur précision
   - GPT-4o-mini peut être plus obéissant aux instructions numériques
   - Test A/B recommandé

---

**🔴 PROBLÈME CRITIQUE - Temps de Réponse Supérieur à 3 Minutes**

**Symptômes:**
- Génération complète : 2-4 minutes en moyenne
- Utilisateur voit "Je réfléchis..." sans feedback intermédiaire
- Risque de timeout frontend ou perception de blocage

**Causes identifiées:**
1. **GPT-4o JSON mode avec 7 jours détaillés** : Génération 12000 tokens peut prendre 60-90 secondes
2. **Validation multi-passes** : Allergen check + macro check + structure check
3. **RAG retrieval** : Fetch documents scientifiques (ajoute ~5-10 secondes)
4. **Retry logic** : Si JSON invalide ou allergen violation, recommence (peut doubler le temps)

**Impact:**
- Mauvaise UX (utilisateur pense que ça plante)
- Risque de timeouts HTTP
- Abandon avant résultat

**Actions recommandées:**

**COURT TERME (MVP):**
1. **Ajouter feedback intermédiaire dans Streamlit:**
   ```python
   with st.spinner("🔍 Analyse de votre profil..."):
       # Fetch profile
   with st.spinner("📚 Recherche de recommandations scientifiques..."):
       # RAG retrieval
   with st.spinner("🍳 Génération de vos recettes personnalisées (2-3 min)..."):
       # GPT-4o generation
   ```

2. **Optimiser RAG retrieval:**
   - Cache les documents fréquents (meal planning, protein timing)
   - Réduit match_count de 4 → 2 documents

3. **Streaming partiel:**
   - Afficher "Jour 1 généré... Jour 2 généré..." si possible avec GPT-4o streaming

**MOYEN TERME (Phase 2):**
1. **Background job avec polling:**
   - Tool déclenche job asynchrone
   - Frontend poll toutes les 5 secondes
   - Affiche progress bar réaliste

2. **Pré-génération intelligente:**
   - Génère plans types pour profils communs
   - Ajuste à la volée pour personnalisation
   - Réduit temps de 3 min → 30 sec

3. **Architecture multi-étapes:**
   - Étape 1: Génère structure (30 sec)
   - Étape 2: Remplit recettes par batch (3x 30 sec = 90 sec total)
   - Affiche résultats progressivement

**Statut:** **INVESTIGATION REQUISE** - Mesurer temps par étape pour identifier bottleneck exact

---

**🟡 INVESTIGATION REQUISE - Architecture Tool vs LLM Formatting**

**Question à clarifier:**
Le formatage final (résumé 1 ligne/jour) est-il fait par:
- **A) Le tool lui-même** (tools.py retourne résumé formaté) ?
- **B) L'agent LLM** (tool retourne JSON complet, agent le formate selon prompt.py) ?

**État actuel:**
- Tool retourne : JSON complet avec tous les détails
- Agent reçoit : JSON + instructions prompt.py (lignes 258-287)
- Agent affiche : Résumé formaté (suite aux instructions)

**Architecture actuelle = OPTION B**

**Avantages:**
- ✅ Séparation des responsabilités (tool = data, agent = présentation)
- ✅ Flexibilité (agent peut choisir format selon contexte)
- ✅ Réutilisabilité (même tool pour différents agents)

**Inconvénients:**
- ❌ Agent peut ignorer instructions de formatage
- ❌ Pas de garantie absolue sur présentation
- ❌ Debug difficile (qui est responsable du format final ?)

**Architecture alternative - OPTION A (Post-processing in tool):**

```python
# Dans tools.py, après validation
if presentation_mode == "summary":
    formatted_response = format_meal_plan_summary(meal_plan_json)
    return json.dumps({"summary": formatted_response, "full_plan_id": plan_id})
else:
    return json.dumps(meal_plan_json)
```

**Recommandation:** Documenter choix actuel (Option B), tester stabilité sur 10+ générations

---

## 🔄 Tests Restants

### Tool 8: Génération de Liste de Courses

**Statut:** ❌ **NON TESTÉ**

**Tests à effectuer:**
1. Générer un plan hebdomadaire
2. Appeler `generate_shopping_list(week_start="2025-12-23")`
3. Vérifier :
   - ✅ Tous les ingrédients sont listés
   - ✅ Quantités agrégées correctement (ex: 500g poulet lundi + 300g jeudi = 800g total)
   - ✅ Catégorisation (Protéines, Légumes, Féculents, etc.)
   - ✅ Pas d'ingrédients allergènes
   - ✅ Format exploitable (Markdown ou JSON structuré)

**Critères de succès:**
- Liste complète en < 30 secondes
- Zéro allergènes
- Groupement intelligent (pas de doublons)

**Priorité:** 🔴 HAUTE (fonctionnalité demandée par utilisateur)

---

### Tool 9: Ajustements Hebdomadaires (Weekly Feedback)

**Statut:** ⚠️ **PARTIELLEMENT TESTÉ** (tests unitaires OK, test end-to-end manquant)

**Tests à effectuer:**
1. Simuler 4 semaines de check-ins
2. Vérifier détection patterns (hunger, energy, adherence)
3. Vérifier red flags (rapid loss, extreme hunger, etc.)
4. Valider apprentissage continu (learning profile update)

**Priorité:** 🟡 MOYENNE (MVP Phase 2)

---

## 📋 Checklist Validation Globale

**Avant mise en production:**

- [ ] **Performance:**
  - [ ] Temps de réponse moyen < 2 minutes pour plan hebdo
  - [ ] 95% des requêtes < 3 minutes
  - [ ] Aucun timeout observé sur 100 tests

- [ ] **Qualité Nutritionnelle:**
  - [ ] 90% des plans dans tolérance macro (±10%)
  - [ ] 100% zéro allergen violations
  - [ ] Validation nutritionniste externe sur 10 plans

- [ ] **UX:**
  - [ ] Format de présentation cohérent sur 100 générations
  - [ ] Feedback intermédiaire pour longues opérations
  - [ ] Messages d'erreur clairs et actionnables

- [ ] **Tests automatisés:**
  - [x] test_meal_plan_agent.py (format, allergènes, 7 jours)
  - [ ] test_shopping_list.py
  - [ ] test_weekly_adjustments_e2e.py
  - [ ] test_performance_benchmarks.py (temps de réponse)

---

## 🎯 Recommandations Prioritaires

**Top 3 Actions Immédiates:**

1. **🔴 CRITIQUE - Résoudre incohérence macros:**
   - Tester efficacité nouvelles instructions (10 générations)
   - Si < 70% de succès → implémenter post-processing (Option A)
   - Documenter résultats dans ce fichier

2. **🔴 CRITIQUE - Améliorer feedback temps de réponse:**
   - Implémenter spinners Streamlit avec étapes
   - Mesurer temps par composant (profiling)
   - Target : perception utilisateur < 2 min

3. **🟡 IMPORTANT - Valider shopping list:**
   - Créer test_shopping_list.py
   - Exécuter 5 scénarios (plan simple, plan complexe, allergies multiples)
   - Valider format + complétude

---

**Fichier maintenu par:** Claude Code (AI Assistant)
**Contact issues:** /mnt/c/Users/meuze/AI-nutrition/.github/issues (si configuré)
