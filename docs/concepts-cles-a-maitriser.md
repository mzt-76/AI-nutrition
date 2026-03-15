# Concepts cles du projet — Ce que tu dois pouvoir expliquer

Ce document couvre les briques techniques que tu n'as pas forcement codees toi-meme
mais que tu dois comprendre pour expliquer ton projet en entretien ou a des amis.

---

## 1. MILP — L'optimiseur de portions (le plus important a comprendre)

### Le probleme qu'on resout

Tu as un plan de repas avec 3-4 recettes pour la journee. Chaque recette a des ingredients
avec des macros (proteines, glucides, lipides, calories). Le probleme :

> "Comment ajuster les quantites de chaque ingredient pour que le TOTAL de la journee
> atteigne exactement tes objectifs macro ?"

**Exemple concret :**
- Objectif : 2000 kcal, 150g proteines, 60g lipides, 200g glucides
- Repas : poulet riz brocoli (dejeuner) + saumon quinoa (diner) + yaourt granola (petit-dej)
- Chaque ingredient a un profil nutritionnel different
- Comment doser le poulet, le riz, l'huile, etc. pour tomber pile sur les cibles ?

### Pourquoi c'est un probleme d'optimisation

C'est exactement le meme type de probleme que dans l'energie :

| Energie | Nutrition |
|---------|-----------|
| Minimiser le cout de production | Minimiser l'ecart aux cibles macro |
| Variables : puissance de chaque centrale | Variables : quantite de chaque ingredient |
| Contrainte : satisfaire la demande | Contrainte : atteindre les cibles calories/proteines/etc. |
| Contrainte : limites min/max de production | Contrainte : bornes min/max par ingredient |
| Variable entiere : nombre de centrales allumees | Variable entiere : nombre d'oeufs (1, 2, 3 — pas 1.7) |

### MILP = Mixed Integer Linear Programming

**Mixed** : certaines variables sont continues (grammes de riz), d'autres entieres (nombre d'oeufs)
**Integer** : les oeufs, tranches de pain, etc. sont des nombres entiers
**Linear** : toutes les relations sont lineaires (2x plus de poulet = 2x plus de proteines)
**Programming** : "programmation" au sens mathematique = optimisation

### Comment ca marche dans notre code

```
Etape 1 : Preparer les variables
  Pour chaque ingredient de chaque recette, on cree une variable :
  - "poulet" → variable continue, bornes [0.5x, 2.0x] la quantite de base
  - "riz" → variable continue, bornes [0.5x, 2.0x]
  - "oeufs" → variable ENTIERE, bornes [1, 4] oeufs
  - "sel" → variable FIXE (on ne touche pas)

Etape 2 : Definir l'objectif
  Minimiser : |calories_reelles - calories_cibles|
            + |proteines_reelles - proteines_cibles|  (poids plus eleve)
            + |lipides_reels - lipides_cibles|
            + |glucides_reels - glucides_cibles|

  Les proteines ont un poids plus eleve car c'est la priorite #1 en nutrition sportive.

Etape 3 : Definir les contraintes
  - Bornes par ingredient : le poulet peut aller de 0.5x a 2x
  - Divergence : dans une meme recette, on ne veut pas x3 de poulet
    mais 0.5x de riz (ca ferait un plat bizarre) → max 2x d'ecart
  - Les oeufs sont des entiers

Etape 4 : Resoudre
  scipy.optimize.milp trouve la combinaison optimale en <10ms
  → "poulet: x1.3, riz: x0.9, brocoli: x1.1, oeufs: 2, huile: x0.6"

Etape 5 : Appliquer
  On recalcule les quantites et les macros resultantes
```

### Le role des ingredients (`ingredient_roles.py`)

Chaque ingredient a un role culinaire qui determine ses bornes :

| Role | Bornes | Exemples | Pourquoi |
|------|--------|----------|----------|
| `protein` | 0.5x – 2.0x | poulet, saumon, tofu | Large marge pour atteindre les cibles proteines |
| `starch` | 0.5x – 2.0x | riz, pates, quinoa | Ajustable pour les glucides |
| `vegetable` | 0.75x – 1.5x | brocoli, tomates | On ne veut pas 3x de brocoli |
| `fat_source` | 0.25x – 2.0x | huile, beurre | Tres ajustable (petit volume, gros impact calorique) |
| `fixed` | 1.0x | sel, poivre, epices | On ne touche pas |

### La contrainte de divergence

Sans cette contrainte, le solveur pourrait proposer : "200g de poulet + 30g de riz"
→ un plat desequilibre culinairement.

La contrainte dit : l'ecart moyen entre les groupes (proteine vs feculent vs legume)
ne doit pas depasser 2x. Si le poulet est a x1.5, le riz ne peut pas etre en dessous de x0.75.

