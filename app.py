import streamlit as st
import time

from embodiment.soul import CharacterSoul
from embodiment.memory_viewer import MemoryViewer
from embodiment.dashboard_utils import SystemMonitor
from core.graph import KnowledgeGraph

# ======================================================
# UI Configuration
# ======================================================
st.set_page_config(
    page_title="The Infinite Library",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stChatMessage {border-radius: 10px; padding: 10px;}
    .stChatMessage[data-testid="stChatMessageUser"] {background-color: #f0f2f6;}
    .stChatMessage[data-testid="stChatMessageAvatarUser"] {display: none;}
    .metric-card {background-color: #f9f9f9; padding: 10px; border-radius: 5px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ======================================================
# Helpers
# ======================================================
def get_available_characters():
    kg = KnowledgeGraph()
    query = "MATCH (c:Character) RETURN c.name AS name ORDER BY c.name"
    with kg.driver.session() as session:
        result = session.run(query)
        return [record["name"] for record in result]

# ======================================================
# Sidebar
# ======================================================
with st.sidebar:
    st.title("📚 Infinite Library")
    st.caption(f"v1.1 • {st.session_state.get('soul_name', 'System Ready')}")
    st.markdown("---")

    try:
        chars = get_available_characters()
        selected_char = st.selectbox("Summon Character", chars) if chars else None
    except Exception as e:
        st.error(f"Database Error: {e}")
        selected_char = None

    st.markdown("---")
    st.subheader("🖥️ System Cortex")

    try:
        monitor = SystemMonitor()
        health = monitor.get_system_health()
        col1, col2 = st.columns(2)
        col1.metric("Ingestion", f"Ch {health.get('ingestion_status', '?')}")
        col2.metric("Drift", "0.0")
        st.metric(
            "Memory Load",
            f"{health.get('memory_raw', 0)} Nodes",
            delta=f"{health.get('memory_summary', 0)} Summaries"
        )
    except Exception:
        st.caption("Monitor offline")

    st.markdown("---")
    st.caption("Status: 🟢 Online")

# ======================================================
# Main UI
# ======================================================
st.header("Project: Infinite Library")

if selected_char:
    tab1, tab2 = st.tabs(["👻 The Soul (Chat)", "🧠 The Brain (Graph)"])

    # ------------------ CHAT ------------------
    with tab1:
        col_header, col_btn = st.columns([4, 1])
        col_header.subheader(f"Speaking with: {selected_char}")

        if col_btn.button("🧹 Reset Memory"):
            st.session_state.messages = []
            st.rerun()

        if "messages" not in st.session_state:
            st.session_state.messages = []

        if "soul" not in st.session_state or st.session_state.soul_name != selected_char:
            with st.spinner(f"Summoning {selected_char}..."):
                st.session_state.soul = CharacterSoul(selected_char)
                st.session_state.soul_name = selected_char
                st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Speak to the character..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()

                with st.status("Accessing Infinite Memory...", expanded=False):
                    memories, facts, history, summaries = st.session_state.soul.deep_recall(prompt)

                    st.write("**Logical Context (Graph):**")
                    for f in facts:
                        st.code(f)

                    st.write("**Long-Term Summaries (Archives):**")
                    for s in summaries:
                        st.info(f"📜 {s['content']} (Compressed {s['compressed_count']} turns)")

                    st.write("**Sensory Context (Vector):**")
                    for m in memories:
                        st.caption(m)

                full_response = st.session_state.soul.speak(prompt,
                 memories=memories,
                 facts=facts,
                 chat_history=history,
                 summaries=summaries
                                    )

                displayed = ""
                for word in full_response.split():
                    displayed += word + " "
                    time.sleep(0.05)
                    message_placeholder.markdown(displayed + "▌")

                message_placeholder.markdown(displayed)

            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

    # ------------------ GRAPH ------------------
    with tab2:
        st.subheader(f"Neural Network: {selected_char}")
        viewer = MemoryViewer()
        mode = st.radio(
            "Visualization Mode:",
            ["🕸️ Network Graph", "📈 Character Evolution"],
            horizontal=True
        )

        try:
            if mode == "🕸️ Network Graph":
                viewer.render_ego_graph(selected_char)
            else:
                viewer.render_character_evolution(selected_char)
        except Exception as e:
            st.error(f"Visualization Error: {e}")

else:
    st.info("👈 Please select a character from the sidebar.")
