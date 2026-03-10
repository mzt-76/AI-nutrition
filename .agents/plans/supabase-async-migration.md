# Plan: Migration Supabase sync → AsyncClient

## Context

Toutes les fonctions DB du projet sont déclarées `async def` mais utilisent le client Supabase **synchrone** (`Client`). Chaque `.execute()` bloque l'event loop de FastAPI, empêchant le traitement concurrent des requêtes.

**Impact** : 57 appels `.execute()` bloquants dans 6 fichiers, 16 fichiers de tests à mettre à jour.

**Approche** : Supabase 2.15.0 (installé) fournit `AsyncClient` + `acreate_client`. La migration est mécanique : changer le client, ajouter `await` devant chaque `.execute()`, mettre à jour les mocks dans les tests.

**Risque** : Moyen — changement mécanique mais massif (57 call sites + 16 tests). Aucun changement d'API publique.

---

## Phase 1 — Infrastructure : créer le client async

### Task 1.1: Ajouter get_async_supabase_client() dans clients.py
- ACTION: Edit `src/clients.py`
- IMPLEMENT:
  - Ajouter l'import : `from supabase import acreate_client, AsyncClient`
  - Créer la fonction :
    ```python
    async def get_async_supabase_client() -> AsyncClient:
        """Create and return an async Supabase client."""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        logger.info(f"Initializing async Supabase client for: {url}")
        return await acreate_client(url, key)
    ```
  - Conserver `get_supabase_client()` sync pour les scripts standalone (openfoodfacts_import.py)
- VALIDATE: `python -c "import asyncio; from src.clients import get_async_supabase_client; print(type(asyncio.run(get_async_supabase_client())))"`

### Task 1.2: Mettre à jour le lifespan FastAPI pour utiliser AsyncClient
- ACTION: Edit `src/api.py`
- IMPLEMENT:
  - Changer l'import : ajouter `AsyncClient` depuis supabase
  - Changer le type du global : `supabase: AsyncClient | None = None`
  - Dans `lifespan()` : remplacer `supabase = get_supabase_client()` par `supabase = await get_async_supabase_client()`
  - Importer `get_async_supabase_client` depuis `src.clients`
- VALIDATE: `ruff check src/api.py && mypy src/api.py`

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
  - Fichiers concernés :
    1. `test_db_utils.py`
    2. `test_api.py`
    3. `test_api_crud.py`
    4. `test_recipe_db.py`
    5. `test_openfoodfacts_client.py`
    6. `test_profile_caching.py`
    7. `test_fetch_meal_plan.py`
    8. `test_generate_custom_recipe.py`
    9. `test_generate_day_plan.py`
    10. `test_generate_from_recipes.py`
    11. `test_generate_week_plan.py`
    12. `test_get_daily_summary.py`
    13. `test_log_food_entries.py`
    14. `test_set_baseline.py`
    15. `test_agent_basic.py`
    16. `test_user_stories_e2e.py`
- VALIDATE: `pytest tests/ -x` (stop au premier échec pour itérer)

---

## Phase 6 — Fichiers inchangés (sync OK)

Ces fichiers utilisent le client sync et ne sont PAS dans le scope de cette migration :

- `src/nutrition/openfoodfacts_import.py` — script standalone (pas async, pas dans FastAPI)
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
- **Estimation** : ~57 `await` à ajouter + ~16 fichiers de tests à mettre à jour. Changements mécaniques mais volume important. Recommandé de faire phase par phase avec `pytest -x` entre chaque.
