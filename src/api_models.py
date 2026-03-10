"""Pydantic request/response models for the FastAPI backend."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class FileAttachment(BaseModel):
    model_config = {"populate_by_name": True}
    file_name: str = Field(alias="fileName")
    content: str  # Base64 encoded
    mime_type: str = Field(alias="mimeType")


class AgentRequest(BaseModel):
    query: str = Field(max_length=5000)
    user_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    request_id: str
    session_id: str = ""
    files: list[FileAttachment] | None = None
    ephemeral: bool = False  # skip conversation/message storage (e.g. quick-add)


class DailyLogCreate(BaseModel):
    user_id: str
    log_date: str | None = None
    meal_type: str
    food_name: str
    quantity: float = 1
    unit: str = "portion"
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    source: str = "openfoodfacts"
    meal_plan_id: str | None = None


class DailyLogUpdate(BaseModel):
    meal_type: str | None = None
    food_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


class FavoriteCreate(BaseModel):
    user_id: str
    recipe_id: str
    notes: str | None = None


class FavoriteUpdate(BaseModel):
    notes: str | None = Field(None, max_length=500)


class RecipeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    meal_type: str = Field(..., min_length=1, max_length=50)
    ingredients: list[dict[str, Any]] = Field(..., max_length=50)
    instructions: str = Field(default="", max_length=5000)
    prep_time_minutes: int = Field(default=30, ge=1, le=480)
    calories_per_serving: float = Field(..., ge=0, le=5000)
    protein_g_per_serving: float = Field(..., ge=0, le=500)
    carbs_g_per_serving: float = Field(..., ge=0, le=500)
    fat_g_per_serving: float = Field(..., ge=0, le=500)


class RecalculateRequest(BaseModel):
    age: int
    gender: Literal["male", "female"]
    weight_kg: float
    height_cm: int
    activity_level: str
    goals: dict[str, int] | None = None


class ShoppingListItemModel(BaseModel):
    name: str
    quantity: float = 0
    unit: str = ""
    category: str = "other"
    checked: bool = False


class ShoppingListCreate(BaseModel):
    user_id: str
    meal_plan_id: str | None = None
    title: str
    items: list[ShoppingListItemModel]


class ShoppingListUpdate(BaseModel):
    title: str | None = None
    items: list[ShoppingListItemModel] | None = None
