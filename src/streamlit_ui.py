"""
Streamlit UI for AI Nutrition Assistant.

A clean chat interface for testing the agent during MVP development.
"""

import streamlit as st
import asyncio
from src.agent import agent, create_agent_deps
from src.clients import get_memory_client
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="AI Nutrition Assistant",
    page_icon="🥗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS for cleaner look
st.markdown(
    """
    <style>
    .stChatMessage {
        padding: 1rem;
    }
    .upload-section {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
st.title("🥗 AI Nutrition Assistant")
st.caption("Ton coach nutrition personnalisé, basé sur la science")


@st.cache_resource
def initialize_mem0():
    """Initialize and cache mem0 client for memory management."""
    logger.info("Initializing mem0 memory client...")
    return get_memory_client()


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "streamlit_user"

# Body composition image upload (collapsible)
with st.expander("📸 Analyse de composition corporelle", expanded=False):
    uploaded_image = st.file_uploader(
        "Dépose ta photo ici",
        type=["png", "jpg", "jpeg"],
        help="Photo de profil (torse visible) pour estimation du taux de masse grasse",
        label_visibility="collapsed",
    )

    if uploaded_image is not None:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.image(uploaded_image, caption="Photo uploadée", width=300)
        with col2:
            st.info("Photo prête pour analyse")

            if st.button("🔍 Analyser", type="primary", use_container_width=True):
                # Add user message about image analysis
                analysis_prompt = "Analyse ma composition corporelle à partir de cette photo. Donne-moi une estimation du taux de masse grasse et des conseils."
                st.session_state.messages.append(
                    {"role": "user", "content": analysis_prompt}
                )

                # Process image analysis
                with st.spinner("Analyse en cours..."):
                    try:
                        # Initialize mem0 client
                        memory = initialize_mem0()
                        user_id = st.session_state.user_id

                        # Convert image to base64 data URI
                        from PIL import Image
                        import io
                        import base64

                        image = Image.open(uploaded_image)
                        if image.mode in ("RGBA", "LA", "P"):
                            image = image.convert("RGB")

                        buffered = io.BytesIO()
                        image.save(buffered, format="JPEG")
                        img_bytes = buffered.getvalue()
                        img_base64 = base64.b64encode(img_bytes).decode()
                        image_data_uri = f"data:image/jpeg;base64,{img_base64}"

                        # Import the image analysis tool from skill script
                        from src.agent import _import_skill_script
                        from src.clients import get_openai_client
                        from pathlib import Path

                        prompt_path = (
                            Path(__file__).parent
                            / "prompts"
                            / "body_composition_analysis.txt"
                        )

                        if prompt_path.exists():
                            with open(prompt_path, "r", encoding="utf-8") as f:
                                analysis_query = f.read()
                        else:
                            analysis_query = """Analyse cette photo pour estimer la composition corporelle.

Instructions:
- Estime le taux de masse grasse (donne une fourchette, ex: 15-18%)
- Explique les indicateurs visuels que tu utilises
- Donne des conseils constructifs et encourageants
- Rappelle les limites de l'estimation visuelle

Sois professionnel, bienveillant et scientifique. Réponds en français."""

                        async def get_response():
                            openai_client = get_openai_client()
                            module = _import_skill_script(
                                "body-analyzing", "image_analysis"
                            )
                            result = await module.execute(
                                image_url=image_data_uri,
                                analysis_prompt=analysis_query,
                                openai_client=openai_client,
                            )
                            return result

                        response = asyncio.run(get_response())

                        st.session_state.messages.append(
                            {"role": "assistant", "content": response}
                        )

                        # Save to memory
                        memory_messages = [
                            {
                                "role": "user",
                                "content": "Photo de composition corporelle analysée",
                            }
                        ]
                        memory.add(memory_messages, user_id=user_id)

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erreur: {str(e)}")
                        logger.error(f"Image analysis error: {e}", exc_info=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Pose ta question nutritionnelle..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Detect if this is a meal plan generation request
    meal_plan_keywords = [
        "plan de repas",
        "plan repas",
        "meal plan",
        "plan pour la semaine",
        "plan hebdomadaire",
        "génère un plan",
        "genere un plan",
        "crée un plan",
        "cree un plan",
        "créer un plan",
        "planifie mes repas",
        "planifier mes repas",
    ]
    is_meal_plan_request = any(
        keyword in prompt.lower() for keyword in meal_plan_keywords
    )

    with st.chat_message("assistant"):
        # Show appropriate spinner message
        if is_meal_plan_request:
            st.info(
                "⏳ **Génération du plan de repas en cours...**\n\n"
                "Cette opération prend généralement **3-4 minutes** car je dois :\n"
                "- Charger ton profil et tes préférences\n"
                "- Générer 7 jours de recettes personnalisées\n"
                "- Valider les macros avec la base OpenFoodFacts\n"
                "- Optimiser les portions pour atteindre tes objectifs\n\n"
                "Merci de patienter !"
            )
            spinner_message = "Génération en cours (3-4 min)..."
        else:
            spinner_message = "Je réfléchis..."

        with st.spinner(spinner_message):
            try:
                memory = initialize_mem0()
                user_id = st.session_state.user_id

                # Load relevant memories
                relevant_memories = memory.search(
                    query=prompt, user_id=user_id, limit=3
                )

                memories_str = ""
                if relevant_memories and relevant_memories.get("results"):
                    memories_str = "\n".join(
                        f"- {entry['memory']}" for entry in relevant_memories["results"]
                    )

                agent_deps = create_agent_deps(
                    memories=memories_str, user_id=st.session_state.user_id
                )

                async def get_response():
                    result = await agent.run(prompt, deps=agent_deps)
                    return result.data

                response = asyncio.run(get_response())

                st.markdown(response)

                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )

                # Save to memory
                memory_messages = [{"role": "user", "content": prompt}]
                memory.add(memory_messages, user_id=user_id)

            except Exception as e:
                error_msg = f"Erreur: {str(e)}"
                st.error(error_msg)
                logger.error(f"Agent error: {e}", exc_info=True)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )

# Sidebar
with st.sidebar:
    st.markdown("### Exemples de questions")
    st.markdown(
        """
    - "Calcule mes besoins: 35 ans, homme, 87kg, 178cm"
    - "Combien de protéines pour prendre du muscle?"
    - "Génère un plan de repas pour la semaine"
    - "Liste de courses pour cette semaine"
    """
    )

    st.divider()

    if st.button("🗑️ Effacer l'historique", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # Memory viewer
    with st.expander("🧠 Mémoire"):
        if st.button("Voir mes mémoires", use_container_width=True):
            try:
                memory = initialize_mem0()
                all_memories = memory.get_all(user_id=st.session_state.user_id)
                if all_memories and all_memories.get("results"):
                    for i, mem in enumerate(all_memories["results"][:5], 1):
                        st.caption(f"{i}. {mem.get('memory', 'N/A')}")
                else:
                    st.info("Aucune mémoire.")
            except Exception as e:
                st.error(f"Erreur: {e}")

    st.divider()
    st.caption("MVP 0.1 • Pydantic AI + Supabase")
