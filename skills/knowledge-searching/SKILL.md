---
name: knowledge-searching
description: "OBLIGATOIRE pour toute question factuelle sur la nutrition — proteines, macros, deficit, supplements, regimes, BMR. Charge ce skill ET appelle retrieve_relevant_documents AVANT de repondre. Ne jamais repondre de memoire sur des sujets nutritionnels."
---

# Knowledge Searching - Recherche Documentaire

## Quand utiliser

- L'utilisateur pose une question sur la nutrition, les macronutriments, les supplements, les regimes
- L'utilisateur demande des recommandations basees sur la science
- Tu as besoin de verifier une information nutritionnelle

## Workflow OBLIGATOIRE

1. **TOUJOURS appeler `retrieve_relevant_documents` EN PREMIER** avec la question de l'utilisateur
2. Si les documents ne repondent pas a la question, utilise `web_search`
3. Base ta reponse sur les documents recuperes et cite les sources (ISSN, AND, EFSA, WHO)
4. Explique le raisonnement scientifique en referencant les etudes
5. Ne te fie JAMAIS uniquement a tes connaissances internes - verifie toujours avec le RAG

## Decision RAG vs Web Search

| Situation | Outil | Raison |
|-----------|-------|--------|
| Question sur proteines, macros, BMR | `retrieve_relevant_documents` | Base de connaissances validee |
| Question sur supplement specifique | `retrieve_relevant_documents` d'abord, puis `web_search` | Completer si necessaire |
| Actualite nutritionnelle recente | `web_search` | Informations post-2024 |
| Question medicale specifique | Aucun - recommande un medecin | Hors competence |

## Exécution

```python
# RAG — base de connaissances nutritionnelles
run_skill_script("knowledge-searching", "retrieve_relevant_documents", {
    "user_query": "protein requirements muscle gain"
})

# Web search — informations récentes
run_skill_script("knowledge-searching", "web_search", {
    "query": "omega-3 recommendations 2025 ISSN guidelines"
})
```

**Scripts disponibles** :
- `scripts/retrieve_relevant_documents.py` : Embedding query → pgvector similarity search → top 4
- `scripts/web_search.py` : Brave API / SearXNG → parse results → top 5 formatted
