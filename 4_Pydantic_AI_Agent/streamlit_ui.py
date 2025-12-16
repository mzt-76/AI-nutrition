"""
Streamlit UI for AI Nutrition Assistant.

A simple chat interface for testing the agent during MVP development.
"""

import streamlit as st
import asyncio
from agent import agent, create_agent_deps
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

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_deps" not in st.session_state:
    logger.info("Initializing agent dependencies...")
    st.session_state.agent_deps = create_agent_deps()
    logger.info("Agent dependencies initialized")

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
                # Run agent asynchronously
                async def get_response():
                    result = await agent.run(
                        prompt,
                        deps=st.session_state.agent_deps
                    )
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
    st.markdown("**Version:** MVP 0.1")
    st.markdown("**Stack:** Pydantic AI + Supabase + OpenAI")
