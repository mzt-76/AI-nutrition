# Règles de Sécurité des Dépendances

**IMPORTANT:** Ce document est lu automatiquement par Claude Code avant chaque session.

---

## 🚨 Règle Critique #1: API de Pydantic AI

### 1.1 AgentRunResult: Utiliser `result.output`

**TOUJOURS utiliser `result.output`, JAMAIS `result.data`**

#### ✅ CORRECT (pydantic-ai 1.x)
```python
result = await agent.run(prompt, deps=deps)
response = result.output  # ✅ Champ dataclass dans 1.39.0
```

#### ❌ INCORRECT (ancienne API 0.0.x — n'existe plus)
```python
result = await agent.run(prompt, deps=deps)
response = result.data  # ❌ AttributeError dans pydantic-ai 1.x
```

**Fichiers concernés:**
- `tests/test_user_stories_e2e.py` — utilise `result.output` ✅
- Tous les nouveaux fichiers de test

**Historique:** En pydantic-ai 0.0.x, l'attribut s'appelait `.data`. Depuis la montée en version 1.x, c'est `.output` (champ dataclass défini dans `AgentRunResult`). La règle précédente (2026-01-04) était valide pour 0.0.53 — elle est obsolète depuis l'upgrade à 1.39.0.

---

### 1.2 Model: Utiliser `OpenAIChatModel`

**TOUJOURS utiliser `OpenAIChatModel` — c'est le nom explicite et stable dans 1.x**

#### ✅ CORRECT (pydantic-ai 1.39.0)
```python
from pydantic_ai.models.openai import OpenAIChatModel

model = OpenAIChatModel(
    "gpt-4o-mini",
    provider=OpenAIProvider(base_url=base_url, api_key=api_key)
)
```

#### ⚠️ FONCTIONNE MAIS DÉCONSEILLÉ
```python
from pydantic_ai.models.openai import OpenAIModel  # Alias encore présent en 1.39.0
# Préférer OpenAIChatModel pour la clarté sémantique
```

**Fichier concerné:**
- `src/agent.py` — import ligne 20 et usage dans `get_model()` ✅

**Historique:** En pydantic-ai 0.0.53, seul `OpenAIModel` existait. En 1.39.0, `OpenAIChatModel` est le nom préféré (plus explicite). `OpenAIModel` existe encore comme alias. La règle précédente (2026-01-29) qui disait "OpenAIChatModel n'existe pas" était valide pour 0.0.53 uniquement — elle est obsolète depuis l'upgrade à 1.39.0.

---

### 1.3 FunctionModel: Pattern pour les tests E2E

Pour tester l'agent sans appeler un vrai LLM, utiliser `FunctionModel` :

```python
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart

def my_model(messages, info) -> ModelResponse:
    if len(messages) == 1:           # Premier appel → faire un tool call
        return ModelResponse(parts=[
            ToolCallPart("tool_name", {"param": "value"})
        ])
    return ModelResponse(parts=[TextPart("Réponse finale.")])  # Après résultat outil

with agent.override(model=FunctionModel(my_model)):
    result = await agent.run("message", deps=deps)
```

**Utilisé dans:** `tests/test_user_stories_e2e.py` — 3 tests unitaires (US-1, US-7, US-8)

---

## 🔒 Règle Critique #2: Versions des Dépendances

**Les versions sont FIXÉES dans `requirements.txt` - NE PAS modifier sans tests**

### Dépendances Critiques (Ne Toucher Qu'en Cas de Nécessité)

| Dépendance | Version Installée | Impact si Cassé |
|------------|-------------------|-----------------|
| `pydantic-ai` | **1.39.0** | 🔴 CRITIQUE - Agent ne fonctionne plus |
| `openai` | **2.14.0** | 🔴 CRITIQUE - Pas de génération LLM |
| `anthropic` | **0.75.0** | 🔴 CRITIQUE - Pas de génération recettes |
| `supabase` | 2.15.0 | 🔴 CRITIQUE - Pas d'accès DB |

### Modèles Claude (skills meal-planning)

| Usage | Modèle |
|-------|--------|
| `generate_custom_recipe.py` | `claude-sonnet-4-6` |
| `seed_recipe_db.py` | `claude-sonnet-4-6` |

### Avant de Mettre à Jour une Dépendance Critique

1. **Lire le CHANGELOG** sur GitHub (rechercher "BREAKING")
2. **Tester dans un environnement isolé** avant d'appliquer
3. **Exécuter TOUS les tests:** `pytest tests/ evals/ -m "not integration"`
4. **Documenter les changements** dans ce fichier et dans le commit message

---

## 🧪 Checklist Avant de Créer une Feature

### Quand Vous Modifiez du Code qui Utilise l'Agent

- [ ] Vérifier que vous utilisez `result.output` (pas `.data`)
- [ ] Si vous ajoutez un tool, utiliser `goals: dict[str, int] | None = None` (pas `dict` nu)
- [ ] Tester avec `FunctionModel` avant de faire des appels réels au LLM
- [ ] Vérifier que le mock Supabase retourne des vrais dicts (pas des `MagicMock`)

### Pattern Standard pour Agent.run()

```python
async def get_response():
    result = await agent.run(prompt, deps=agent_deps)
    return result.output  # ✅ Toujours .output en pydantic-ai 1.x
```

### Pattern Standard pour Mock Supabase dans les Tests

```python
def _make_supabase_mock(profile: dict | None = None) -> MagicMock:
    mock = MagicMock()
    result = MagicMock()
    result.data = [profile] if profile else []
    chain = mock.table.return_value
    chain.select.return_value.limit.return_value.execute.return_value = result
    chain.update.return_value.eq.return_value.execute.return_value = result
    chain.insert.return_value.execute.return_value = result
    return mock
```

---

## 🛠️ Que Faire si Vous Voyez une Erreur de Dépendance

### Erreur: `'AgentRunResult' object has no attribute 'data'`

**Cause:** Code utilise l'ancienne API pydantic-ai 0.0.x

**Solution:**
```bash
grep -rn "result\.data" tests/ src/
# Remplacer par result.output
```

### Erreur: `ImportError: cannot import name 'OpenAIModel'`

**Cause:** Version de pydantic-ai trop ancienne (< 1.x) ou nom retiré

**Solution:**
```python
from pydantic_ai.models.openai import OpenAIChatModel  # Toujours disponible en 1.x
```

### Erreur: `ValidationError: goals — Input should be an object`

**Cause:** LLM passe une liste pour `goals` au lieu d'un dict

**Solution:** Vérifier que le paramètre `goals` dans `agent.py` est typé `dict[str, int] | None` (pas `dict` nu). Le type explicite génère un JSON schema correct que le LLM comprend.

### Erreur: `ModuleNotFoundError` après `pip install`

**Solution:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📚 Références Utiles

- **CLAUDE.md** — Guide de développement complet
- **src/agent.py** — Exemple correct de `OpenAIChatModel` et `result.output`
- **tests/test_user_stories_e2e.py** — Pattern `FunctionModel` + `_make_supabase_mock`

---

**Dernière mise à jour:** 2026-02-19
**Raison:** Upgrade pydantic-ai 0.0.53 → 1.39.0. Correction `result.data` → `result.output`. Correction `OpenAIModel` → `OpenAIChatModel` (préféré). Ajout pattern FunctionModel et mock Supabase. Ajout modèles Claude.
