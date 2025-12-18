"""
Streamlit UI for AI Nutrition Assistant.

A simple chat interface for testing the agent during MVP development.
"""

import streamlit as st
import asyncio
from agent import agent, create_agent_deps
from clients import get_memory_client
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="AI Nutrition Assistant",
    page_icon="🥗",
    layout="wide"
)

# Title
st.title("🥗 AI Nutrition Assistant")
st.markdown("*Your personalized nutrition coach powered by science*")


@st.cache_resource
def initialize_mem0():
    """Initialize and cache mem0 client for memory management."""
    logger.info("Initializing mem0 memory client...")
    return get_memory_client()


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "streamlit_user"  # Could be dynamic based on auth later

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Pose ta question nutritionnelle..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("💭 Je réfléchis..."):
            try:
                # Initialize mem0 client
                memory = initialize_mem0()
                user_id = st.session_state.user_id

                # Load relevant memories for context
                logger.info(f"Loading memories for user: {user_id}")
                relevant_memories = memory.search(
                    query=prompt,
                    user_id=user_id,
                    limit=3
                )

                # Format memories as string
                memories_str = ""
                if relevant_memories and relevant_memories.get("results"):
                    memories_str = "\n".join(
                        f"- {entry['memory']}"
                        for entry in relevant_memories["results"]
                    )
                    logger.info(f"Loaded {len(relevant_memories['results'])} memories")

                # Create agent deps with memories
                agent_deps = create_agent_deps(memories=memories_str)

                # Run agent asynchronously
                async def get_response():
                    result = await agent.run(prompt, deps=agent_deps)
                    return result.data

                # Execute async function
                response = asyncio.run(get_response())

                # Display response
                st.markdown(response)

                # Add to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })

                # Save new memories (user message only, not assistant response)
                logger.info("Saving new memories...")
                memory_messages = [
                    {"role": "user", "content": prompt}
                ]
                memory.add(memory_messages, user_id=user_id)
                logger.info("Memories saved successfully")

            except Exception as e:
                error_msg = f"❌ Erreur: {str(e)}"
                st.error(error_msg)
                logger.error(f"Agent error: {e}", exc_info=True)

                # Add error to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })

# Sidebar with information
with st.sidebar:
    st.markdown("### 📋 Commandes Rapides")

    st.markdown("""
    **Exemples de questions:**

    - "Calcule mes besoins nutritionnels: 35 ans, homme, 87kg, 178cm"
    - "Combien de protéines pour prendre du muscle?"
    - "Quelles sont les recommandations sur le timing des glucides?"
    - "Charge mon profil"

    **Fonctionnalités:**
    - ✅ Calculs nutritionnels (BMR, TDEE, macros)
    - ✅ Base de connaissances scientifique (RAG)
    - ✅ Recherche web (Brave API)
    - ✅ Profil utilisateur (Supabase)
    - 🔄 Ajustements hebdomadaires (à venir)
    - 🔄 Analyse de composition corporelle (à venir)
    """)

    st.markdown("---")

    if st.button("🗑️ Effacer l'historique"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")

    # Memory viewer
    st.markdown("### 🧠 Mémoire Long-Terme")
    if st.button("👁️ Voir mes mémoires"):
        try:
            memory = initialize_mem0()
            all_memories = memory.get_all(user_id=st.session_state.user_id)
            if all_memories and all_memories.get("results"):
                st.markdown("**Mémoires sauvegardées:**")
                for i, mem in enumerate(all_memories["results"][:5], 1):
                    st.text(f"{i}. {mem.get('memory', 'N/A')}")
            else:
                st.info("Aucune mémoire sauvegardée pour le moment.")
        except Exception as e:
            st.error(f"Erreur: {e}")

    st.markdown("---")
    st.markdown("**Version:** MVP 0.1")
    st.markdown("**Stack:** Pydantic AI + Supabase + OpenAI + mem0")
