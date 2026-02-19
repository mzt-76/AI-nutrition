# Format de Presentation du Plan de Repas

## Structure OBLIGATOIRE (strictement 2 niveaux)

### A. Resume global
- Nombre total de recettes uniques
- Temps de preparation moyen
- Securite allergenes (validation passee)

### B. Details COMPLETS pour 2 JOURS EXACTEMENT (Lundi ET Mardi)

Pour CHAQUE jour :
- Nom du jour et date
- **Pour CHAQUE repas/collation** :
  * Nom de la recette (creatif)
  * Liste complete des ingredients avec quantites ARRONDIES
  * Instructions de preparation (phrase complete)
  * Macros du repas (calories | proteines | glucides | lipides)
- Total quotidien (calories | proteines | glucides | lipides)

**JAMAIS afficher ce niveau de detail pour plus de 2 jours**

### C. ABSOLUMENT INTERDIT D'AFFICHER UN RESUME DES 5 AUTRES JOURS

- NE GENERE PAS : "Resume des 5 jours restants", "Les jours suivants"
- NE LISTE PAS les totaux caloriques des jours 3-7
- N'ECRIS RIEN sur les jours Mercredi a Dimanche

**SEULEMENT CE MESSAGE** :
```
---
Le plan complet des 7 jours (avec tous les details) est sauvegarde dans la base de donnees.
```

### D. Document Markdown
- Le tool retourne un champ `markdown_document` avec le chemin du fichier
- Mentionne : "Document complet telechargeable : [chemin_du_fichier.md]"

### E. Proposition explicite (APRES le message ci-dessus)
- "Veux-tu que je t'affiche les details d'un jour specifique ?"
- "Ou preferes-tu que je genere la liste de courses pour la semaine ?"

## Exemple Complet

```
Plan de 7 jours cree (6-12 janvier 2025)

Resume Hebdomadaire
- 21 recettes uniques
- Temps de preparation moyen : 35 min
- Structure : 3 repas complets

Securite Allergenes
Aucun allergene detecte

---

Lundi 6 Janvier

Petit-dejeuner (07:30) - Omelette aux epinards et toast avocat
- Ingredients : 3 oeufs, 50g epinards frais, 60g pain complet, 80g avocat
- Instructions : Battre les oeufs. Faire revenir les epinards. Cuire en omelette. Griller le pain, etaler l'avocat.
- Macros : 520 kcal | 28g proteines | 45g glucides | 24g lipides

Dejeuner (12:30) - Poulet grille et salade quinoa
- Ingredients : 150g poulet, 80g quinoa cuit, 100g tomates cerises, 50g concombre, 15ml huile d'olive
- Instructions : Griller le poulet. Cuire le quinoa. Melanger avec les legumes et l'huile d'olive.
- Macros : 680 kcal | 52g proteines | 55g glucides | 22g lipides

Diner (19:30) - Saumon au four avec legumes rotis
- Ingredients : 150g saumon, 100g brocoli, 100g carottes, 120g pommes de terre, 10ml huile d'olive
- Instructions : Prechauffer le four a 200C. Disposer saumon et legumes. Cuire 25 minutes.
- Macros : 620 kcal | 48g proteines | 45g glucides | 26g lipides

Total quotidien : 1820 kcal | 128g proteines | 145g glucides | 72g lipides

---

[Mardi avec meme niveau de detail...]

---

Le plan complet des 7 jours est sauvegarde dans la base de donnees.

Veux-tu que je t'affiche les details d'un jour specifique ?
Ou preferes-tu que je genere la liste de courses pour la semaine ?
```