### Ce que tu peux dire en entretien

> "J'ai implemente un optimiseur MILP qui ajuste les portions de chaque ingredient
> pour atteindre des cibles nutritionnelles quotidiennes. C'est de la programmation
> lineaire en nombres mixtes — les memes maths que pour l'optimisation de dispatching
> energetique ou de mix de production. J'utilise scipy.optimize.milp, avec des contraintes
> de coherence culinaire pour que les repas restent equilibres."

---

## 2. Pydantic AI — Le framework agent

### Ce que c'est

Un framework Python pour creer des agents IA (chatbots qui peuvent executer des actions).
C'est comme LangChain mais plus simple, type-safe, et base sur Pydantic (validation de donnees).

### Comment on l'utilise

```python
# On cree un agent avec un modele LLM et des outils
agent = Agent(model, system_prompt="Tu es un assistant nutrition...")

# On definit des outils que l'agent peut appeler
@agent.tool
def load_skill(ctx, skill_name: str) -> str:
    """Charge un skill (nutrition, meal-planning, etc.)"""
    ...

@agent.tool
def run_skill_script(ctx, skill_name: str, script_name: str, params: dict) -> str:
    """Execute un script de skill"""
    ...
```

### Le pattern skill

L'agent n'a que 6 outils fixes. Il n'a PAS un outil par fonctionnalite.
A la place, il charge des **skills** dynamiquement :

```
Utilisateur : "Fais-moi un plan repas pour la semaine"

Agent (LLM) : "C'est du meal-planning"
  → appelle load_skill("meal-planning")
  → lit le SKILL.md (documentation du skill)
  → appelle run_skill_script("meal-planning", "generate_week_plan", {days: 7})
  → le script s'execute et retourne le resultat
```

**Pourquoi ce pattern ?** Ajouter une fonctionnalite = creer un dossier dans `skills/`,
sans jamais toucher au code de l'agent. Separation des responsabilites.

### Ce que tu peux dire en entretien

> "L'architecture est un agent IA avec un systeme de skills modulaire. L'agent a 6 outils
> generiques et charge dynamiquement des skills specialises. Ajouter une fonctionnalite
> ne touche pas au code de l'agent — c'est un pattern plugin. Le framework est Pydantic AI,
> qui assure le typage fort des parametres d'outils."

---

## 3. Supabase + RLS — La base de donnees

### Ce que c'est

Supabase = PostgreSQL heberge + authentification + API auto-generee.
C'est une alternative open-source a Firebase.

### Row Level Security (RLS)

Le concept cle : **chaque ligne de la base sait a quel utilisateur elle appartient**,
et PostgreSQL REFUSE de renvoyer les lignes des autres utilisateurs.

```sql
-- Chaque plan repas a un user_id
CREATE TABLE meal_plans (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES user_profiles(id),
  plan_data JSONB,
  ...
);

-- RLS : un utilisateur ne voit QUE ses propres plans
CREATE POLICY "user_sees_own_plans" ON meal_plans
  FOR SELECT USING (auth.uid() = user_id);
```

**Pourquoi c'est important :** meme si le code backend a un bug, la base de donnees
elle-meme empeche l'acces aux donnees des autres. C'est une defense en profondeur.

### Notre architecture auth

```
Utilisateur → Frontend React → Supabase Auth (email/Google OAuth)
                                    ↓ JWT token
              Frontend → Backend FastAPI (verifie le JWT)
                                    ↓ user_id extrait du token
              Backend → Supabase DB (toutes les requetes filtrees par user_id)
```

### Ce que tu peux dire en entretien

> "La base est sur Supabase (PostgreSQL). L'authentification utilise Supabase Auth
> avec email et Google OAuth. Les donnees sont isolees par utilisateur via Row Level Security —
> c'est une politique de securite au niveau de la base, pas du code applicatif.
> Meme si le backend avait une faille, un utilisateur ne pourrait pas acceder
> aux donnees d'un autre."

---

## 4. Streaming NDJSON — La communication temps reel

### Le probleme

L'agent IA met 5-15 secondes a generer une reponse complete. Sans streaming,
l'utilisateur voit un spinner pendant 15 secondes puis TOUT le texte d'un coup.

### La solution : NDJSON (Newline Delimited JSON)

Le backend envoie les morceaux de reponse au fur et a mesure :

```
POST /api/agent  →  reponse en streaming

{"type": "text", "content": "Voici "}
{"type": "text", "content": "votre plan "}
{"type": "text", "content": "repas..."}
{"type": "ui_component", "component": "MacroGauges", "props": {...}}
{"type": "done", "conversation_id": "abc-123"}
```

Chaque ligne est un JSON independant. Le frontend les lit ligne par ligne
et affiche le texte progressivement (comme ChatGPT).

