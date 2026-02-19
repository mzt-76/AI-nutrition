"""Pydantic-evals test suite for migrated skill script execution logic.

Tests the execute() functions of 5 migrated skill scripts across diverse
scenarios, validating correctness, error handling, and safety constraints.

Scripts tested:
    - nutrition-calculating/calculate_nutritional_needs.py (pure calc)
    - knowledge-searching/retrieve_relevant_documents.py (mocked DB + embedding)
    - knowledge-searching/web_search.py (mocked HTTP)
    - body-analyzing/image_analysis.py (mocked OpenAI Vision)
    - weekly-coaching/calculate_weekly_adjustments.py (mocked DB)
"""

import asyncio
import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import (
    Evaluator,
    EvaluationReason,
    EvaluatorContext,
    MaxDuration,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = {
    "nutritional_needs": (
        PROJECT_ROOT
        / "skills"
        / "nutrition-calculating"
        / "scripts"
        / "calculate_nutritional_needs.py"
    ),
    "retrieve_documents": (
        PROJECT_ROOT
        / "skills"
        / "knowledge-searching"
        / "scripts"
        / "retrieve_relevant_documents.py"
    ),
    "web_search": (
        PROJECT_ROOT
        / "skills"
        / "knowledge-searching"
        / "scripts"
        / "web_search.py"
    ),
    "image_analysis": (
        PROJECT_ROOT
        / "skills"
        / "body-analyzing"
        / "scripts"
        / "image_analysis.py"
    ),
    "weekly_adjustments": (
        PROJECT_ROOT
        / "skills"
        / "weekly-coaching"
        / "scripts"
        / "calculate_weekly_adjustments.py"
    ),
}

_module_cache: dict[str, object] = {}


def _load_script(script_path: Path):
    """Load a skill script module via importlib (cached)."""
    key = str(script_path)
    if key not in _module_cache:
        spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _module_cache[key] = module
    return _module_cache[key]


# ---------------------------------------------------------------------------
# Custom evaluators
# ---------------------------------------------------------------------------


@dataclass
class ContainsSubstring(Evaluator):
    """Assert that the output string contains a specific substring."""

    substring: str
    case_sensitive: bool = True
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        target = self.substring
        haystack = output if self.case_sensitive else output.lower()
        needle = target if self.case_sensitive else target.lower()
        if needle in haystack:
            return EvaluationReason(value=True, reason=f"Found '{target}'")
        return EvaluationReason(
            value=False,
            reason=f"'{target}' not found in output ({len(output)} chars)",
        )


@dataclass
class NoError(Evaluator):
    """Assert that output does not start with 'Error'."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        output = str(ctx.output)
        if not output.startswith("Error"):
            return EvaluationReason(value=True, reason="No error prefix")
        return EvaluationReason(value=False, reason=f"Error response: {output[:120]}")


@dataclass
class MinLength(Evaluator):
    """Assert that output string meets a minimum length."""

    min_chars: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        length = len(str(ctx.output))
        if length >= self.min_chars:
            return EvaluationReason(
                value=True, reason=f"{length} chars >= {self.min_chars}"
            )
        return EvaluationReason(
            value=False,
            reason=f"Output too short: {length} chars < {self.min_chars}",
        )


@dataclass
class IsValidJSON(Evaluator):
    """Assert that the output is valid JSON."""

    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            json.loads(str(ctx.output))
            return EvaluationReason(value=True, reason="Valid JSON")
        except (json.JSONDecodeError, TypeError) as e:
            return EvaluationReason(value=False, reason=f"Invalid JSON: {e}")


@dataclass
class JSONHasKey(Evaluator):
    """Assert that parsed JSON output contains a specific key."""

    key: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            data = json.loads(str(ctx.output))
        except (json.JSONDecodeError, TypeError):
            return EvaluationReason(value=False, reason="Output is not valid JSON")
        if isinstance(data, dict) and self.key in data:
            return EvaluationReason(value=True, reason=f"Key '{self.key}' present")
        return EvaluationReason(value=False, reason=f"Key '{self.key}' not found")


@dataclass
class JSONFieldEquals(Evaluator):
    """Assert that a specific JSON field matches an expected string value."""

    key: str
    expected: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            data = json.loads(str(ctx.output))
        except (json.JSONDecodeError, TypeError):
            return EvaluationReason(value=False, reason="Output is not valid JSON")
        if not isinstance(data, dict):
            return EvaluationReason(value=False, reason="JSON is not an object")
        actual = data.get(self.key)
        if str(actual) == str(self.expected):
            return EvaluationReason(
                value=True, reason=f"{self.key}='{actual}' matches"
            )
        return EvaluationReason(
            value=False,
            reason=f"{self.key}='{actual}', expected '{self.expected}'",
        )


@dataclass
class CaloriesInRange(Evaluator):
    """Assert that target_calories in JSON output falls within safe bounds."""

    min_cal: int
    max_cal: int
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            data = json.loads(str(ctx.output))
        except (json.JSONDecodeError, TypeError):
            return EvaluationReason(value=False, reason="Output is not valid JSON")
        calories = data.get("target_calories") if isinstance(data, dict) else None
        if calories is None:
            return EvaluationReason(value=False, reason="No target_calories field")
        if self.min_cal <= calories <= self.max_cal:
            return EvaluationReason(
                value=True,
                reason=f"Calories {calories} in [{self.min_cal}, {self.max_cal}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"Calories {calories} outside [{self.min_cal}, {self.max_cal}]",
        )


@dataclass
class JSONErrorCode(Evaluator):
    """Assert that JSON output has a specific error code."""

    code: str
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            data = json.loads(str(ctx.output))
        except (json.JSONDecodeError, TypeError):
            return EvaluationReason(value=False, reason="Output is not valid JSON")
        actual_code = data.get("code") if isinstance(data, dict) else None
        if actual_code == self.code:
            return EvaluationReason(
                value=True, reason=f"Error code '{self.code}' found"
            )
        return EvaluationReason(
            value=False,
            reason=f"Expected code '{self.code}', got '{actual_code}'",
        )


@dataclass
class JSONNumericFieldInRange(Evaluator):
    """Assert that a numeric JSON field is within a given range."""

    key: str
    min_val: float
    max_val: float
    evaluation_name: str | None = field(default=None)

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            data = json.loads(str(ctx.output))
        except (json.JSONDecodeError, TypeError):
            return EvaluationReason(value=False, reason="Output is not valid JSON")
        value = data.get(self.key) if isinstance(data, dict) else None
        if value is None:
            return EvaluationReason(value=False, reason=f"Key '{self.key}' not found")
        try:
            num = float(value)
        except (TypeError, ValueError):
            return EvaluationReason(
                value=False, reason=f"'{self.key}' is not numeric: {value}"
            )
        if self.min_val <= num <= self.max_val:
            return EvaluationReason(
                value=True,
                reason=f"{self.key}={num} in [{self.min_val}, {self.max_val}]",
            )
        return EvaluationReason(
            value=False,
            reason=f"{self.key}={num} outside [{self.min_val}, {self.max_val}]",
        )


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _mock_supabase_rpc(docs=None):
    """Build a mock Supabase client for RPC calls (retrieve_relevant_documents)."""
    mock = MagicMock()
    mock.rpc.return_value.execute.return_value = MagicMock(
        data=docs if docs is not None else []
    )
    return mock


def _mock_supabase_tables(profile_data=None, history_data=None, learning_data=None):
    """Build a mock Supabase client with configurable table responses."""
    mock = MagicMock()
    _cache: dict[str, MagicMock] = {}

    def _make_table(name: str) -> MagicMock:
        t = MagicMock()
        if name == "my_profile":
            t.select.return_value.limit.return_value.execute.return_value = MagicMock(
                data=profile_data if profile_data is not None else []
            )
        elif name == "weekly_feedback":
            # SELECT chain: .select().order().limit().execute()
            t.select.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(
                data=history_data if history_data is not None else []
            )
            # INSERT chain: .insert().execute()
            t.insert.return_value.execute.return_value = MagicMock(data=[])
        elif name == "user_learning_profile":
            # SELECT chain: .select().limit().execute()
            t.select.return_value.limit.return_value.execute.return_value = MagicMock(
                data=learning_data if learning_data is not None else []
            )
            # UPDATE chain: .update().eq().execute()
            t.update.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            # UPSERT chain: .upsert().execute()
            t.upsert.return_value.execute.return_value = MagicMock(data=[])
        return t

    def _table_fn(name: str) -> MagicMock:
        if name not in _cache:
            _cache[name] = _make_table(name)
        return _cache[name]

    mock.table = MagicMock(side_effect=_table_fn)
    return mock


def _mock_embedding_client(embedding=None, raise_error=False):
    """Build a mock AsyncOpenAI client returning a fixed embedding vector."""
    mock = AsyncMock()
    if raise_error:
        mock.embeddings.create = AsyncMock(
            side_effect=Exception("Embedding API error")
        )
    else:
        if embedding is None:
            embedding = [0.1] * 1536
        response = MagicMock()
        response.data = [MagicMock(embedding=embedding)]
        mock.embeddings.create = AsyncMock(return_value=response)
    return mock


def _mock_http_client(json_response=None, raise_error=None):
    """Build a mock httpx.AsyncClient with configurable get() response."""
    mock = AsyncMock()
    if raise_error:
        mock.get = AsyncMock(side_effect=raise_error)
    else:
        response = MagicMock()
        response.json.return_value = json_response or {}
        response.raise_for_status = MagicMock()
        mock.get = AsyncMock(return_value=response)
    return mock


def _mock_openai_client(content=None, raise_error=None):
    """Build a mock AsyncOpenAI client for chat completions."""
    mock = AsyncMock()
    if raise_error:
        mock.chat.completions.create = AsyncMock(side_effect=raise_error)
    else:
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content=content or ""))]
        mock.chat.completions.create = AsyncMock(return_value=response)
    return mock


# ---------------------------------------------------------------------------
# Task functions
# ---------------------------------------------------------------------------


async def _nutritional_needs_task(inputs: dict) -> str:
    """Task: calculate nutritional needs (pure calculation, no mocking)."""
    module = _load_script(SCRIPTS["nutritional_needs"])
    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    return await module.execute(**params)


async def _retrieve_documents_task(inputs: dict) -> str:
    """Task: retrieve documents via RAG (mocked supabase + embedding)."""
    rpc_docs = inputs.get("_rpc_docs")
    embedding_error = inputs.get("_embedding_error", False)

    supabase = _mock_supabase_rpc(docs=rpc_docs)
    embedding_client = _mock_embedding_client(raise_error=embedding_error)

    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    module = _load_script(SCRIPTS["retrieve_documents"])
    return await module.execute(
        supabase=supabase, embedding_client=embedding_client, **params
    )


async def _web_search_task(inputs: dict) -> str:
    """Task: web search via Brave API (mocked http client)."""
    response_json = inputs.get("_response_json", {})
    http_error = inputs.get("_http_error", False)

    if http_error:
        http_client = _mock_http_client(
            raise_error=Exception("Connection timeout")
        )
    else:
        http_client = _mock_http_client(json_response=response_json)

    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    module = _load_script(SCRIPTS["web_search"])
    return await module.execute(http_client=http_client, **params)


async def _image_analysis_task(inputs: dict) -> str:
    """Task: image analysis via GPT-4 Vision (mocked OpenAI client)."""
    response_content = inputs.get("_response_content", "")
    openai_error = inputs.get("_openai_error", False)

    if openai_error:
        openai_client = _mock_openai_client(
            raise_error=Exception("Vision API error")
        )
    else:
        openai_client = _mock_openai_client(content=response_content)

    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    module = _load_script(SCRIPTS["image_analysis"])
    return await module.execute(openai_client=openai_client, **params)


async def _weekly_adjustments_task(inputs: dict) -> str:
    """Task: weekly adjustments (mocked supabase tables)."""
    profile_data = inputs.get("_profile", [])
    history_data = inputs.get("_history", [])
    learning_data = inputs.get("_learning", [])

    supabase = _mock_supabase_tables(profile_data, history_data, learning_data)

    params = {k: v for k, v in inputs.items() if not k.startswith("_")}
    module = _load_script(SCRIPTS["weekly_adjustments"])
    return await module.execute(supabase=supabase, **params)


# ---------------------------------------------------------------------------
# Dataset 1: Nutritional needs (10 cases, no mocking)
# ---------------------------------------------------------------------------

# Verified calculations (Mifflin-St Jeor + activity multipliers):
#   male 35y 87kg 178cm moderate: BMR=1812, TDEE=2808, muscle_gain→3108
#   female 28y 70kg 165cm light:  BMR=1430, TDEE=1966, weight_loss→1466
#   male 50y 95kg 180cm sedentary: BMR=1830, TDEE=2196, maintenance→2196
#   female 22y 58kg 170cm active:  BMR=1371, TDEE=2364, performance→2364
#   male 40y 100kg 175cm moderate: BMR=1898, TDEE=2941, weight_loss→2441
#   male 30y 80kg 180cm moderate:  BMR=1780, TDEE=2759, muscle_gain→3059
#   female 25y 45kg 155cm sedentary: BMR=1132, TDEE=1358, maintenance→1358


def nutritional_needs_dataset() -> Dataset:
    """Dataset: 10 cases testing BMR/TDEE/macro calculation and validation."""
    return Dataset(
        name="nutritional_needs",
        cases=[
            Case(
                name="male_moderate_muscle_gain",
                inputs={
                    "age": 35,
                    "gender": "male",
                    "weight_kg": 87,
                    "height_cm": 178,
                    "activity_level": "moderate",
                    "activities": ["musculation"],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="muscle_gain"),
                    JSONNumericFieldInRange(key="bmr", min_val=1700, max_val=1900),
                    JSONNumericFieldInRange(key="tdee", min_val=2600, max_val=3000),
                    CaloriesInRange(min_cal=2900, max_cal=3300),
                ),
            ),
            Case(
                name="female_light_weight_loss",
                inputs={
                    "age": 28,
                    "gender": "female",
                    "weight_kg": 70,
                    "height_cm": 165,
                    "activity_level": "light",
                    "context": "je veux perdre du poids",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="weight_loss"),
                    CaloriesInRange(min_cal=1200, max_cal=1800),
                ),
            ),
            Case(
                name="male_sedentary_maintenance",
                inputs={
                    "age": 50,
                    "gender": "male",
                    "weight_kg": 95,
                    "height_cm": 180,
                    "activity_level": "sedentary",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="maintenance"),
                    CaloriesInRange(min_cal=2000, max_cal=2400),
                ),
            ),
            Case(
                name="female_active_performance",
                inputs={
                    "age": 22,
                    "gender": "female",
                    "weight_kg": 58,
                    "height_cm": 170,
                    "activity_level": "active",
                    "activities": ["basket"],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="performance"),
                    CaloriesInRange(min_cal=2100, max_cal=2600),
                ),
            ),
            Case(
                name="explicit_weight_loss_goal",
                inputs={
                    "age": 40,
                    "gender": "male",
                    "weight_kg": 100,
                    "height_cm": 175,
                    "activity_level": "moderate",
                    "goals": {"weight_loss": 10},
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="weight_loss"),
                    CaloriesInRange(min_cal=2200, max_cal=2600),
                ),
            ),
            Case(
                name="context_muscle_gain_french",
                inputs={
                    "age": 30,
                    "gender": "male",
                    "weight_kg": 80,
                    "height_cm": 180,
                    "activity_level": "moderate",
                    "context": "prise de masse",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="primary_goal", expected="muscle_gain"),
                    CaloriesInRange(min_cal=2800, max_cal=3300),
                ),
            ),
            Case(
                name="safety_min_calories_female",
                inputs={
                    "age": 25,
                    "gender": "female",
                    "weight_kg": 45,
                    "height_cm": 155,
                    "activity_level": "sedentary",
                },
                evaluators=(
                    IsValidJSON(),
                    CaloriesInRange(min_cal=1200, max_cal=1600),
                ),
            ),
            Case(
                name="edge_age_18",
                inputs={
                    "age": 18,
                    "gender": "male",
                    "weight_kg": 70,
                    "height_cm": 175,
                    "activity_level": "moderate",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="bmr"),
                    JSONHasKey(key="tdee"),
                    JSONHasKey(key="target_calories"),
                ),
            ),
            Case(
                name="invalid_age_under_18",
                inputs={
                    "age": 15,
                    "gender": "male",
                    "weight_kg": 70,
                    "height_cm": 175,
                    "activity_level": "moderate",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONErrorCode(code="VALIDATION_ERROR"),
                    JSONHasKey(key="error"),
                ),
            ),
            Case(
                name="invalid_weight_too_low",
                inputs={
                    "age": 30,
                    "gender": "male",
                    "weight_kg": 30,
                    "height_cm": 175,
                    "activity_level": "moderate",
                },
                evaluators=(
                    IsValidJSON(),
                    JSONErrorCode(code="VALIDATION_ERROR"),
                    JSONHasKey(key="error"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 2: Retrieve documents (4 cases, mocked DB + embedding)
# ---------------------------------------------------------------------------


def retrieve_documents_dataset() -> Dataset:
    """Dataset: 4 cases testing RAG document retrieval."""
    return Dataset(
        name="retrieve_documents",
        cases=[
            Case(
                name="documents_found",
                inputs={
                    "user_query": "What is protein and why is it important?",
                    "_rpc_docs": [
                        {
                            "content": "Document 1: Protein is an essential macronutrient composed of amino acids.",
                            "similarity": 0.85,
                        },
                        {
                            "content": "Document 2: Amino acids are the building blocks of protein.",
                            "similarity": 0.72,
                        },
                    ],
                },
                evaluators=(
                    ContainsSubstring(substring="Document 1"),
                    ContainsSubstring(substring="Document 2"),
                    MinLength(min_chars=50),
                    ContainsSubstring(substring="0.85"),
                ),
            ),
            Case(
                name="no_documents",
                inputs={
                    "user_query": "extremely obscure query xyz",
                    "_rpc_docs": [],
                },
                evaluators=(
                    ContainsSubstring(
                        substring="No relevant documents", case_sensitive=False
                    ),
                ),
            ),
            Case(
                name="below_threshold",
                inputs={
                    "user_query": "vague query about something",
                    "_rpc_docs": [
                        {"content": "Doc A about cooking", "similarity": 0.3},
                        {"content": "Doc B about exercise", "similarity": 0.4},
                    ],
                },
                evaluators=(
                    ContainsSubstring(
                        substring="No sufficiently relevant", case_sensitive=False
                    ),
                ),
            ),
            Case(
                name="api_error",
                inputs={
                    "user_query": "test query",
                    "_embedding_error": True,
                },
                evaluators=(
                    ContainsSubstring(
                        substring="Error retrieving", case_sensitive=False
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 3: Web search (4 cases, mocked HTTP)
# ---------------------------------------------------------------------------


def web_search_dataset() -> Dataset:
    """Dataset: 4 cases testing Brave web search."""
    return Dataset(
        name="web_search",
        cases=[
            Case(
                name="results_found",
                inputs={
                    "query": "protein benefits nutrition",
                    "brave_api_key": "test-key-123",
                    "_response_json": {
                        "web": {
                            "results": [
                                {
                                    "title": "Protein Guide",
                                    "description": "Complete guide to protein intake",
                                    "url": "https://example.com/protein",
                                },
                                {
                                    "title": "Nutrition Tips",
                                    "description": "Top nutrition tips for athletes",
                                    "url": "https://example.com/nutrition",
                                },
                                {
                                    "title": "Health Benefits",
                                    "description": "Health benefits of high protein",
                                    "url": "https://example.com/health",
                                },
                            ]
                        }
                    },
                },
                evaluators=(
                    ContainsSubstring(substring="1."),
                    ContainsSubstring(substring="Protein Guide"),
                    MinLength(min_chars=50),
                ),
            ),
            Case(
                name="no_results",
                inputs={
                    "query": "xyznonexistentquery123",
                    "brave_api_key": "test-key-123",
                    "_response_json": {"web": {"results": []}},
                },
                evaluators=(
                    ContainsSubstring(
                        substring="No search results", case_sensitive=False
                    ),
                ),
            ),
            Case(
                name="no_api_key",
                inputs={
                    "query": "test query",
                    "_response_json": {},
                },
                evaluators=(
                    ContainsSubstring(
                        substring="unavailable", case_sensitive=False
                    ),
                ),
            ),
            Case(
                name="api_error",
                inputs={
                    "query": "test query",
                    "brave_api_key": "test-key-123",
                    "_http_error": True,
                },
                evaluators=(
                    ContainsSubstring(
                        substring="Web search error", case_sensitive=False
                    ),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 4: Image analysis (3 cases, mocked OpenAI Vision)
# ---------------------------------------------------------------------------


def image_analysis_dataset() -> Dataset:
    """Dataset: 3 cases testing GPT-4 Vision image analysis."""
    return Dataset(
        name="image_analysis",
        cases=[
            Case(
                name="successful_analysis",
                inputs={
                    "image_url": "https://example.com/body_photo.jpg",
                    "analysis_prompt": "Estimate body fat percentage from this photo",
                    "_response_content": (
                        "Based on the image analysis, the estimated body fat "
                        "percentage is approximately 15-18%. The subject shows "
                        "visible muscle definition in the arms and shoulders."
                    ),
                },
                evaluators=(
                    MinLength(min_chars=20),
                    NoError(),
                    ContainsSubstring(substring="body fat"),
                ),
            ),
            Case(
                name="api_error",
                inputs={
                    "image_url": "https://example.com/broken.jpg",
                    "analysis_prompt": "Analyze body composition",
                    "_openai_error": True,
                },
                evaluators=(
                    ContainsSubstring(
                        substring="Image analysis error", case_sensitive=False
                    ),
                ),
            ),
            Case(
                name="empty_response",
                inputs={
                    "image_url": "https://example.com/empty.jpg",
                    "analysis_prompt": "Analyze this image",
                    "_response_content": "",
                },
                evaluators=(NoError(),),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 5: Weekly adjustments (7 cases, mocked DB)
# ---------------------------------------------------------------------------

# Shared profile fixtures
_WEIGHT_LOSS_PROFILE = {
    "primary_goal": "weight_loss",
    "current_protein_g": 150,
    "current_carbs_g": 350,
    "current_fat_g": 90,
    "tdee": 2868,
}

_MUSCLE_GAIN_PROFILE = {
    "primary_goal": "muscle_gain",
    "current_protein_g": 180,
    "current_carbs_g": 350,
    "current_fat_g": 80,
    "tdee": 2868,
}


def weekly_adjustments_dataset() -> Dataset:
    """Dataset: 7 cases testing weekly coaching adjustments."""
    return Dataset(
        name="weekly_adjustments",
        cases=[
            Case(
                name="optimal_weight_loss",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 86.5,
                    "adherence_percent": 85,
                    "hunger_level": "medium",
                    "energy_level": "medium",
                    "sleep_quality": "good",
                    "_profile": [_WEIGHT_LOSS_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="status", expected="success"),
                    JSONNumericFieldInRange(
                        key="confidence_level", min_val=0.2, max_val=0.5
                    ),
                ),
            ),
            Case(
                name="too_fast_weight_loss",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 85.5,
                    "adherence_percent": 90,
                    "hunger_level": "medium",
                    "energy_level": "medium",
                    "sleep_quality": "good",
                    "_profile": [_WEIGHT_LOSS_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="status", expected="success"),
                    # Calorie adjustment should be +100 (reduce deficit)
                    JSONHasKey(key="adjustments"),
                ),
            ),
            Case(
                name="muscle_gain_on_track",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 87.3,
                    "adherence_percent": 90,
                    "hunger_level": "medium",
                    "energy_level": "high",
                    "sleep_quality": "good",
                    "_profile": [_MUSCLE_GAIN_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="status", expected="success"),
                    JSONHasKey(key="analysis"),
                ),
            ),
            Case(
                name="high_hunger_low_adherence",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 86.8,
                    "adherence_percent": 35,
                    "hunger_level": "high",
                    "energy_level": "low",
                    "sleep_quality": "fair",
                    "_profile": [_WEIGHT_LOSS_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="status", expected="success"),
                    # extreme_hunger flag: hunger=high + adherence=35 < 40
                    JSONHasKey(key="red_flags"),
                ),
            ),
            Case(
                name="no_profile_found",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 86.5,
                    "adherence_percent": 85,
                    "hunger_level": "medium",
                    "energy_level": "medium",
                    "sleep_quality": "good",
                    "_profile": [],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONErrorCode(code="PROFILE_NOT_FOUND"),
                ),
            ),
            Case(
                name="first_week_no_history",
                inputs={
                    "weight_start_kg": 87.0,
                    "weight_end_kg": 86.7,
                    "adherence_percent": 80,
                    "hunger_level": "medium",
                    "energy_level": "medium",
                    "sleep_quality": "good",
                    "_profile": [_WEIGHT_LOSS_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="status", expected="success"),
                    JSONNumericFieldInRange(
                        key="week_number", min_val=1, max_val=1
                    ),
                    JSONNumericFieldInRange(
                        key="confidence_level", min_val=0.2, max_val=0.5
                    ),
                ),
            ),
            Case(
                name="validation_error",
                inputs={
                    "weight_start_kg": 20.0,
                    "weight_end_kg": 19.5,
                    "adherence_percent": 85,
                    "_profile": [_WEIGHT_LOSS_PROFILE],
                    "_history": [],
                    "_learning": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONErrorCode(code="VALIDATION_ERROR"),
                    JSONHasKey(key="error"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=5.0)],
    )


# ---------------------------------------------------------------------------
# Pytest test functions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nutritional_needs_eval():
    """Eval: BMR/TDEE/macro calculations across 10 diverse scenarios."""
    dataset = nutritional_needs_dataset()
    report = await dataset.evaluate(task=_nutritional_needs_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_retrieve_documents_eval():
    """Eval: RAG document retrieval with mocked DB and embeddings."""
    dataset = retrieve_documents_dataset()
    report = await dataset.evaluate(task=_retrieve_documents_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_web_search_eval():
    """Eval: Web search with mocked Brave API responses."""
    dataset = web_search_dataset()
    report = await dataset.evaluate(task=_web_search_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_image_analysis_eval():
    """Eval: GPT-4 Vision image analysis with mocked OpenAI client."""
    dataset = image_analysis_dataset()
    report = await dataset.evaluate(task=_image_analysis_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_weekly_adjustments_eval():
    """Eval: Weekly coaching adjustments with mocked Supabase tables."""
    dataset = weekly_adjustments_dataset()
    report = await dataset.evaluate(task=_weekly_adjustments_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


# ---------------------------------------------------------------------------
# Dataset 6: select_recipes (3 cases, mocked DB)
# ---------------------------------------------------------------------------

_SELECT_RECIPES_SCRIPT = (
    PROJECT_ROOT / "skills" / "meal-planning" / "scripts" / "select_recipes.py"
)

_SAMPLE_RECIPE = {
    "id": "recipe-uuid-test",
    "name": "Omelette protéinée",
    "meal_type": "petit-dejeuner",
    "calories_per_serving": 450.0,
    "protein_g_per_serving": 30.0,
    "carbs_g_per_serving": 10.0,
    "fat_g_per_serving": 32.0,
    "ingredients": [{"name": "oeufs", "quantity": 3, "unit": "pièces"}],
    "instructions": "Cuire.",
    "allergen_tags": ["oeuf"],
    "usage_count": 5,
    "off_validated": True,
    "cuisine_type": "française",
    "diet_type": "omnivore",
    "tags": [],
}

_SAMPLE_MEAL_TARGETS = [
    {
        "meal_type": "Petit-déjeuner",
        "time": "08:00",
        "target_calories": 700,
        "target_protein_g": 45,
        "target_carbs_g": 80,
        "target_fat_g": 25,
    }
]


async def _select_recipes_task(inputs: dict) -> str:
    """Task wrapper for select_recipes.execute()."""
    from unittest.mock import patch, AsyncMock

    module = _load_script(_SELECT_RECIPES_SCRIPT)
    mock_recipes = inputs.get("_mock_recipes", [])

    supabase = MagicMock()

    with patch(
        "src.nutrition.recipe_db.search_recipes",
        new=AsyncMock(return_value=mock_recipes),
    ):
        return await module.execute(
            supabase=supabase,
            meal_targets=inputs.get("meal_targets", _SAMPLE_MEAL_TARGETS),
            user_allergens=inputs.get("user_allergens", []),
            diet_type=inputs.get("diet_type", "omnivore"),
            exclude_recipe_ids=inputs.get("exclude_recipe_ids", []),
        )


def select_recipes_dataset() -> Dataset:
    """Dataset: 3 cases for select_recipes script."""
    return Dataset(
        name="select_recipes",
        cases=[
            Case(
                name="happy_path_db_match",
                inputs={
                    "meal_targets": _SAMPLE_MEAL_TARGETS,
                    "user_allergens": [],
                    "_mock_recipes": [_SAMPLE_RECIPE],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="day_recipes"),
                    JSONHasKey(key="unmatched_slots"),
                    JSONFieldEquals(key="unmatched_slots", expected="0"),
                ),
            ),
            Case(
                name="no_db_match",
                inputs={
                    "meal_targets": _SAMPLE_MEAL_TARGETS,
                    "user_allergens": [],
                    "_mock_recipes": [],
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="unmatched_slots"),
                    JSONFieldEquals(key="unmatched_slots", expected="1"),
                ),
            ),
            Case(
                name="allergen_exclusion",
                inputs={
                    "meal_targets": _SAMPLE_MEAL_TARGETS,
                    "user_allergens": ["oeuf"],
                    "_mock_recipes": [_SAMPLE_RECIPE],  # Has "oeuf" allergen tag
                },
                evaluators=(
                    IsValidJSON(),
                    # Recipe with "oeuf" tag should be excluded → unmatched
                    JSONFieldEquals(key="unmatched_slots", expected="1"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 7: scale_portions (3 cases, pure math)
# ---------------------------------------------------------------------------

_SCALE_PORTIONS_SCRIPT = (
    PROJECT_ROOT / "skills" / "meal-planning" / "scripts" / "scale_portions.py"
)


async def _scale_portions_task(inputs: dict) -> str:
    """Task wrapper for scale_portions.execute()."""
    module = _load_script(_SCALE_PORTIONS_SCRIPT)
    return await module.execute(
        recipe=inputs.get("recipe", _SAMPLE_RECIPE),
        target_calories=inputs.get("target_calories", 675),
        target_protein_g=inputs.get("target_protein_g", 45),
        target_carbs_g=inputs.get("target_carbs_g"),
        target_fat_g=inputs.get("target_fat_g"),
    )


def scale_portions_dataset() -> Dataset:
    """Dataset: 3 cases for scale_portions script."""
    return Dataset(
        name="scale_portions",
        cases=[
            Case(
                name="scale_up_1_5x",
                inputs={
                    "recipe": _SAMPLE_RECIPE,
                    "target_calories": 675,  # 450 * 1.5
                    "target_protein_g": 45,
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="scaled_recipe"),
                    JSONHasKey(key="scale_factor"),
                    JSONHasKey(key="nutrition_after"),
                    # scale factor should be close to 1.5
                    JSONNumericFieldInRange(key="scale_factor", min_val=1.4, max_val=1.6),
                ),
            ),
            Case(
                name="scale_down_0_5x",
                inputs={
                    "recipe": _SAMPLE_RECIPE,
                    "target_calories": 225,  # 450 * 0.5 → clamped at MIN (0.5)
                    "target_protein_g": 15,
                },
                evaluators=(
                    IsValidJSON(),
                    JSONNumericFieldInRange(key="scale_factor", min_val=0.49, max_val=0.51),
                ),
            ),
            Case(
                name="empty_recipe_error",
                inputs={
                    "recipe": {},
                    "target_calories": 600,
                    "target_protein_g": 40,
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="error"),
                    JSONErrorCode(code="VALIDATION_ERROR"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Dataset 8: validate_day (3 cases)
# ---------------------------------------------------------------------------

_VALIDATE_DAY_SCRIPT = (
    PROJECT_ROOT / "skills" / "meal-planning" / "scripts" / "validate_day.py"
)

_VALID_DAY_PLAN = {
    "day": "Lundi",
    "date": "2026-02-18",
    "meals": [
        {
            "meal_type": "Déjeuner",
            "name": "Poulet grillé",
            "ingredients": [{"name": "poulet", "quantity": 150, "unit": "g"}],
            "nutrition": {"calories": 2800, "protein_g": 175, "carbs_g": 350, "fat_g": 80},
        }
    ],
    "daily_totals": {"calories": 2800.0, "protein_g": 175.0, "carbs_g": 350.0, "fat_g": 80.0},
}


async def _validate_day_task(inputs: dict) -> str:
    """Task wrapper for validate_day.execute()."""
    module = _load_script(_VALIDATE_DAY_SCRIPT)
    return await module.execute(
        day_plan=inputs.get("day_plan", _VALID_DAY_PLAN),
        user_allergens=inputs.get("user_allergens", []),
        target_macros=inputs.get("target_macros", {}),
        protein_tolerance=inputs.get("protein_tolerance", 0.05),
        other_tolerance=inputs.get("other_tolerance", 0.10),
    )


def validate_day_dataset() -> Dataset:
    """Dataset: 3 cases for validate_day script."""
    return Dataset(
        name="validate_day",
        cases=[
            Case(
                name="valid_day_no_allergens",
                inputs={
                    "day_plan": _VALID_DAY_PLAN,
                    "user_allergens": [],
                    "target_macros": {
                        "calories": 2800,
                        "protein_g": 175,
                        "carbs_g": 350,
                        "fat_g": 80,
                    },
                },
                evaluators=(
                    IsValidJSON(),
                    JSONHasKey(key="valid"),
                    JSONHasKey(key="violations"),
                    JSONFieldEquals(key="valid", expected="True"),
                    JSONFieldEquals(key="day", expected="Lundi"),
                ),
            ),
            Case(
                name="allergen_violation",
                inputs={
                    "day_plan": {
                        "day": "Mardi",
                        "date": "2026-02-19",
                        "meals": [
                            {
                                "meal_type": "Déjeuner",
                                "name": "Pâtes au beurre",
                                "ingredients": [
                                    {"name": "beurre", "quantity": 30, "unit": "g"}
                                ],
                                "nutrition": {"calories": 500, "protein_g": 5, "carbs_g": 60, "fat_g": 25},
                            }
                        ],
                        "daily_totals": {"calories": 500, "protein_g": 5, "carbs_g": 60, "fat_g": 25},
                    },
                    "user_allergens": ["lactose"],
                    "target_macros": {},
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="valid", expected="False"),
                    JSONHasKey(key="allergen_violations"),
                ),
            ),
            Case(
                name="macro_violation",
                inputs={
                    "day_plan": {
                        "day": "Mercredi",
                        "date": "2026-02-20",
                        "meals": [],
                        "daily_totals": {"calories": 500, "protein_g": 30, "carbs_g": 50, "fat_g": 15},
                    },
                    "user_allergens": [],
                    # Target 2800 kcal — 500 is way outside 10% tolerance
                    "target_macros": {"calories": 2800, "protein_g": 175, "carbs_g": 350, "fat_g": 80},
                },
                evaluators=(
                    IsValidJSON(),
                    JSONFieldEquals(key="valid", expected="False"),
                    JSONHasKey(key="macro_violations"),
                ),
            ),
        ],
        evaluators=[MaxDuration(seconds=2.0)],
    )


# ---------------------------------------------------------------------------
# Eval runner tests for new datasets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_select_recipes_eval():
    """Eval: select_recipes script with mocked recipe DB."""
    dataset = select_recipes_dataset()
    report = await dataset.evaluate(task=_select_recipes_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_scale_portions_eval():
    """Eval: scale_portions script — pure mathematical scaling."""
    dataset = scale_portions_dataset()
    report = await dataset.evaluate(task=_scale_portions_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


@pytest.mark.asyncio
async def test_validate_day_eval():
    """Eval: validate_day script — allergen and macro validation."""
    dataset = validate_day_dataset()
    report = await dataset.evaluate(task=_validate_day_task)
    report.print()
    assert len(report.failures) == 0, f"Failures: {[f.name for f in report.failures]}"


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    async def run_all_evals():
        """Run all 5 eval suites and print reports."""
        suites = [
            ("Nutritional Needs", nutritional_needs_dataset(), _nutritional_needs_task),
            ("Retrieve Documents", retrieve_documents_dataset(), _retrieve_documents_task),
            ("Web Search", web_search_dataset(), _web_search_task),
            ("Image Analysis", image_analysis_dataset(), _image_analysis_task),
            ("Weekly Adjustments", weekly_adjustments_dataset(), _weekly_adjustments_task),
            ("Select Recipes", select_recipes_dataset(), _select_recipes_task),
            ("Scale Portions", scale_portions_dataset(), _scale_portions_task),
            ("Validate Day", validate_day_dataset(), _validate_day_task),
        ]

        total_failures = 0
        for name, dataset, task in suites:
            print(f"\n{'=' * 60}")
            print(f"  {name}")
            print(f"{'=' * 60}")
            report = await dataset.evaluate(task=task)
            report.print()
            total_failures += len(report.failures)

        print(f"\n{'=' * 60}")
        print(f"  Total failures: {total_failures}")
        print(f"{'=' * 60}")

    asyncio.run(run_all_evals())
