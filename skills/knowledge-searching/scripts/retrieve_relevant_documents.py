"""Retrieve relevant document chunks from knowledge base using semantic search (RAG).

Utility script — can be imported by agent tool wrapper or run standalone.
Uses text-embedding-3-small for semantic matching with cross-language support.

Source: Extracted from src/tools.py retrieve_relevant_documents_tool
"""

import logging

logger = logging.getLogger(__name__)


async def execute(**kwargs) -> str:
    """Retrieve relevant documents via RAG semantic search.

    Args:
        supabase: Supabase client for pgvector database access.
        embedding_client: AsyncOpenAI client for text-embedding-3-small.
        user_query: Natural language question or topic (French or English).

    Returns:
        Formatted string with up to 4 most relevant document chunks.
    """
    supabase = kwargs["supabase"]
    embedding_client = kwargs["embedding_client"]
    user_query = kwargs["user_query"]

    try:
        logger.info(f"RAG query: {user_query[:50]}...")

        # Generate embedding for query
        response = await embedding_client.embeddings.create(
            model="text-embedding-3-small", input=user_query
        )
        query_embedding = response.data[0].embedding

        # Query Supabase vectorstore
        result = supabase.rpc(
            "match_documents",
            {
                "query_embedding": query_embedding,
                "match_count": 10,
                "filter": {},
            },
        ).execute()

        if not result.data:
            logger.warning("No relevant documents found")
            return "No relevant documents found in knowledge base."

        # Filter by similarity threshold (0.5 for cross-language queries) and take top 4
        MIN_SIMILARITY = 0.5
        relevant_docs = [
            doc for doc in result.data if doc.get("similarity", 0) >= MIN_SIMILARITY
        ][:4]

        if not relevant_docs:
            logger.warning(f"No documents above similarity threshold {MIN_SIMILARITY}")
            return f"No sufficiently relevant documents found (threshold: {MIN_SIMILARITY})."

        # Format results
        formatted_docs = []
        for i, doc in enumerate(relevant_docs, 1):
            similarity = doc.get("similarity", 0)
            content = doc.get("content", "")
            formatted_docs.append(
                f"--- Document {i} (similarity: {similarity:.2f}) ---\n{content}"
            )

        logger.info(f"Retrieved {len(formatted_docs)} relevant documents")

        return "\n\n".join(formatted_docs)

    except Exception as e:
        logger.error(f"Error in RAG retrieval: {e}", exc_info=True)
        return f"Error retrieving documents: {str(e)}"
