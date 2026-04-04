# Workaround for ChromaDB SQLite version on Hugging Face Spaces
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import os
from retriever import FAQRetriever


# ── Page Configuration ──────────────────────────────────────
st.set_page_config(
    page_title="Pharma FAQ Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .main .block-container {
        max-width: 900px;
        padding-top: 2rem;
    }

    h1 {
        background: linear-gradient(135deg, #1a3c6e 0%, #2980b9 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2rem !important;
    }

    /* Chat message styling */
    .stChatMessage {
        border-radius: 12px !important;
        margin-bottom: 0.5rem !important;
    }

    /* Source citation box */
    .source-box {
        background: linear-gradient(135deg, #f0f4f8 0%, #e8eef5 100%);
        border-left: 4px solid #1a3c6e;
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        margin-top: 8px;
        font-size: 0.85em;
        color: #2c3e50 !important;
    }

    /* Confidence badges */
    .badge-high {
        display: inline-block;
        background: #27ae60;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
    }
    .badge-medium {
        display: inline-block;
        background: #f39c12;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
    }
    .badge-low {
        display: inline-block;
        background: #e74c3c;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
    }

    /* Clarify box */
    .clarify-box {
        background: #fef9e7;
        border-left: 4px solid #f39c12;
        border-radius: 0 8px 8px 0;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-size: 0.9em;
        color: #2c3e50 !important;
    }

    /* Table styling */
    .faq-table {
        margin: 16px 0;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    .faq-table table {
        border-collapse: collapse;
        width: 100%;
        font-size: 0.88em;
        border: none;
    }
    .faq-table th {
        background: linear-gradient(135deg, #1a3c6e 0%, #2c5f8a 100%);
        color: white;
        padding: 12px 16px;
        text-align: left;
        font-weight: 600;
        font-size: 0.9em;
        letter-spacing: 0.3px;
        border: none;
    }
    .faq-table td {
        padding: 10px 16px;
        border-bottom: 1px solid #e8eef5;
        color: #2c3e50;
        border-left: none;
        border-right: none;
    }
    .faq-table tr:nth-child(even) {
        background: #f5f8fc;
    }
    .faq-table tr:nth-child(odd) {
        background: #ffffff;
    }
    .faq-table tr:hover td {
        background: #eaf2fa;
    }
    .faq-table tr:last-child td {
        border-bottom: none;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a3c6e 0%, #0d2137 100%);
    }
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    section[data-testid="stSidebar"] .stMarkdown a {
        color: #7ec8e3 !important;
    }

    /* No match box */
    .no-match-box {
        background: #fdf2f2;
        border-left: 4px solid #e74c3c;
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        font-size: 0.9em;
        color: #2c3e50 !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Initialize ──────────────────────────────────────────────
@st.cache_resource
def load_retriever():
    """Load the Retriever subsystem, auto-ingesting DOCX if stores are completely empty."""
    from vector_store import FAQVectorStore
    from database import FAQDatabase
    from ingest import run_ingestion

    store = FAQVectorStore()
    db = FAQDatabase()

    # Auto-ingest if the stores are empty (first run / HF Spaces deploy)
    if store.collection.count() == 0 or db.count() == 0:
        docs_dir = os.path.join(os.path.dirname(__file__), "new_docs")
        if os.path.isdir(docs_dir):
            run_ingestion([docs_dir])
        
        # Reload instances after ingestion
        store = FAQVectorStore()
        db = FAQDatabase()

    from retriever import FAQRetriever
    print("🚀 Initializing FAQ Retriever...")
    r = FAQRetriever(store=store, db=db)
    print("✅ FAQ Retriever ready.")
    return r


print("👾 Streamlit Server Heartbeat: app.py loaded.")
retriever = load_retriever()

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# --- SIDEBAR: Settings ---
with st.sidebar:
    st.markdown("### 🔍 Search Settings")
    
    # Ingestion Stats
    stats = None
    try:
        stats = retriever.get_stats()
        st.info(f"**📚 Knowledge Base Status**\n\n📄 Documents: `{stats['source_documents']}`\n\n❓ FAQ Pairs: `{stats['total_qa_pairs']}`")
    except Exception:
        st.warning("⚠️ Knowledge base not indexed or out of sync.")
        if st.button("🔄 Refresh Status"):
            st.cache_resource.clear()
            st.rerun()
            
    st.divider()
    st.markdown("## 🏥 Pharma FAQ")
    st.markdown("**Medical Information Assistant**")
    st.markdown("---")

    st.markdown("### ℹ️ About")
    st.markdown(
        "This assistant answers questions from approved FAQ documents. "
        "All answers are **verbatim** from the source — no AI-generated content."
    )

    if stats:
        st.markdown("---")
        st.markdown("### 📚 Indexed Documents")
        st.markdown(f"**{stats['total_qa_pairs']}** Q-A pairs from **{stats['source_documents']}** documents")
        for doc in stats["source_doc_names"]:
            st.markdown(f"- {doc.replace('.pdf', '').replace('.docx', '')}")
    
    st.markdown("---")
    st.markdown("### 🔧 Settings")
    top_k = st.slider("Results to consider", 1, 5, 3)
    search_mode = st.radio("Search Mode", ["Semantic", "Hybrid", "Advanced"], horizontal=True).lower()
    selected_channel = st.selectbox("Preferred Channel", ["Voicebot", "WhatsApp", "Webchat", "Email"])
    show_debug = st.checkbox("Show debug info", value=False)

    st.markdown("---")
    st.markdown("### 💡 Sample Questions")
    sample_qs = [
        "What is the starting dose for hypertension?",
        "Side effects of the diabetes injection?",
        "Can the inhaler be used in children?",
        "How to manage immune-related pneumonitis?",
        "Is the anxiety medication safe with alcohol?",
    ]
    for sq in sample_qs:
        st.markdown(f"*\"{sq}\"*")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ── Main Chat Area ──────────────────────────────────────────
st.markdown("# 🏥 Pharma FAQ Assistant")
st.markdown(
    "*Ask questions about our pharmaceutical products. "
    "Answers are extracted verbatim from approved FAQ documents.*"
)

# Helper function to render a result
def render_result(result, selected_channel):
    response_html = ""
    if result["status"] == "answered":
        sim = result["similarity"]
        response_html += f'<span class="badge-high">✓ High Confidence ({sim:.0%})</span><br><br>'

        # Channel Specific Response Extraction
        answer_text = result["answer"]
        channels = result.get("channels", {})
        
        # Always strip raw table text from the fallback master block
        if result.get("table_text"):
            for line in result["table_text"].split("\\n"):
                line = line.strip()
                if line and line in answer_text:
                    answer_text = answer_text.replace(line, "").strip()
            answer_text = ' '.join(answer_text.split())

        chan_key = selected_channel.lower()
        if chan_key in channels and channels[chan_key].strip():
            answer_text = channels[chan_key]
        else:
            answer_text = f"*(Warning: No {selected_channel} specific response provided in the document. Showing full block)*<br><br>{answer_text}"
            
        response_html += f'<div style="white-space: pre-wrap;">{answer_text}</div><br><br>'

        if result.get("table_html"):
            response_html += f'<div class="faq-table">{result["table_html"]}</div><br><br>'

        # Clean matched question for display
        clean_question = result["matched_question"].split(" | Question: ")[-1]
        response_html += (
            f'<div class="source-box">'
            f'📄 <b>Source:</b> {result["source_doc"]} · Page {result["page_num"]} · '
            f'Section: {result["section"]} · '
            f'⏱️ <b>Response Time:</b> {result.get("latency", 0)}s<br>'
            f'🔎 <b>Matched FAQ:</b> <i>"{clean_question}"</i>'
            f'</div>'
        )

    elif result["status"] == "clarify":
        sim = result["similarity"]
        response_html += f'<span class="badge-medium">⚠ Medium Confidence ({sim:.0%})</span><br><br>'

        answer_text = result["answer"]
        channels = result.get("channels", {})
        
        # Always strip raw table text from the fallback master block
        if result.get("table_text"):
            for line in result["table_text"].split("\\n"):
                line = line.strip()
                if line and line in answer_text:
                    answer_text = answer_text.replace(line, "").strip()
            answer_text = ' '.join(answer_text.split())
        
        chan_key = selected_channel.lower()
        if chan_key in channels and channels[chan_key].strip():
            answer_text = channels[chan_key]
        else:
            answer_text = f"*(Warning: No {selected_channel} specific response provided in the document. Showing full block)*<br><br>{answer_text}"

        response_html += f'<div style="white-space: pre-wrap;"><b>{answer_text}</b></div><br><br>'
        
        if result.get("table_html"):
            response_html += f'<div class="faq-table">{result["table_html"]}</div><br><br>'

        response_html += (
            f'<div class="source-box">'
            f'📄 <b>Source:</b> {result["source_doc"]} · Page {result["page_num"]} · '
            f'⏱️ <b>Response Time:</b> {result.get("latency", 0)}s'
            f'</div><br><br>'
        )
        response_html += "**Other possible matches:**<br>"
        for alt in result["alternatives"]:
            clean_alt_q = alt['question'].split(" | Question: ")[-1]
            response_html += f"- {clean_alt_q} ({alt['similarity']:.0%})<br>"
            
    else:
        response_html += f'<div class="no-match-box">❌ {result["message"]}</div>'
        
    return response_html

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"], unsafe_allow_html=True)
        else:
            # Re-render dynamically to respect the latest channels dropdown
            st.markdown(render_result(message["result"], selected_channel), unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Ask a question about our pharmaceutical products..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get answer
    with st.chat_message("assistant"):
        import time
        start_time = time.time()
        
        with st.spinner(f"Searching ({search_mode})..."):
            result = retriever.get_best_answer(prompt, search_mode=search_mode)
            
        latency = round(time.time() - start_time, 2)
        result["latency"] = latency
            
        # Dynamically render response using the current dropdown setting 
        response_html = render_result(result, selected_channel)
        st.markdown(response_html, unsafe_allow_html=True)

        # Debug info
        if show_debug:
            with st.expander("🔧 Debug Info"):
                st.json(result)

    # Save assistant message with RAW data payload instead of static HTML
    st.session_state.messages.append({"role": "assistant", "result": result})
