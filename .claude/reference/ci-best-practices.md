# CI Best Practices

## Le problème

En local, le `.env` fournit toutes les clés API et URLs. En CI (GitHub Actions), il n'y a que des fake env vars déclarées dans le workflow. Si du code vérifie une env var à l'import (pas à l'exécution), tous les tests qui importent ce module crashent.

## Règles

### 1. Nouvelle env var → l'ajouter au CI

Fichier : `.github/workflows/python-unit-tests.yml`, section `env:`.

Env vars actuelles :
```yaml
env:
  SUPABASE_URL: https://fake.supabase.co
  SUPABASE_SERVICE_KEY: fake-key
  DATABASE_URL: postgresql://fake:fake@localhost:5432/fake
  ANTHROPIC_API_KEY: fake-key-for-ci
  LLM_API_KEY: fake-key-for-ci
  EMBEDDING_API_KEY: fake-key-for-ci
  ENVIRONMENT: test
```

Si tu ajoutes une nouvelle env var obligatoire dans le code (ex: `BRAVE_API_KEY`), ajoute-la ici avec une valeur fake.

### 2. Test qui nécessite une vraie DB/API → `@requires_real_db`

```python
from tests.test_openfoodfacts_client import requires_real_db  # ou le redéfinir

@requires_real_db
@pytest.mark.asyncio
async def test_something_that_needs_real_supabase():
    ...
```

Le décorateur skip le test quand `SUPABASE_URL` commence par `https://fake`.

Exemples de tests qui nécessitent la vraie DB :
- Recherche full-text dans `openfoodfacts_products` (264K produits)
- Lecture/écriture dans `ingredient_mapping` (cache)
- Tout test qui fait un vrai appel réseau à Supabase

### 3. Éviter les initialisations top-level qui crashent

**Mauvais :**
```python
# agent.py — exécuté à l'import
agent = Agent(get_model(), ...)  # crash si LLM_API_KEY absent
```

**Mieux :**
```python
# Lazy init — exécuté à la première utilisation
_agent = None
def get_agent():
    global _agent
    if _agent is None:
        _agent = Agent(get_model(), ...)
    return _agent
```

Note : `agent.py` utilise actuellement le pattern top-level (pour des raisons historiques). C'est compensé par les fake env vars en CI. Si on refactore un jour, préférer le lazy init.

### 4. Séparer tests unitaires et tests d'intégration

| Type | Caractéristiques | Où |
|---|---|---|
| **Unitaire** | Pas de réseau, pas de DB, déterministe | `tests/` — tourne en CI |
| **Intégration** | Nécessite Supabase, API externes | `tests/` avec `@requires_real_db` — skip en CI |
| **Eval** | Nécessite un vrai LLM | `evals/` — jamais en CI |

### 5. Checklist avant de push

- [ ] Nouvelle env var ajoutée ? → mise à jour de `python-unit-tests.yml`
- [ ] Nouveau test qui tape une vraie DB ? → `@requires_real_db`
- [ ] Import d'un module qui vérifie des env vars ? → vérifier que les fake vars couvrent

## Historique

Ces règles ont été établies après que le CI a cassé lors du premier déploiement (mars 2026). Les causes étaient :
- `LLM_API_KEY`, `ANTHROPIC_API_KEY`, `EMBEDDING_API_KEY`, `DATABASE_URL` absentes en CI
- Tests OpenFoodFacts qui tapaient `fake.supabase.co` → DNS error
- Mypy `continue-on-error` qui ne propageait pas au workflow parent
