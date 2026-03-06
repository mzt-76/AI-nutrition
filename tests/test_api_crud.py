"""Tests for CRUD API endpoints: daily-log, meal-plans, favorites, shopping-lists.

Uses FastAPI TestClient with mocked Supabase. No real database calls.
Follows the same pattern as test_api.py (mock supabase, override verify_token).
"""

from unittest.mock import MagicMock

import pytest

USER_ID = "user-abc-123"
OTHER_USER_ID = "user-other-456"


def _setup_supabase(data=None):
    """Create a fresh MagicMock supabase and set it on api_module.

    Returns the mock so tests can further customize if needed.
    The mock supports deep chaining — any sequence of .method() calls
    eventually returns a response with .data = data.
    """
    import src.api as api_module

    mock = MagicMock()
    mock_resp = MagicMock()
    mock_resp.data = data

    # Build a recursive chain: every method call returns the same chain object
    # and .execute() returns mock_resp.
    chain = MagicMock()
    chain.execute.return_value = mock_resp

    for method in (
        "select",
        "insert",
        "update",
        "delete",
        "eq",
        "order",
        "limit",
        "single",
    ):
        getattr(chain, method).return_value = chain

    mock.table.return_value = chain
    api_module.supabase = mock
    return mock


@pytest.fixture
def auth_client():
    """TestClient with auth returning USER_ID."""
    import src.api as api_module
    from fastapi.testclient import TestClient

    api_module.supabase = MagicMock()
    api_module.title_agent = MagicMock()
    api_module.mem0_client = None

    api_module.app.dependency_overrides[api_module.verify_token] = lambda: {
        "id": USER_ID
    }

    with TestClient(api_module.app, raise_server_exceptions=False) as c:
        yield c

    api_module.app.dependency_overrides.clear()


@pytest.fixture
def noauth_client():
    """TestClient with no auth (verify_token returns None)."""
    import src.api as api_module
    from fastapi.testclient import TestClient

    api_module.supabase = MagicMock()
    api_module.title_agent = MagicMock()
    api_module.mem0_client = None

    api_module.app.dependency_overrides[api_module.verify_token] = lambda: None

    with TestClient(api_module.app, raise_server_exceptions=False) as c:
        yield c

    api_module.app.dependency_overrides.clear()


# =============================================================================
# Daily Food Log
# =============================================================================


class TestDailyLogGet:
    """Tests for GET /api/daily-log."""

    def test_returns_entries_for_date(self, auth_client):
        entries = [
            {
                "id": "e1",
                "food_name": "poulet",
                "calories": 250,
                "meal_type": "dejeuner",
            },
            {"id": "e2", "food_name": "riz", "calories": 180, "meal_type": "dejeuner"},
        ]
        _setup_supabase(data=entries)

        resp = auth_client.get(f"/api/daily-log?user_id={USER_ID}&date=2026-03-05")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[0]["food_name"] == "poulet"

    def test_returns_empty_list_when_no_entries(self, auth_client):
        _setup_supabase(data=[])

        resp = auth_client.get(f"/api/daily-log?user_id={USER_ID}&date=2026-03-05")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.get(
            f"/api/daily-log?user_id={OTHER_USER_ID}&date=2026-03-05"
        )
        assert resp.status_code == 403

    def test_invalid_date_format_returns_400(self, auth_client):
        resp = auth_client.get(f"/api/daily-log?user_id={USER_ID}&date=not-a-date")
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.get(f"/api/daily-log?user_id={USER_ID}&date=2026-03-05")
        assert resp.status_code == 401


