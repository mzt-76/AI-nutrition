"""Pydantic request/response models for the FastAPI backend."""

from typing import Any, Literal

from pydantic import BaseModel, Field

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


class FileAttachment(BaseModel):
    model_config = {"populate_by_name": True}
    file_name: str = Field(alias="fileName")
    content: str  # Base64 encoded
    mime_type: str = Field(alias="mimeType")


class AgentRequest(BaseModel):
    query: str = Field(max_length=5000)
    user_id: str = Field(pattern=_UUID_PATTERN)
    request_id: str = Field(pattern=_UUID_PATTERN)
    session_id: str = ""
    files: list[FileAttachment] | None = None
    ephemeral: bool = False  # skip conversation/message storage (e.g. quick-add)


class DailyLogCreate(BaseModel):
    user_id: str = Field(pattern=_UUID_PATTERN)
    log_date: str | None = None
    meal_type: str = Field(max_length=50)
    food_name: str = Field(max_length=200)
    quantity: float = 1
    unit: str = Field("portion", max_length=30)
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    source: str = Field("openfoodfacts", max_length=50)
    meal_plan_id: str | None = Field(default=None, pattern=_UUID_PATTERN)


class DailyLogUpdate(BaseModel):
    meal_type: str | None = Field(None, max_length=50)
    food_name: str | None = Field(None, max_length=200)
    quantity: float | None = None
    unit: str | None = Field(None, max_length=30)
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


class FavoriteCreate(BaseModel):
    user_id: str = Field(pattern=_UUID_PATTERN)
    recipe_id: str = Field(pattern=_UUID_PATTERN)
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
    name: str = Field(max_length=200)
    quantity: float = 0
    unit: str = Field("", max_length=30)
    category: str = Field("other", max_length=50)
    checked: bool = False


class ShoppingListCreate(BaseModel):
    user_id: str = Field(pattern=_UUID_PATTERN)
    meal_plan_id: str | None = Field(default=None, pattern=_UUID_PATTERN)
    title: str = Field(max_length=200)
    items: list[ShoppingListItemModel]


class ShoppingListUpdate(BaseModel):
    title: str | None = None
    items: list[ShoppingListItemModel] | None = None