### Generative UI

En plus du texte, l'agent peut envoyer des **composants React** :
- `NutritionSummaryCard` : resume calorique
- `MacroGauges` : barres de progression proteines/glucides/lipides
- `MealCard` : une recette avec ingredients
- `DayPlanCard` : plan d'une journee complete

L'agent ecrit des marqueurs speciaux dans son texte (`<!--UI:MacroGauges:{...}-->`),
le backend les detecte et les envoie comme chunks `ui_component`,
et le frontend les rend comme de vrais composants interactifs.

### Ce que tu peux dire en entretien

> "La communication frontend-backend utilise du streaming NDJSON — le texte de l'agent
> s'affiche en temps reel, token par token. En plus du texte, j'ai implemente
> un systeme de Generative UI : l'agent peut emettre des composants React
> (graphiques macro, cartes recettes) directement dans la conversation.
> Le frontend les valide avec Zod avant de les rendre."

---

## 5. OpenFoodFacts — Les donnees nutritionnelles

### Ce que c'est

Une base de donnees open-source de produits alimentaires (comme Wikipedia pour la nourriture).
On l'utilise pour avoir les macros de chaque ingredient.

### Notre pipeline de donnees

```
OpenFoodFacts API (2M+ produits)
       ↓ import + nettoyage
Local DB : 264K produits (filtres, valides)
       ↓
ingredient_mapping : 1200+ mappings "ingredient" → "code OFF"
       ↓
Quand on cree une recette : chaque ingredient est lie a un produit OFF
→ on connait ses macros pour 100g → on peut calculer les macros de la recette
```

### Le controle qualite : Atwater check

Les donnees OpenFoodFacts sont souvent fausses (saisies par des utilisateurs).
On verifie avec la formule d'Atwater :

```
calories_attendues = proteines*4 + glucides*4 + lipides*9

Si |calories_declarees - calories_attendues| > 20% → on rejette le produit
```

C'est un filtre simple mais efficace : si quelqu'un a saisi 500 kcal pour un produit
qui a 10g de chaque macro (= 90 kcal attendues), on le detecte.

### Ce que tu peux dire en entretien

> "Les donnees nutritionnelles viennent d'OpenFoodFacts, une base open-source.
> J'ai importe 264K produits nettoyes avec un filtre Atwater pour rejeter
> les donnees incoherentes. Chaque ingredient de recette est lie a un produit
> valide, ce qui permet de calculer les macros exactes des portions ajustees."

---

## 6. Docker + Render — Le deploiement

Voir `docs/twa-digital-asset-links.md` pour la partie mobile (TWA/APK).

### Architecture de deploiement

```
GitHub (code source)
   ↓ git push
GitHub Actions (CI : lint + tests + build Docker)
   ↓ si tout passe
Render (hebergement)
   ├── Frontend : site statique (CDN) → pas de Docker, juste des fichiers HTML/JS/CSS
   └── Backend : container Docker (FastAPI, port 8001)
                       ↓
                  Supabase (PostgreSQL heberge)
```

### Pourquoi Docker pour le backend mais pas le frontend ?

- **Backend** : c'est un serveur Python qui tourne en continu → Docker garantit
  le meme environnement partout (dependances, version Python, etc.)
- **Frontend** : c'est juste des fichiers statiques apres le build (`npm run build`)
  → un CDN les sert plus vite, moins cher, sans cold start

### Ce que tu peux dire en entretien

> "Le backend est deploye en container Docker sur Render, le frontend en CDN statique.
> Le CI/CD est automatise avec GitHub Actions — 11 workflows (lint, tests, build Docker,
> securite, licences). L'app mobile est une TWA (Trusted Web Activity) qui emballe
> le site dans un APK Android avec verification Digital Asset Links."

---

## Resume : les 6 concepts a maitriser

| # | Concept | En une phrase | Fichier cle |
|---|---------|---------------|-------------|
| 1 | **MILP** | Optimisation mathematique des portions pour atteindre les cibles macro | `src/nutrition/portion_optimizer_v2.py` |
| 2 | **Pydantic AI + Skills** | Agent IA modulaire avec systeme de plugins | `src/agent.py` + `skills/` |
| 3 | **Supabase + RLS** | Base de donnees avec securite par ligne | `sql/0-all-tables.sql` |
| 4 | **Streaming NDJSON** | Communication temps reel + composants UI dans le chat | `src/api.py` + `src/ui_components.py` |
| 5 | **OpenFoodFacts** | Donnees nutritionnelles open-source avec controle qualite | `src/nutrition/openfoodfacts_client.py` |
| 6 | **Docker + Render** | Deploiement automatise backend container + frontend CDN | `Dockerfile` + `render.yaml` |