class TestDailyLogCreate:
    """Tests for POST /api/daily-log."""

    def test_creates_entry(self, auth_client):
        created = {
            "id": "new-1",
            "user_id": USER_ID,
            "food_name": "poulet",
            "calories": 250,
            "meal_type": "dejeuner",
        }
        _setup_supabase(data=[created])

        resp = auth_client.post(
            "/api/daily-log",
            json={
                "user_id": USER_ID,
                "meal_type": "dejeuner",
                "food_name": "poulet",
                "calories": 250,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["food_name"] == "poulet"

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.post(
            "/api/daily-log",
            json={
                "user_id": OTHER_USER_ID,
                "meal_type": "dejeuner",
                "food_name": "poulet",
            },
        )
        assert resp.status_code == 403

    def test_missing_required_field_returns_422(self, auth_client):
        resp = auth_client.post(
            "/api/daily-log",
            json={"user_id": USER_ID},
        )
        assert resp.status_code == 422

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.post(
            "/api/daily-log",
            json={
                "user_id": USER_ID,
                "meal_type": "dejeuner",
                "food_name": "riz",
            },
        )
        assert resp.status_code == 401


class TestDailyLogDelete:
    """Tests for DELETE /api/daily-log/{entry_id}."""

    def test_deletes_own_entry(self, auth_client):
        _setup_supabase(data={"user_id": USER_ID})

        resp = auth_client.delete("/api/daily-log/entry-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_wrong_user_returns_403(self, auth_client):
        _setup_supabase(data={"user_id": OTHER_USER_ID})

        resp = auth_client.delete("/api/daily-log/entry-1")
        assert resp.status_code == 403

    def test_not_found_returns_404(self, auth_client):
        _setup_supabase(data=None)

        resp = auth_client.delete("/api/daily-log/nonexistent")
        assert resp.status_code == 404

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.delete("/api/daily-log/entry-1")
        assert resp.status_code == 401


class TestDailyLogUpdate:
    """Tests for PUT /api/daily-log/{entry_id}."""

    def test_updates_own_entry(self, auth_client):
        import src.api as api_module

        updated = {"id": "e1", "food_name": "poulet grille", "calories": 300}

        api_module.supabase = MagicMock()
        # Ownership check chain: table().select().eq().single().execute()
        ownership_resp = MagicMock()
        ownership_resp.data = {"user_id": USER_ID}
        ownership_chain = MagicMock()
        ownership_chain.execute.return_value = ownership_resp
        select_chain = MagicMock()
        select_chain.eq.return_value = MagicMock()
        select_chain.eq.return_value.single.return_value = ownership_chain
        table_mock = MagicMock()
        table_mock.select.return_value = select_chain
        # Update chain: table().update().eq().execute()
        update_resp = MagicMock()
        update_resp.data = [updated]
        update_eq = MagicMock()
        update_eq.execute.return_value = update_resp
        update_chain = MagicMock()
        update_chain.eq.return_value = update_eq
        table_mock.update.return_value = update_chain

        api_module.supabase.table.return_value = table_mock

        resp = auth_client.put(
            "/api/daily-log/e1",
            json={"food_name": "poulet grille", "calories": 300},
        )
        assert resp.status_code == 200

    def test_empty_update_returns_400(self, auth_client):
        # Ownership check passes, but no fields to update
        _setup_supabase(data={"user_id": USER_ID})

        resp = auth_client.put("/api/daily-log/e1", json={})
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.put("/api/daily-log/e1", json={"calories": 100})
        assert resp.status_code == 401


# =============================================================================
# Meal Plans
# =============================================================================


class TestMealPlansList:
    """Tests for GET /api/meal-plans."""

    def test_returns_plans(self, auth_client):
        plans = [
            {
                "id": "p1",
                "user_id": USER_ID,
                "week_start": "2026-03-03",
                "created_at": "2026-03-03T10:00:00",
            },
        ]
        _setup_supabase(data=plans)

        resp = auth_client.get(f"/api/meal-plans?user_id={USER_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.get(f"/api/meal-plans?user_id={OTHER_USER_ID}")
        assert resp.status_code == 403

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.get(f"/api/meal-plans?user_id={USER_ID}")
        assert resp.status_code == 401


class TestMealPlanGet:
    """Tests for GET /api/meal-plans/{plan_id}."""

    PLAN_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_returns_plan(self, auth_client):
        plan = {"id": self.PLAN_UUID, "user_id": USER_ID, "plan_data": {"days": []}}
        _setup_supabase(data=plan)

        resp = auth_client.get(f"/api/meal-plans/{self.PLAN_UUID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == self.PLAN_UUID

    def test_wrong_user_returns_403(self, auth_client):
        _setup_supabase(data={"id": self.PLAN_UUID, "user_id": OTHER_USER_ID})

        resp = auth_client.get(f"/api/meal-plans/{self.PLAN_UUID}")
        assert resp.status_code == 403

    def test_not_found_returns_404(self, auth_client):
        _setup_supabase(data=None)

        resp = auth_client.get(f"/api/meal-plans/{self.PLAN_UUID}")
        assert resp.status_code == 404

    def test_invalid_uuid_returns_400(self, auth_client):
        resp = auth_client.get("/api/meal-plans/not-a-uuid")
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.get(f"/api/meal-plans/{self.PLAN_UUID}")
        assert resp.status_code == 401


# =============================================================================
# Favorites
# =============================================================================


class TestFavoritesList:
    """Tests for GET /api/favorites."""

    def test_returns_favorites(self, auth_client):
        favs = [
            {
                "id": "f1",
                "user_id": USER_ID,
                "recipe_id": "r1",
                "recipes": {"name": "Poulet"},
            }
        ]
        _setup_supabase(data=favs)

        resp = auth_client.get(f"/api/favorites?user_id={USER_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.get(f"/api/favorites?user_id={OTHER_USER_ID}")
        assert resp.status_code == 403


class TestFavoritesCreate:
    """Tests for POST /api/favorites."""

    def test_adds_favorite(self, auth_client):
        created = {"id": "f-new", "user_id": USER_ID, "recipe_id": "r1"}
        _setup_supabase(data=[created])

        resp = auth_client.post(
            "/api/favorites",
            json={"user_id": USER_ID, "recipe_id": "r1"},
        )
        assert resp.status_code == 200
        assert resp.json()["recipe_id"] == "r1"

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.post(
            "/api/favorites",
            json={"user_id": OTHER_USER_ID, "recipe_id": "r1"},
        )
        assert resp.status_code == 403


class TestFavoritesDelete:
    """Tests for DELETE /api/favorites/{favorite_id}."""

    def test_removes_own_favorite(self, auth_client):
        _setup_supabase(data={"user_id": USER_ID})

        resp = auth_client.delete("/api/favorites/f1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_wrong_user_returns_403(self, auth_client):
        _setup_supabase(data={"user_id": OTHER_USER_ID})

        resp = auth_client.delete("/api/favorites/f1")
        assert resp.status_code == 403

    def test_not_found_returns_404(self, auth_client):
        _setup_supabase(data=None)

        resp = auth_client.delete("/api/favorites/nonexistent")
        assert resp.status_code == 404


# =============================================================================
# Shopping Lists
# =============================================================================


class TestShoppingListsList:
    """Tests for GET /api/shopping-lists."""

    def test_returns_lists(self, auth_client):
        lists = [{"id": "sl1", "user_id": USER_ID, "title": "Courses semaine 10"}]
        _setup_supabase(data=lists)

        resp = auth_client.get(f"/api/shopping-lists?user_id={USER_ID}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_wrong_user_returns_403(self, auth_client):
        resp = auth_client.get(f"/api/shopping-lists?user_id={OTHER_USER_ID}")
        assert resp.status_code == 403


class TestShoppingListGet:
    """Tests for GET /api/shopping-lists/{list_id}."""

    def test_returns_list(self, auth_client):
        sl = {"id": "sl1", "user_id": USER_ID, "title": "Courses", "items": []}
        _setup_supabase(data=sl)

        resp = auth_client.get("/api/shopping-lists/sl1")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Courses"

    def test_wrong_user_returns_403(self, auth_client):
        _setup_supabase(data={"id": "sl1", "user_id": OTHER_USER_ID})

        resp = auth_client.get("/api/shopping-lists/sl1")
        assert resp.status_code == 403

    def test_not_found_returns_404(self, auth_client):
        _setup_supabase(data=None)

        resp = auth_client.get("/api/shopping-lists/nonexistent")
        assert resp.status_code == 404


class TestShoppingListUpdate:
    """Tests for PUT /api/shopping-lists/{list_id}."""

    def test_updates_list(self, auth_client):
        import src.api as api_module

        api_module.supabase = MagicMock()
        # Ownership check
        ownership_resp = MagicMock()
        ownership_resp.data = {"user_id": USER_ID}
        ownership_chain = MagicMock()
        ownership_chain.execute.return_value = ownership_resp
        select_chain = MagicMock()
        select_chain.eq.return_value = MagicMock()
        select_chain.eq.return_value.single.return_value = ownership_chain
        table_mock = MagicMock()
        table_mock.select.return_value = select_chain
        # Update chain
        update_resp = MagicMock()
        update_resp.data = [{"id": "sl1", "title": "Updated", "items": []}]
        update_eq = MagicMock()
        update_eq.execute.return_value = update_resp
        update_chain = MagicMock()
        update_chain.eq.return_value = update_eq
        table_mock.update.return_value = update_chain

        api_module.supabase.table.return_value = table_mock

        resp = auth_client.put(
            "/api/shopping-lists/sl1",
            json={
                "items": [
                    {
                        "name": "Tomates",
                        "quantity": 4,
                        "unit": "pcs",
                        "category": "produce",
                        "checked": True,
                    }
                ]
            },
        )
        assert resp.status_code == 200

    def test_empty_update_returns_400(self, auth_client):
        _setup_supabase(data={"user_id": USER_ID})

        resp = auth_client.put("/api/shopping-lists/sl1", json={})
        assert resp.status_code == 400

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.put("/api/shopping-lists/sl1", json={"title": "Updated"})
        assert resp.status_code == 401


# =============================================================================
# Profile Recalculate
# =============================================================================


class TestProfileRecalculate:
    """Tests for POST /api/profile/recalculate."""

    VALID_BODY = {
        "age": 30,
        "gender": "male",
        "weight_kg": 80.0,
        "height_cm": 178,
        "activity_level": "moderate",
    }

    def test_calculates_correctly(self, auth_client):
        _setup_supabase(data=[{"id": USER_ID}])

        resp = auth_client.post("/api/profile/recalculate", json=self.VALID_BODY)
        assert resp.status_code == 200

        data = resp.json()
        assert "bmr" in data
        assert "tdee" in data
        assert "target_calories" in data
        assert "target_protein_g" in data
        assert "target_carbs_g" in data
        assert "target_fat_g" in data
        assert "primary_goal" in data

        # Mifflin-St Jeor for 30yo male, 80kg, 178cm:
        # BMR = 10*80 + 6.25*178 - 5*30 + 5 = 800 + 1112.5 - 150 + 5 = 1767
        assert data["bmr"] == 1767
        # TDEE = 1767 * 1.55 = 2738
        assert data["tdee"] == 2738
        # Default goal = maintenance (score 7), target_cal = TDEE + 0
        assert data["primary_goal"] == "maintenance"
        assert data["target_calories"] == 2738
        assert data["target_protein_g"] > 0
        assert data["target_carbs_g"] > 0
        assert data["target_fat_g"] > 0

    def test_no_auth_returns_401(self, noauth_client):
        resp = noauth_client.post("/api/profile/recalculate", json=self.VALID_BODY)
        assert resp.status_code == 401

    def test_invalid_gender_returns_422(self, auth_client):
        body = {**self.VALID_BODY, "gender": "other"}
        resp = auth_client.post("/api/profile/recalculate", json=body)
        assert resp.status_code == 422

    def test_invalid_activity_level_returns_500(self, auth_client):
        body = {**self.VALID_BODY, "activity_level": "extreme"}
        resp = auth_client.post("/api/profile/recalculate", json=body)
        # calculate_tdee raises ValueError -> 500
        assert resp.status_code == 500

    def test_missing_required_field_returns_422(self, auth_client):
        resp = auth_client.post(
            "/api/profile/recalculate",
            json={"age": 30, "gender": "male"},
        )
        assert resp.status_code == 422
