# Workflow automatisé de gestion des bugs

## Vue d'ensemble

Trois GitHub Actions travaillent ensemble pour détecter, diagnostiquer, discuter et corriger les bugs automatiquement via Claude Code.

```
┌─────────────────┐     label ajouté      ┌──────────────────────┐
│  Tu crées une   │ ──────────────────────▶│  Niveau 1: Enquête   │
│  issue GitHub   │   "user-feedback"      │  (investigate-bug)   │
└─────────────────┘                        └──────────┬───────────┘
                                                      │
                                           Diagnostic + plan posté
                                           en commentaire sur l'issue
                                                      │
                                                      ▼
┌─────────────────┐   tu commentes         ┌──────────────────────┐
│  Tu discutes,   │ ──────────────────────▶│  Bug Assistant       │
│  poses des      │   (n'importe quoi)     │  (fix-bug)           │
│  questions      │                        │  → répond, ajuste    │
└─────────────────┘                        └──────────────────────┘
                                                      │
┌─────────────────┐   /fix                            │
│  Tu valides     │ ──────────────────────▶  Claude implémente    │
│  le plan        │                        │  le fix + crée PR    │
└─────────────────┘                        └──────────────────────┘

┌─────────────────┐   cron: */2 jours      ┌──────────────────────┐
│  Automatique    │ ──────────────────────▶│  Niveau 2: Monitoring│
│  (pas d'action  │   06:00 UTC            │  (proactive-monit.)  │
│   de ta part)   │                        │  → scan Langfuse +   │
└─────────────────┘                        │    Supabase          │
                                           └──────────────────────┘
```

---

## Les 3 workflows

### 1. `investigate-bug.yml` — Enquête automatique

**Déclencheur :** Label `user-feedback` ajouté sur une issue

**Ce que fait Claude :**
1. Lit la description de l'issue
2. Décide s'il a besoin de données (Langfuse, Supabase) ou juste d'analyser le code
3. Analyse le code source pour trouver la cause racine
4. Poste un commentaire avec :
   - **Diagnostic** : cause racine, fichiers concernés, lignes de code
   - **Sévérité** : critical / high / medium / low
   - **Plan d'implémentation** : étapes précises pour corriger

**Temps :** ~5-7 minutes

---

### 2. `fix-bug.yml` — Assistant conversationnel + /fix

**Déclencheur :** N'importe quel commentaire sur une issue `user-feedback`

**Deux modes :**

#### Mode conversation (commentaire normal)
Tu commentes → Claude répond. Tu peux :
- Poser des questions sur le diagnostic
- Donner du feedback ("je pense que c'est plutôt X")
- Demander de préciser le plan
- Claude ajuste son analyse et reposte un plan mis à jour

#### Mode fix (`/fix`)
Tu commentes `/fix` → Claude :
1. Lit le plan d'implémentation validé
2. Crée une branche `fix/issue-<number>`
3. Implémente le fix
4. Lance les linters + tests
5. Crée une PR qui référence l'issue
6. Poste un lien vers la PR sur l'issue

**Temps :** ~5-12 minutes selon la complexité

---

### 3. `proactive-monitoring.yml` — Surveillance proactive (Niveau 2)

**Déclencheur :** Cron automatique tous les 2 jours à 06:00 UTC + déclenchement manuel possible

**Ce que fait Claude :**
1. Lance `scripts/investigate_bugs.py --langfuse --supabase --hours 48`
2. Analyse les traces d'erreur, la latence, les conversations abandonnées
3. Si anomalies détectées → crée des issues avec le label `auto-detected`
4. Si tout va bien → poste un résumé "all clear" sur l'issue de monitoring (#2)

**Temps :** ~5-10 minutes

---

## Guide d'utilisation

### Reporter un bug (depuis ton téléphone)

1. Va sur https://github.com/mzt-76/AI-nutrition/issues/new/choose
2. Choisis **"User Feedback / Bug Report"**
3. Remplis le formulaire :
   - **What happened?** — décris le bug (obligatoire)
   - **Session ID** — si tu l'as (optionnel)
   - **When** — quand c'est arrivé (optionnel)
   - **Area** — quel domaine (optionnel)
4. Le label `user-feedback` est ajouté automatiquement
5. **Attends ~7 min** → Claude poste son diagnostic

### Discuter du diagnostic

Commente directement sur l'issue comme si tu parlais à un développeur :
- "Est-ce que ça pourrait aussi affecter la page Suivi du Jour ?"
- "Je pense que le problème vient plutôt de l'API, pas du frontend"
- "Ajoute aussi un test pour ce cas"

