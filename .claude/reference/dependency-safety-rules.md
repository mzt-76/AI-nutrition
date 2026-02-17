# Règles de Sécurité des Dépendances

**IMPORTANT:** Ce document est lu automatiquement par Claude Code avant chaque session.

---

## 🚨 Règle Critique #1: API de Pydantic AI

### 1.1 AgentRunResult: Utiliser `result.data`

**TOUJOURS utiliser `result.data`, JAMAIS `result.output`**

#### ✅ CORRECT
```python
result = await agent.run(prompt, deps=deps)
response = result.data  # ✅ Utilise .data
```

#### ❌ INCORRECT (API OBSOLÈTE)
```python
result = await agent.run(prompt, deps=deps)
response = result.output  # ❌ OBSOLÈTE - Causera AttributeError
```

**Fichiers concernés:**
- `streamlit_ui.py` - Lignes 209 et 357
- Tous les fichiers de test (`test_*.py`)

**Historique:** Le 2026-01-04, `result.output` a été renommé en `result.data` dans pydantic-ai. Toujours utiliser `.data`.

---

### 1.2 Model: Utiliser `OpenAIModel`

**TOUJOURS utiliser `OpenAIModel`, JAMAIS `OpenAIChatModel`**

#### ✅ CORRECT
```python
from pydantic_ai.models.openai import OpenAIModel

model = OpenAIModel(
    "gpt-4o-mini",
    provider=OpenAIProvider(base_url=base_url, api_key=api_key)
)
```

#### ❌ INCORRECT (N'EXISTE PAS)
```python
from pydantic_ai.models.openai import OpenAIChatModel  # ❌ N'existe pas

model = OpenAIChatModel(...)  # ❌ Causera ImportError
```

**Fichier concerné:**
- `agent.py` - Ligne 14 (import) et ligne 77 (usage)

**Historique:** Dans pydantic-ai 0.0.53, la classe s'appelle `OpenAIModel`. Corrigé le 2026-01-29.

---

## 🔒 Règle Critique #2: Versions des Dépendances

**Les versions sont FIXÉES dans `requirements.txt` - NE PAS modifier sans tests**

### Dépendances Critiques (Ne Toucher Qu'en Cas de Nécessité)

| Dépendance | Version Actuelle | Impact si Cassé |
|------------|------------------|-----------------|
| `pydantic-ai` | 0.0.53 | 🔴 CRITIQUE - Agent ne fonctionne plus |
| `openai` | 1.71.0 | 🔴 CRITIQUE - Pas de génération LLM |
| `supabase` | 2.15.0 | 🔴 CRITIQUE - Pas d'accès DB |
| `streamlit` | 1.44.1 | 🟡 IMPORTANT - UI cassée |

### Avant de Mettre à Jour une Dépendance Critique

1. **Lire le CHANGELOG** sur GitHub (rechercher "BREAKING")
2. **Tester dans un environnement isolé** avant d'appliquer
3. **Exécuter TOUS les tests:** `pytest`
4. **Documenter les changements** dans le commit message

---

## ✅ Checklist Avant de Créer une Feature

### Quand Vous Modifiez du Code qui Utilise l'Agent

- [ ] Vérifier que vous utilisez `result.data` (pas `.output`)
- [ ] Si vous ajoutez un appel à `agent.run()`, suivre le pattern existant
- [ ] Tester avec Streamlit avant de commit

### Pattern Standard pour Agent.run()

```python
# Pattern à suivre (voir agent.py ligne 540 ou streamlit_ui.py ligne 209)
async def get_response():
    result = await agent.run(prompt, deps=agent_deps)
    return result.data  # ✅ Toujours .data

response = asyncio.run(get_response())
```

---

## 🛠️ Que Faire si Vous Voyez une Erreur de Dépendance

### Erreur: `'AgentRunResult' object has no attribute 'output'`

**Cause:** Code utilise l'ancienne API pydantic-ai

**Solution:**
```bash
# Chercher toutes les occurrences
grep -rn "result.output" *.py

# Remplacer par result.data
sed -i 's/result\.output/result.data/g' fichier.py
```

### Erreur: `ModuleNotFoundError` après `pip install`

**Cause:** Dépendance manquante ou version incorrecte

**Solution:**
```bash
# Réinstaller depuis requirements.txt (from project root)
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📚 Références Utiles

- **CLAUDE.md** - Guide de développement complet
- **agent.py ligne 540** - Exemple correct d'utilisation de `result.data`
- **streamlit_ui.py lignes 207-209** - Pattern async standard

---

**Dernière mise à jour:** 2026-01-29
**Raison:** Correction `OpenAIChatModel` → `OpenAIModel` (n'existait pas)
