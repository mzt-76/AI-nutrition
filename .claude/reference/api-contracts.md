# API Contracts

**Purpose:** Type matching and error handling patterns between Python backend and TypeScript frontend.

---

## Type Matching (Python TypedDict ↔ TypeScript interface)

**Backend:**
```python
class NutritionResult(TypedDict):
    bmr: int
    tdee: int
    target_calories: int
    target_protein_g: int
```

**Frontend:**
```typescript
interface NutritionResult {
  bmr: number;
  tdee: number;
  target_calories: number;
  target_protein_g: number;
}
```

---

## Error Handling

**Backend:**
- Success: `{"output": "..."}`
- Error: `{"error": "...", "code": "VALIDATION_ERROR"}`

**Frontend:**
- Check `data.error` first
- Fallback to `data.output || data.response`