Claude lit tous les commentaires précédents et répond en contexte.

### Valider et lancer le fix

Quand le plan te convient, commente :
```
/fix
```

Claude crée une PR. Tu la review et merge depuis GitHub.

### Déclencher le monitoring manuellement

1. Va sur https://github.com/mzt-76/AI-nutrition/actions
2. Choisis **"Proactive Monitoring (Niveau 2)"**
3. Clique **"Run workflow"**

---

## Script de données : `scripts/investigate_bugs.py`

Script Python (LLM-free) qui fetch les données de diagnostic. Utilisé par les workflows, mais tu peux aussi le lancer manuellement :

```bash
# Voir les erreurs Langfuse des dernières 24h
PYTHONPATH=. python scripts/investigate_bugs.py --langfuse --hours 24

# Voir les conversations Supabase récentes
PYTHONPATH=. python scripts/investigate_bugs.py --supabase --hours 24

# Investiguer une session spécifique
PYTHONPATH=. python scripts/investigate_bugs.py --langfuse --supabase --session-id "user-uuid~3"

# Sans flags = rapport vide (valide JSON)
PYTHONPATH=. python scripts/investigate_bugs.py
```

**Flags :**
| Flag | Description |
|------|-------------|
| `--langfuse` | Query les traces Langfuse |
| `--supabase` | Query les conversations Supabase |
| `--hours N` | Fenêtre de temps (défaut: 24h) |
| `--session-id ID` | Investigation ciblée sur une session |
| `--user-id ID` | Filtrer par utilisateur |
| `--format json\|text` | Format de sortie (défaut: json) |

---

## Secrets GitHub requis

| Secret | Description | Source |
|--------|-------------|--------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Auth Claude Code (abonnement Max) | `claude setup-token` |
| `LANGFUSE_PUBLIC_KEY` | Clé publique Langfuse | Dashboard Langfuse |
| `LANGFUSE_SECRET_KEY` | Clé secrète Langfuse | Dashboard Langfuse |
| `SUPABASE_URL` | URL du projet Supabase | Dashboard Supabase |
| `SUPABASE_SERVICE_KEY` | Clé service Supabase | Dashboard Supabase |

Pour ajouter/mettre à jour un secret :
```bash
gh secret set NOM_DU_SECRET --repo mzt-76/AI-nutrition
```

---

## Labels GitHub

| Label | Couleur | Utilisé par |
|-------|---------|-------------|
| `user-feedback` | rouge | Déclenche l'enquête (Niveau 1) |
| `auto-detected` | jaune | Ajouté par le monitoring (Niveau 2) |
| `monitoring` | vert | Issue de suivi santé (#2) |

---

## Modifier / améliorer les workflows

### Changer le prompt d'investigation
Édite `.github/workflows/investigate-bug.yml`, section `prompt:` du step "Investigate bug".

### Changer le comportement de l'assistant
Édite `.github/workflows/fix-bug.yml`, section `prompt:` du step "Respond to comment".

### Changer la fréquence du monitoring
Édite `.github/workflows/proactive-monitoring.yml`, ligne `cron:` :
```yaml
# Tous les jours à 6h
- cron: "0 6 * * *"
# Tous les 2 jours à 6h (actuel)
- cron: "0 6 */2 * *"
# Tous les lundis à 8h
- cron: "0 8 * * 1"
```

### Ajouter des outils autorisés pour Claude
Modifie `claude_args` → `--allowedTools` dans le workflow concerné. Format :
```
"Bash(commande*),Read,Edit,Write,Glob,Grep"
```

### Ajouter un nouveau type de données au script
Édite `scripts/investigate_bugs.py` :
1. Ajoute une nouvelle fonction `fetch_*()`
2. Ajoute un flag CLI dans `main()`
3. Intègre dans `build_report()`
4. Ajoute des tests dans `tests/test_investigate_bugs.py`
5. Mets à jour le prompt du workflow pour utiliser le nouveau flag

### Renouveler le token OAuth Claude
```bash
claude setup-token
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo mzt-76/AI-nutrition
```

---

## Architecture

```
.github/
├── ISSUE_TEMPLATE/
│   └── user-feedback.yml        # Formulaire de bug report
└── workflows/
    ├── investigate-bug.yml      # Niveau 1: enquête (label trigger)
    ├── fix-bug.yml              # Assistant conversationnel + /fix
    └── proactive-monitoring.yml # Niveau 2: scan cron 48h

scripts/
└── investigate_bugs.py          # Data fetcher (Langfuse + Supabase)

tests/
└── test_investigate_bugs.py     # 20 tests unitaires (mocked, CI-safe)
```
