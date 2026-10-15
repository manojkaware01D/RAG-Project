import hashlib
import json
from pathlib import Path

import streamlit as st

from rag import SEED_DOCUMENTS, import_public_repository, retrieve_passages


APP_DIR = Path(__file__).resolve().parent
DATA_PATH = APP_DIR / ".app_data" / "documents.json"

st.set_page_config(page_title="Ledgerline | Banking RAG", page_icon="🏦", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root { --forest: #176b52; --paper: #f5f6f2; --line: #e3e8e1; }
    .stApp { background: var(--paper); color: #182320; font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'Manrope', sans-serif !important; letter-spacing: 0 !important; }
    [data-testid="stSidebar"] { background: #fbfcf9; border-right: 1px solid var(--line); }
    [data-testid="stSidebar"] h1 { color: var(--forest); font-size: 1.4rem; }
    .eyebrow { color: #738078; font-size: .68rem; font-weight: 700; letter-spacing: 1.2px; }
    .stButton > button[kind="primary"] { background: var(--forest); border-color: var(--forest); }
    .stButton > button { border-radius: 5px; }
    [data-testid="stMetric"] { background: #fff; border: 1px solid var(--line); padding: 12px; border-radius: 6px; }
    [data-testid="stExpander"] { border-color: var(--line); background: rgba(255,255,255,.55); }
    .source-note { color: #718078; font-size: .8rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_documents() -> list[dict[str, str]]:
    if DATA_PATH.exists():
        try:
            saved = json.loads(DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, list) and all(isinstance(item, dict) for item in saved):
                return saved
        except (OSError, json.JSONDecodeError):
            pass
    return [dict(document) for document in SEED_DOCUMENTS]


def save_documents(documents: list[dict[str, str]]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = DATA_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(DATA_PATH)


def add_document(title: str, content: str, category: str, **metadata: str) -> bool:
    normalized = content.strip()
    if not normalized:
        return False
    digest = hashlib.sha256(f"{title}\0{normalized}".encode("utf-8")).hexdigest()
    if any(document.get("id") == digest for document in st.session_state.documents):
        return False
    st.session_state.documents.append(
        {
            "id": digest,
            "title": title,
            "category": category,
            "content": normalized,
            "updated": "Added in this workspace",
            **metadata,
        }
    )
    return True


def run_query(question: str) -> None:
    question = question.strip()
    if not question:
        return
    st.session_state.last_question = question
    st.session_state.last_results = retrieve_passages(question, st.session_state.documents)
    st.session_state.activity.insert(0, question)
    st.session_state.activity = st.session_state.activity[:30]


def set_suggestion(question: str) -> None:
    st.session_state.question_input = question
    st.session_state.run_suggestion = True


if "documents" not in st.session_state:
    st.session_state.documents = load_documents()
if "activity" not in st.session_state:
    st.session_state.activity = []
if "last_question" not in st.session_state:
    st.session_state.last_question = ""
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "run_suggestion" not in st.session_state:
    st.session_state.run_suggestion = False

st.sidebar.markdown("# ledgerline")
st.sidebar.caption("NORTHSTAR BANK · RETAIL SUPPORT")
view = st.sidebar.radio("Workspace", ["Ask assistant", "Knowledge library", "Recent activity"], label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.markdown("**Private workspace**")
st.sidebar.caption("Documents are stored locally")


if view == "Ask assistant":
    left, right = st.columns([2.2, 1], gap="large")
    with left:
        st.markdown('<p class="eyebrow">SUPPORT KNOWLEDGE</p>', unsafe_allow_html=True)
        st.title("Banking knowledge desk")
        st.caption("Northstar Bank · Retail support")
        st.text_area(
            "Ask a banking question",
            key="question_input",
            height=92,
            placeholder="Ask about accounts, cards, fees, and more…",
        )
        if st.button("Find an answer", type="primary"):
            run_query(st.session_state.question_input)

        st.markdown("<p class='eyebrow'>TRY ASKING</p>", unsafe_allow_html=True)
        prompts = [
            "How can a monthly fee be waived?",
            "What should I do about a lost debit card?",
            "When is a wire transfer fee charged?",
        ]
        prompt_columns = st.columns(len(prompts))
        for column, prompt in zip(prompt_columns, prompts):
            column.button(prompt, key=f"prompt-{prompt}", on_click=set_suggestion, args=(prompt,))
        if st.session_state.run_suggestion:
            st.session_state.run_suggestion = False
            run_query(st.session_state.question_input)

        if st.session_state.last_question:
            st.divider()
            st.caption(f"Answer to: {st.session_state.last_question}")
            if st.session_state.last_results:
                st.markdown("**Extractive answer · grounded in source text**")
                st.text(st.session_state.last_results[0]["text"])
                for index, result in enumerate(st.session_state.last_results, start=1):
                    document = result["document"]
                    with st.expander(f"[{index}] {document['title']}"):
                        st.text(result["text"])
                        st.caption(f"{document['category']} · {document['updated']}")
            else:
                st.info("No close match in the current library.")

    with right:
        st.markdown('<p class="eyebrow">YOUR KNOWLEDGE</p>', unsafe_allow_html=True)
        st.subheader("Source library")
        st.metric("Documents indexed", len(st.session_state.documents))
        for document in st.session_state.documents[:6]:
            st.markdown(f"**{document['title']}**")
            st.caption(document["category"])
        if len(st.session_state.documents) > 6:
            st.caption(f"+ {len(st.session_state.documents) - 6} more documents")
        st.divider()
        st.caption("Local retrieval · no external AI calls")

elif view == "Knowledge library":
    st.markdown('<p class="eyebrow">KNOWLEDGE MANAGEMENT</p>', unsafe_allow_html=True)
    st.title("Knowledge library")
    st.caption(f"{len(st.session_state.documents)} indexed sources")

    st.subheader("Add documents")
    uploaded_files = st.file_uploader("Documents", type=["txt", "md", "csv"], accept_multiple_files=True, label_visibility="collapsed")
    if st.button("Index selected files", disabled=not uploaded_files):
        added = 0
        for uploaded_file in uploaded_files:
            text = uploaded_file.getvalue().decode("utf-8", errors="replace")
            added += add_document(uploaded_file.name, text, "Uploaded")
        if added:
            save_documents(st.session_state.documents)
        st.success(f"Added {added} document(s).")

    st.subheader("Add a GitHub repository")
    with st.form("github_repository_form"):
        repository_url = st.text_input("Public repository URL", placeholder="https://github.com/owner/repository")
        import_repository = st.form_submit_button("Import repository", type="primary")
    if import_repository:
        with st.spinner("Reading repository documentation…"):
            try:
                imported_documents = import_public_repository(repository_url)
                existing_repositories = {
                    document.get("source_repo", "").lower() for document in st.session_state.documents
                }
                if imported_documents and imported_documents[0]["source_repo"].lower() in existing_repositories:
                    st.warning("This repository is already in the library.")
                else:
                    for document in imported_documents:
                        add_document(
                            document["title"],
                            document["content"],
                            "GitHub",
                            source_repo=document["source_repo"],
                            source_path=document["source_path"],
                        )
                    save_documents(st.session_state.documents)
                    st.success(f"Added {len(imported_documents)} file(s) from {imported_documents[0]['source_repo']}.")
            except (ValueError, RuntimeError) as error:
                st.error(str(error))

    st.divider()
    for document in list(st.session_state.documents):
        details, remove = st.columns([8, 1])
        with details:
            st.markdown(f"**{document['title']}**")
            source_path = document.get("source_path")
            source_label = f"GitHub · {source_path}" if source_path else document["category"]
            st.caption(f"{source_label} · {document['updated']}")
        with remove:
            if st.button("Remove", key=f"remove-{document['id']}"):
                st.session_state.documents = [
                    item for item in st.session_state.documents if item["id"] != document["id"]
                ]
                save_documents(st.session_state.documents)
                st.rerun()

elif view == "Recent activity":
    st.markdown('<p class="eyebrow">YOUR WORKSPACE</p>', unsafe_allow_html=True)
    st.title("Recent activity")
    if st.button("Clear activity"):
        st.session_state.activity = []
    if st.session_state.activity:
        for question in st.session_state.activity:
            st.write(question)
    else:
        st.caption("No questions asked yet.")