# Plan: Migration Supabase sync → AsyncClient

## Context

Toutes les fonctions DB du projet sont déclarées `async def` mais utilisent le client Supabase **synchrone** (`Client`). Chaque `.execute()` bloque l'event loop de FastAPI, empêchant le traitement concurrent des requêtes.

**Impact** : 81 appels `.execute()` bloquants dans 16 fichiers async (6 src/ + 10 skills/), 16+ fichiers de tests à mettre à jour.

**Approche** : Supabase 2.15.0 (installé) fournit `AsyncClient`. **Découverte clé** : `AsyncClient(url, key)` peut être construit de manière **synchrone** (son `__init__` n'est pas une coroutine). Seul `.execute()` devient un coroutine qu'il faut `await`. Cela signifie que `_get_shared_clients()` et `create_agent_deps()` restent **sync** — pas de cascade async.

**Risques vérifiés par tests** :
1. Construction sync `AsyncClient(url, key)` : fonctionne avec service key (testé)
2. Concurrent `asyncio.gather()` sur client partagé : fonctionne (testé 5 requêtes parallèles)
3. Pattern Streamlit `asyncio.run()` : fonctionne (testé)
4. `create_agent_deps()` reste sync : aucun des 50+ callers ne casse
5. `test_create_agent_deps_returns_valid_object` : reste sync, pas impacté

**Risque** : Faible — changement mécanique. `_get_shared_clients()` et `create_agent_deps()` restent sync. Aucun changement d'API publique.

---

## Phase 1 — Infrastructure : remplacer le client sync par async

### Task 1.1: Ajouter get_async_supabase_client() dans clients.py
- ACTION: Edit `src/clients.py`
- IMPLEMENT:
  - Ajouter l'import : `from supabase._async.client import AsyncClient as SupabaseAsyncClient`
  - Créer la fonction **SYNC** (pas async !) :
    ```python
    def get_async_supabase_client() -> SupabaseAsyncClient:
        """Create and return an async Supabase client (sync construction).

        AsyncClient.__init__ is synchronous — only .execute() is async.
        This allows _get_shared_clients() to remain sync while providing
        a client whose queries can be properly awaited.
        """
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        logger.info(f"Initializing async Supabase client for: {url}")
        return SupabaseAsyncClient(url, key)
    ```
  - Conserver `get_supabase_client()` sync pour les scripts standalone (openfoodfacts_import.py, RAG pipeline, verify_setup)
- VALIDATE: `python -c "from src.clients import get_async_supabase_client; c = get_async_supabase_client(); print(type(c))"`

### Task 1.2: Remplacer le client dans _get_shared_clients() et AgentDeps
- ACTION: Edit `src/agent.py`
- IMPLEMENT:
  - Importer `get_async_supabase_client` depuis `src.clients`
  - Dans `_get_shared_clients()` : remplacer `get_supabase_client()` par `get_async_supabase_client()`
  - Changer le type hint de `AgentDeps.supabase` : `Client` → `SupabaseAsyncClient`
  - `create_agent_deps()` reste **sync** — aucun changement de signature
- VALIDATE: `python -c "from src.agent import create_agent_deps; d = create_agent_deps(); print(type(d.supabase))"`

### Task 1.3: Mettre à jour le global supabase dans api.py + aclose au shutdown
- ACTION: Edit `src/api.py`
- IMPLEMENT:
  - Changer l'import : ajouter `SupabaseAsyncClient` depuis supabase._async.client
  - Changer le type du global : `supabase: SupabaseAsyncClient | None = None`
  - Dans `lifespan()` : remplacer `supabase = get_supabase_client()` par `supabase = get_async_supabase_client()` (sync, pas await)
  - Importer `get_async_supabase_client` depuis `src.clients`
  - **Ajouter `aclose()` au shutdown** dans le lifespan, après le `yield` :
    ```python
    # shutdown
    if supabase:
        await supabase.aclose()  # ferme le pool de connexions httpx
    ```
- VALIDATE: `ruff check src/api.py`

### Task 1.4: Ajouter filterwarnings pour détecter les await oubliés
- ACTION: Edit `pytest.ini`
- IMPLEMENT:
  - Ajouter dans la section `[pytest]` :
    ```ini
    filterwarnings =
        error::RuntimeWarning
    ```
  - Cela transforme `RuntimeWarning: coroutine was never awaited` en erreur fatale pendant les tests
- VALIDATE: `pytest tests/test_db_utils.py -x` (vérifie que le warning est bien une erreur)

---

## Phase 2 — Migration des fonctions DB (db_utils.py + tools.py)

### Task 2.1: Migrer db_utils.py vers AsyncClient
- ACTION: Edit `src/db_utils.py`
- IMPLEMENT:
  - Changer le type hint du paramètre `supabase` dans toutes les fonctions : `Client` → `AsyncClient`
  - Ajouter `await` devant chaque `.execute()` (7 occurrences) :
    - `fetch_conversation_history` (ligne ~44)
    - `create_conversation` (ligne ~76)
    - `update_conversation_title` (ligne ~100)
    - `store_message` (ligne ~140)
    - `check_rate_limit` (ligne ~180)
    - `store_request` (ligne ~230)
    - `update_request_status` (ligne ~270)
  - Mettre à jour l'import : `from supabase import AsyncClient`
- PATTERN: Pour chaque fonction, le changement est identique :
  ```python
  # AVANT
  response = supabase.table("x").select("*").execute()
  # APRÈS
  response = await supabase.table("x").select("*").execute()
  ```
- VALIDATE: `mypy src/db_utils.py && pytest tests/test_db_utils.py`

### Task 2.2: Migrer tools.py vers AsyncClient
- ACTION: Edit `src/tools.py`
- IMPLEMENT:
  - Changer `Client` → `AsyncClient` dans les type hints
  - Ajouter `await` devant les 2 `.execute()` dans `fetch_my_profile_tool` et `update_my_profile_tool`
- VALIDATE: `mypy src/tools.py && pytest tests/test_profile_caching.py`

---

## Phase 3 — Migration des modules nutrition/

### Task 3.1: Migrer recipe_db.py vers AsyncClient
- ACTION: Edit `src/nutrition/recipe_db.py`
- IMPLEMENT:
  - Changer `Client` → `AsyncClient` dans tous les type hints
  - Ajouter `await` devant les 6 `.execute()` dans :
    - `search_recipes` (~3 appels)
    - `get_recipe_by_id` (~1 appel)
    - `save_recipe` (~1 appel)
    - `increment_usage` (~1 appel, c'est un `.rpc()`)
  - Pour les RPC : `await supabase.rpc("increment_recipe_usage", {...}).execute()`
- VALIDATE: `mypy src/nutrition/recipe_db.py && pytest tests/test_recipe_db.py`

### Task 3.2: Migrer openfoodfacts_client.py vers AsyncClient
- ACTION: Edit `src/nutrition/openfoodfacts_client.py`
- IMPLEMENT:
  - Changer `Client` → `AsyncClient` dans les type hints
  - Ajouter `await` devant les 5 `.execute()` dans :
    - `search_food_local`
    - `match_ingredient`
    - `off_validate_recipe`
  - RPC call : `await supabase.rpc("search_openfoodfacts", {...}).execute()`
- VALIDATE: `mypy src/nutrition/openfoodfacts_client.py && pytest tests/test_openfoodfacts_client.py`

### Task 3.3: Migrer feedback_extraction.py (si nécessaire)
- ACTION: Vérifier `src/nutrition/feedback_extraction.py`
- IMPLEMENT: Si le `.execute()` est dans un docstring/example seulement → rien à faire. Si c'est un vrai appel dans une `async def` → ajouter `await` et changer le type hint.
- VALIDATE: `mypy src/nutrition/feedback_extraction.py`

---

## Phase 3b — Migration des skill scripts (26 appels — MANQUANTS dans la version initiale)

Les skill scripts reçoivent le client Supabase via `kwargs["supabase"]` injecté par `run_skill_script()`.
Chaque script a `async def execute(**kwargs)` et utilise `.execute()` de manière synchrone.

### Task 3b.1: Migrer food-tracking scripts
- ACTION: Edit `skills/food-tracking/scripts/log_food_entries.py` et `get_daily_summary.py`
- IMPLEMENT:
  - `log_food_entries.py`: 5 × `await .execute()`, changer type hint `Client` → `AsyncClient`
  - `get_daily_summary.py`: 2 × `await .execute()`
- VALIDATE: `pytest tests/test_log_food_entries.py tests/test_get_daily_summary.py`

### Task 3b.2: Migrer meal-planning scripts
- ACTION: Edit 4 fichiers dans `skills/meal-planning/scripts/`
- IMPLEMENT:
  - `fetch_stored_meal_plan.py`: 1 × `await .execute()`
  - `generate_custom_recipe.py`: 1 × `await .execute()`
  - `generate_day_plan.py`: 1 × `await .execute()`
  - `generate_week_plan.py`: 1 × `await .execute()`
- VALIDATE: `pytest tests/test_fetch_meal_plan.py tests/test_generate_day_plan.py tests/test_generate_week_plan.py`

### Task 3b.3: Migrer shopping-list scripts
- ACTION: Edit `skills/shopping-list/scripts/generate_from_recipes.py` et `generate_shopping_list.py`
- IMPLEMENT:
  - `generate_from_recipes.py`: 2 × `await .execute()`
  - `generate_shopping_list.py`: 3 × `await .execute()`
- VALIDATE: `pytest tests/test_generate_from_recipes.py`

### Task 3b.4: Migrer weekly-coaching scripts
- ACTION: Edit `skills/weekly-coaching/scripts/calculate_weekly_adjustments.py` et `set_baseline.py`
- IMPLEMENT:
  - `calculate_weekly_adjustments.py`: 6 × `await .execute()`
  - `set_baseline.py`: 3 × `await .execute()`
- VALIDATE: `pytest tests/test_set_baseline.py`

### Task 3b.5: Migrer knowledge-searching script
- ACTION: Edit `skills/knowledge-searching/scripts/retrieve_relevant_documents.py`
- IMPLEMENT: 1 × `await .execute()`
- VALIDATE: `ruff check skills/`

---

## Phase 4 — Migration de api.py (34 appels)

### Task 4.1: Migrer les endpoints CRUD de api.py
- ACTION: Edit `src/api.py`
- IMPLEMENT:
  - Le global `supabase` est déjà `AsyncClient` (Task 1.2)
  - Ajouter `await` devant les 34 `.execute()` dans tous les endpoints :
    - `list_conversations` (~2 appels)
    - `agent_endpoint` (~4 appels : conversation, messages)
    - `get_meal_plan`, `list_meal_plans`, `delete_meal_plan` (~3 appels)
    - `delete_conversation` (~2 appels)
    - `food_search` (~1 appel)
    - `get_daily_log`, `create_daily_log`, `update_daily_log`, `delete_daily_log` (~6 appels)
    - `list_favorites`, `add_favorite`, `remove_favorite` (~4 appels)
    - `recalculate_needs` endpoint (~4 appels)
    - Autres endpoints restants (~8 appels)
  - **Attention** : certains appels sont dans des try/except — ne pas casser la structure
- VALIDATE: `mypy src/api.py && pytest tests/test_api.py tests/test_api_crud.py`

---

## Phase 5 — Mise à jour des mocks dans les tests

### Task 5.1: Créer un helper AsyncMock pour Supabase
- ACTION: Edit ou créer `tests/conftest.py`
- IMPLEMENT:
  - Créer un fixture/helper qui mock le client async :
    ```python
    from unittest.mock import AsyncMock, MagicMock

    def make_async_supabase_mock():
        """Create a mock AsyncClient with chainable async .execute()."""
        mock = MagicMock()
        # Make .execute() return a coroutine
        mock.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[...])
        )
        # ... same for insert, update, delete, rpc chains
        return mock
    ```
  - Le pattern change de `MagicMock` pur à `AsyncMock` sur `.execute()`
- VALIDATE: `pytest tests/conftest.py --co -q`

### Task 5.2: Migrer les 16 fichiers de tests
- ACTION: Edit chaque fichier de test
- IMPLEMENT: Pour chaque test qui mock Supabase :
  - Remplacer `mock_supabase.table(...).execute.return_value` par `mock_supabase.table(...).execute = AsyncMock(return_value=...)`
  - Le chainage `.select().eq().gte()` reste `MagicMock` (sync) — seul `.execute()` devient `AsyncMock`
  - Fichiers concernés (14 fichiers avec mocks `.execute()`) :
    1. `test_db_utils.py`
    2. `test_api.py`
    3. `test_api_crud.py`
    4. `test_recipe_db.py`
    5. `test_profile_caching.py`
    6. `test_fetch_meal_plan.py`
    7. `test_generate_custom_recipe.py`
    8. `test_generate_day_plan.py`
    9. `test_generate_from_recipes.py`
    10. `test_generate_week_plan.py`
    11. `test_get_daily_summary.py`
    12. `test_log_food_entries.py`
    13. `test_set_baseline.py`
    14. `test_user_stories_e2e.py`
  - Fichiers NON impactés (pas de mock .execute()) :
    - `test_openfoodfacts_client.py` — pas de mock supabase
    - `test_agent_basic.py` — teste la structure, pas les requêtes DB
- VALIDATE: `pytest tests/ -x` (stop au premier échec pour itérer)

---

## Phase 6 — Fichiers inchangés (sync OK)

Ces fichiers utilisent le client sync et ne sont PAS dans le scope de cette migration :

- `src/nutrition/openfoodfacts_import.py` — script standalone, pas async
- `src/nutrition/feedback_extraction.py` — `.execute()` dans un docstring seulement
- `src/verify_setup.py` — script de diagnostic, pas async
- `src/RAG_Pipeline/common/db_handler.py` — pipeline RAG standalone (9 appels, pas async)
- `src/RAG_Pipeline/Google_Drive/drive_watcher.py` — pipeline RAG standalone (5 appels, pas async)
- `scripts/*` — scripts CLI, exécutés hors event loop

Ils continueront à utiliser `get_supabase_client()` (sync).

---

## Vérification finale

### Task FINAL: Validation complète
- ACTION: Run full test suite + linters
- IMPLEMENT:
  ```bash
  ruff format src/ tests/ && ruff check src/ tests/ && mypy src/ && pytest tests/ -x
  ```
- VALIDATE: Tout passe au vert. Vérifier manuellement que `uvicorn src.api:app` démarre sans erreur et qu'un appel API fonctionne.

---

## Notes techniques

- **Backward compat** : `get_supabase_client()` sync est conservé pour les scripts standalone
- **Pas de changement d'API publique** : les endpoints FastAPI gardent les mêmes signatures
- **Le client async de Supabase** utilise `httpx.AsyncClient` en interne — parfaitement compatible avec FastAPI
- **Estimation** : ~81 `await` à ajouter dans 16 fichiers async + ~16 fichiers de tests à mettre à jour. Changements mécaniques mais volume important. Recommandé de faire phase par phase avec `pytest -x` entre chaque.

---

## Détection des `await` oubliés

Un `await` oublié ne crash pas — `.execute()` retourne un objet `coroutine` au lieu des données.
Le code continue et plante plus loin avec une erreur incompréhensible.

**Stratégie de détection multi-couche :**
1. **mypy strict** : `.execute()` retourne `Coroutine[...]` au lieu de `APIResponse` → mypy signale le type mismatch
2. **ruff** : règle `RUF006` détecte les coroutines non-awaited dans les fonctions async
3. **pytest -x** : les tests avec `AsyncMock` échouent si `.execute()` n'est pas awaité (le mock attend un `await`)
4. **Runtime** : Python émet `RuntimeWarning: coroutine 'execute' was never awaited` — on ajoutera `filterwarnings("error", "coroutine.*was never awaited")` dans `pyproject.toml` pour transformer ce warning en erreur fatale pendant les tests

---

## Pourquoi on bypass `.create()` — et pourquoi c'est sûr

### Architecture auth du projet

```
Frontend (React)                    Backend (FastAPI)                  Supabase
─────────────────                   ─────────────────                  ────────
User se connecte
 → Supabase Auth
 → reçoit un JWT perso
 → envoie JWT au backend ─────→    Décode le JWT
                                    Extrait user_id
                                    Requête avec SERVICE KEY ──────→  Bypass RLS
                                    + filtre .eq("id", user_id)       Retourne les données
```

Le backend utilise **un seul client admin** (service key) pour **tous** les utilisateurs.
La distinction entre utilisateurs se fait par le `user_id` dans les requêtes, pas par le client.

### `.create()` vs construction directe

| | `await AsyncClient.create(url, key)` | `AsyncClient(url, key)` |
|---|---|---|
| Construction | async (nécessite `await`) | sync (appel direct) |
| Ce que fait en plus | `await client.auth.get_session()` → résout la session auth du token | Rien — configure juste les headers |
| Utile quand | Le client utilise un **JWT utilisateur** (frontend JS) | Le client utilise un **service key** (backend admin) |
| Notre cas | ❌ Pas nécessaire | ✅ C'est ce qu'on utilise |

Le service key est envoyé dans le header `apikey` par `__init__`. Pas de session à résoudre.
Même avec 1000 utilisateurs, le backend utilise un seul client admin — le `user_id` vient du JWT décodé par FastAPI.

### Quand il faudrait `.create()`

Si on changeait l'architecture pour que le backend crée **un client par utilisateur** avec son JWT (pour que Supabase applique les RLS côté DB au lieu du code). C'est un choix d'architecture différent, pas prévu.

---

## Fermeture du client async (aclose)

**Client sync** (`Client`) : utilise `httpx.Client` → crée une connexion TCP par requête → la ferme aussitôt. Rien à nettoyer.

**Client async** (`AsyncClient`) : utilise `httpx.AsyncClient` → maintient un **pool de connexions keep-alive** pour réutiliser les connexions (plus performant). Ces connexions restent ouvertes en arrière-plan.

**Action requise** : Ajouter `await supabase.aclose()` au shutdown dans les deux endroits :

1. **api.py** — dans le lifespan FastAPI :
   ```python
   @asynccontextmanager
   async def lifespan(app):
       # startup
       supabase = get_async_supabase_client()
       yield
       # shutdown
       if supabase:
           await supabase.aclose()
   ```

2. **agent.py** — pas critique (le process CLI se termine, l'OS ferme les connexions), mais propre de le faire dans un cleanup si on en ajoute un.

Sans `aclose()` : les connexions TCP restent pendantes + Python affiche `ResourceWarning: unclosed transport`. Pas de bug fonctionnel mais pas propre.

---

## Risques vérifiés (tests passés le 2026-03-10)

| Risque | Statut | Détail |
|--------|--------|--------|
| `AsyncClient(url, key)` construction sync | ✅ Vérifié | `__init__` n'est pas une coroutine. Service key fonctionne sans `.create()` |
| Requêtes concurrentes sur client partagé | ✅ Vérifié | `asyncio.gather()` avec 5 requêtes parallèles OK |
| Pattern Streamlit `asyncio.run()` | ✅ Vérifié | Client construit en sync, utilisé en async dans `asyncio.run()` |
| `create_agent_deps()` reste sync | ✅ Vérifié | 50+ callers non impactés, test existant passe |
| `acreate_client` est async | ⚠️ Évité | On n'utilise PAS `acreate_client` — construction directe `AsyncClient(url, key)` |
| Chaînage `.table().select().eq()` reste sync | ✅ Vérifié | Seul `.execute()` change en coroutine |
| Multi-utilisateur avec service key | ✅ Sûr | Un seul client admin, `user_id` filtré dans les requêtes, pas dans le client |
