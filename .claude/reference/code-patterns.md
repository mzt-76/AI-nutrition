# Common Code Patterns

**Purpose:** Copy-paste reference for frequently used patterns in the AI Nutrition Assistant project.

---

## Pattern 1: Pydantic AI Tool

```python
@dataclass
class AgentDeps:
    supabase: Client
    http_client: AsyncClient

agent = Agent(get_model(), system_prompt=PROMPT, deps_type=AgentDeps, retries=2)

@agent.tool
async def calculate_nutritional_needs(
    ctx: RunContext[AgentDeps],
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: int,
    activity_level: str
) -> str:
    """Calculate BMR/TDEE using Mifflin-St Jeor. Returns JSON string."""
    logger.info(f"Calculating nutrition for age={age}, weight={weight_kg}kg")

    if not 18 <= age <= 100:
        raise ValueError("Age must be between 18 and 100")

    bmr = mifflin_st_jeor_bmr(age, gender, weight_kg, height_cm)
    tdee = calculate_tdee(bmr, activity_level)

    return json.dumps({"bmr": bmr, "tdee": tdee, "target_calories": tdee + 300})
```

---

## Pattern 2: Supabase RAG Query

```python
async def retrieve_relevant_documents(
    supabase: Client, embedding_client: AsyncOpenAI, user_query: str
) -> str:
    """Retrieve relevant chunks using semantic search."""
    response = await embedding_client.embeddings.create(
        model="text-embedding-3-small", input=user_query
    )
    query_embedding = response.data[0].embedding

    result = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_count": 4,
        "match_threshold": 0.7
    }).execute()

    if not result.data:
        return "No relevant documents found."

    return "\n".join([
        f"--- Doc {i} (sim: {d['similarity']:.2f}) ---\n{d['content']}"
        for i, d in enumerate(result.data, 1)
    ])
```

---

## Pattern 3: React Hook with API

```typescript
export function useNutritionCalculation() {
  const [result, setResult] = useState<NutritionResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculate = async (params: NutritionParams) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_URL}/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      });
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown');
    } finally {
      setIsLoading(false);
    }
  };

  return { result, isLoading, error, calculate };
}
```
