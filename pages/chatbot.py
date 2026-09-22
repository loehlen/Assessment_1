import streamlit as st
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
import hashlib
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

st.set_page_config(
    page_title="United Brands v Commission — Chatbot",
    page_icon="⚖️",
)

ASSISTANT_AVATAR = "⚖️"
USER_AVATAR = "🙋‍♀️"

# Paragraph range for each chunk file, keyed by filename (not position).
# This means the mapping can never silently desync if files are added,
# removed, or resplit later — only this dict needs updating.
CHUNK_PARAGRAPHS = {
    "01_framing_legal_test.txt": "§§ 10–11",
    "02_applicant_argument_interchangeability.txt": "§§ 12–13",
    "03_applicant_evidence_seasonal_data.txt": "§§ 14–18",
    "04_commission_rebuttal.txt": "§§ 19–21",
    "05_court_test_special_features.txt": "§§ 22–27",
    "06_court_cross_elasticity_data.txt": "§§ 28–30",
    "07_court_banana_characteristics.txt": "§§ 31–33",
    "08_court_conclusion.txt": "§§ 34–35",
}


# --------------------------------------------------
# Page styling (matches intro page)
# --------------------------------------------------

st.markdown(
    """
    <style>
    /* Main buttons */
    div.stButton > button {
        border: 1px solid #E8CDD4;
        border-radius: 8px;
        background-color: white;
        color: #30313D;
    }

    div.stButton > button:hover {
        border-color: #D8B3BE;
        background-color: #F5E6EA;
        color: #30313D;
    }

    /* Primary button */
    div.stButton > button[kind="primary"] {
        border: 1px solid #9B6574;
        background-color: #9B6574;
        color: white;
    }

    div.stButton > button[kind="primary"]:hover {
        border-color: #85526035;
        background-color: #85525F;
        color: white;
    }


    /* Expanders */
    div[data-testid="stExpander"] {
        border: 1px solid #E2D9DC;
        border-radius: 8px;
    }

    /* Small paragraph references */
    .paragraph-reference {
        color: #8A7C81;
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }

    /* Step progress indicator */
    .step-indicator {
        color: #9B6574;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }

    /* Hook / teaser line */
    .teaser {
        font-size: 1.02rem;
        color: #4A4A52;
        margin-bottom: 0.6rem;
    }

    /* Conclusion / court-holding box */
    .conclusion-box {
        background-color: #F5E6EA;
        border: 1px solid #E8CDD4;
        border-left: 4px solid #9B6574;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        color: #30313D;
        margin: 1rem 0;
    }

    .conclusion-box strong {
        color: #9B6574;
    }

    /* Slim progress bar in the theme color */
    div[data-testid="stProgress"] div[role="progressbar"] > div {
        background-color: #9B6574;
    }

    /* Background/case-info card */
    .case-card {
        background-color: #FAF6F7;
        border: 1px solid #E2D9DC;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin: 0.8rem 0 1.2rem 0;
    }

    .case-card .case-row {
        display: flex;
        gap: 0.5rem;
        font-size: 0.95rem;
        margin-bottom: 0.3rem;
    }

    .case-card .case-label {
        color: #9B6574;
        font-weight: 600;
        min-width: 110px;
    }

    /* Retrieved-chunk cards inside the chatbot's "sources" expander */
    .chunk-card {
        background-color: #FAF6F7;
        border: 1px solid #E2D9DC;
        border-left: 3px solid #9B6574;
        border-radius: 8px;
        padding: 0.7rem 1rem;
        margin-bottom: 0.6rem;
    }

    .chunk-card .chunk-title {
        color: #9B6574;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.2rem;
    }

    /* --------------------------------------------------
       Chat input & password field: exactly ONE pink ring,
       drawn only by the outer container. Every element
       inside is forced to have no border/shadow/outline of
       its own, in every state, so rings never stack.
       -------------------------------------------------- */

    div[data-testid="stChatInput"],
    div[data-testid="stTextInput"] > div {
        border-color: #E2D9DC !important;
        box-shadow: none !important;
    }

    div[data-testid="stChatInput"]:hover,
    div[data-testid="stChatInput"]:focus-within,
    div[data-testid="stTextInput"] > div:hover,
    div[data-testid="stTextInput"] > div:focus-within {
        border-color: #9B6574 !important;
        box-shadow: 0 0 0 1px #9B6574 !important;
    }

    div[data-testid="stChatInput"] *,
    div[data-testid="stTextInput"] * {
        border-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    div[data-testid="stChatInput"] textarea,
    div[data-testid="stTextInput"] input {
        caret-color: #9B6574 !important;
    }

    /* Chat input submit (arrow) button keeps its own solid fill,
       not the transparent-border rule above */
    div[data-testid="stChatInput"] button {
        background-color: #9B6574 !important;
        border-color: #9B6574 !important;
        color: white !important;
    }

    div[data-testid="stChatInput"] button:hover,
    div[data-testid="stChatInput"] button:focus,
    div[data-testid="stChatInput"] button:active {
        background-color: #85525F !important;
        border-color: #85525F !important;
        color: white !important;
    }

    div[data-testid="stChatInput"] button svg {
        fill: white !important;
        color: white !important;
    }

    /* Justified ("Blocksatz") body text throughout the app */
    [data-testid="stChatMessageContent"] p,
    [data-testid="stMarkdownContainer"] p,
    .case-card,
    .teaser,
    .conclusion-box {
        text-align: justify;
        text-justify: inter-word;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# --------------------------------------------------
# Password
# --------------------------------------------------

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:

    st.title("United Brands v Commission")
    st.subheader("Relevant Product Market Chatbot")

    st.markdown(
        '<div class="teaser">Enter the password to access the chatbot.</div>',
        unsafe_allow_html=True
    )

    password_input = st.text_input(
        label="Password",
        type="password",
        placeholder="Enter password"
    )

    if password_input:

        if password_input == os.environ["PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

if st.session_state.authenticated:

    os.environ["CHROMA_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

    CASE_NAME = "United Brands v Commission (Case 27/76)"

    CHUNKS_FOLDER = (
        "Chunks - United Brands v Commission - Relevant Product Market"
    )

    @st.cache_resource
    def get_collection():

        client = chromadb.PersistentClient(
            path="./my_chroma_db"
        )

        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            model_name="text-embedding-3-large",
        )

        collection = client.get_or_create_collection(
            name="united_brands_relevant_market",
            embedding_function=openai_ef,
        )

        # Ingest the prepared chunks
        folder = Path(CHUNKS_FOLDER)

        if folder.exists():

            with st.spinner("Loading case materials..."):

                files = sorted(folder.glob("*.txt"))

                documents, metadatas, ids = [], [], []

                for file in files:

                    text = file.read_text(
                        encoding="utf-8",
                        errors="ignore"
                    ).strip()

                    if text:

                        documents.append(text)

                        paragraphs = CHUNK_PARAGRAPHS.get(file.name, "")

                        if not paragraphs:
                            st.warning(
                                f"No paragraph range mapped for {file.name} "
                                "— check CHUNK_PARAGRAPHS."
                            )

                        metadatas.append({
                            "source": CASE_NAME,
                            "filename": file.name,
                            "paragraphs": paragraphs
                        })

                        ids.append(
                            hashlib.md5(
                                file.name.encode()
                            ).hexdigest()
                        )

                if documents:

                    collection.upsert(
                        documents=documents,
                        metadatas=metadatas,
                        ids=ids
                    )

        return collection


    collection = get_collection()


    # --------------------------------------------------
    # Header (matches intro page's title/subheader/case-card)
    # --------------------------------------------------

    st.title("United Brands v Commission")
    st.subheader("Relevant Product Market Chatbot")

    st.markdown(
        f"""
        <div class="case-card">
            <div class="case-row"><span class="case-label">Case</span><span>27/76, United Brands Co. v Commission (14 February 1978)</span></div>
            <div class="case-row"><span class="case-label">Covers</span><span>Chapter I, Section 1 — "The relevant market" (paragraphs 10–35)</span></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="teaser">Ask questions about how the Court determined '
        'the relevant product market. The chatbot covers paragraphs 10–35 '
        'only.</div>',
        unsafe_allow_html=True
    )

    st.divider()


    # --- Conversation history ---

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None


    if st.sidebar.button("← Back to case overview"):
        st.switch_page("home.py")

    if st.sidebar.button("Reset conversation"):
        st.session_state.messages = []
        st.rerun()


    def render_sources(sources):
        """Render the 'Retrieved chunks used for this answer' expander
        for a given list of {"paragraphs": ..., "doc": ...} sources."""

        with st.expander("Retrieved chunks used for this answer"):

            for rank, source in enumerate(sources, start=1):

                paragraphs = source.get("paragraphs") or "unspecified paragraphs"

                st.markdown(
                    f"""
                    <div class="chunk-card">
                        <div class="chunk-title">Match {rank} · Paragraphs {paragraphs}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.caption(source.get("doc", ""))


    for message in st.session_state.messages:

        avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR

        # Replay the retrieved-chunks expander for past assistant answers too
        if message["role"] == "assistant" and message.get("sources"):
            render_sources(message["sources"])

        with st.chat_message(message["role"], avatar=avatar):
            st.write(message["content"])


    # --- Search / RAG response ---

    query = st.chat_input(
        "Ask a question about the relevant product market..."
    )

    if not query and st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None

    n_results = 3

    client = OpenAI()


    if query:

        # Show user question
        st.session_state.messages.append(
            {
                "role": "user",
                "content": query
            }
        )

        with st.chat_message("user", avatar=USER_AVATAR):
            st.write(query)


        # Retrieve relevant chunks
        try:

            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )

        except Exception:

            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                st.error(
                    "Something went wrong retrieving relevant passages. "
                    "Please try asking again."
                )

            st.stop()


        # Build a plain list of sources so it can be displayed now AND
        # stored with the assistant's message for later replay
        sources = [
            {
                "paragraphs": meta.get("paragraphs"),
                "doc": doc
            }
            for doc, meta in zip(
                results["documents"][0],
                results["metadatas"][0],
            )
        ]

        # Show retrieved chunks (styled like the intro's case-card)
        render_sources(sources)


        # Use retrieved chunks as context for a RAG response, each one
        # labelled with its paragraph range so the model can cite it
        context = "\n\n---\n\n".join(
            f"[Paragraphs {source['paragraphs'] or 'unspecified'}]\n{source['doc']}"
            for source in sources
        )


        # System instructions
        system_prompt = f"""
You are a legal research assistant on the relevant PRODUCT market in
{CASE_NAME} (paragraphs 10–35 only; not geographic market or other parts
of the case). Use only the retrieved context below — no outside knowledge.

If the user's message isn't a clear, answerable question (too short,
ambiguous, a single word/number, etc.), don't guess what they meant —
ask them to clarify instead of answering. If the context lacks the
answer, say so; never make anything up.

Distinguish clearly between the applicant's arguments, the Commission's
arguments, and the Court's own reasoning/findings.

Each chunk is labelled with its paragraph range, e.g. "[Paragraphs
§§ 22–27]". Cite that range right after ANY sentence drawing on it —
including the opening sentence, and including when you're merely
paraphrasing/characterising a party's argument or the Court's holding,
not just stating a fact. Cite each chunk used, at the point you use it.

Example:
Q: "How did the Court respond to the applicant's argument that bananas
are interchangeable with other fresh fruit?"
A: "The applicant argued that bananas are reasonably interchangeable
with other fresh fruit, pointing to shared shops, shelves and prices
(§§ 12–13). The Court rejected this, holding that bananas have specific
characteristics — such as year-round availability — that limit their
interchangeability with other fruit to only a limited extent (§§ 22–27)."
(Note the opening sentence is cited too — follow this pattern always.)
"""


        # Keep recent conversation history — strip any extra keys (like
        # "sources") so only role/content is sent to the API
        history = [
            {
                "role": message["role"],
                "content": message["content"]
            }
            for message in st.session_state.messages[-6:-1]
        ]


        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        messages += history

        messages.append(
            {
                "role": "user",
                "content": f"""
Retrieved context:

{context}

Question:

{query}
"""
            }
        )


        # Generate RAG response
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):

            try:

                with st.spinner("Generating response..."):

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0,
                    )

                answer = response.choices[0].message.content

                st.write(answer)

            except Exception:

                st.error(
                    "Something went wrong generating a response. "
                    "Please try again in a moment."
                )

                st.stop()


        # Save assistant response, along with the sources used, so the
        # "Retrieved chunks" expander can be replayed for this answer
        # even after later questions are asked
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": sources
            }
        )


    # --- Example questions — rendered last so they always sit below the
    # full conversation (including anything just answered this run),
    # directly above the fixed chat input at the bottom of the page.
    #
    # A pool larger than the number of visible slots means each click
    # swaps that slot for a fresh, not-yet-shown question instead of
    # just re-triggering the same one. ---

    EXAMPLE_POOL = [
        (
            "Applicant's argument",
            "What argument did the applicant make about the "
            "interchangeability of bananas with other fresh fruit?"
        ),
        (
            "Commission's response",
            "How did the Commission respond to the applicant's "
            "argument about interchangeability?"
        ),
        (
            "Court's reasoning",
            "What characteristics of bananas did the Court rely on "
            "in reaching its conclusion?"
        ),
        (
            "Seasonal substitution",
            "What did the Court find about seasonal substitution "
            "between bananas and other fresh fruit?"
        ),
        (
            "Cross-elasticity evidence",
            "What evidence did the Court consider regarding "
            "cross-elasticity between bananas and other fruit?"
        ),
        (
            "Overall conclusion",
            "What was the Court's overall conclusion on whether "
            "bananas form a distinct market?"
        ),
    ]

    NUM_EXAMPLE_SLOTS = 3

    if "example_slots" not in st.session_state:
        st.session_state.example_slots = list(range(NUM_EXAMPLE_SLOTS))

    # Indices that have ever been clicked — kept separately from
    # example_slots so a question can never resurface once asked, even
    # after it scrolls out of the currently-visible slots.
    if "used_examples" not in st.session_state:
        st.session_state.used_examples = set()


    def next_unused_example():
        shown = {
            slot for slot in st.session_state.example_slots
            if slot is not None
        }
        excluded = shown | st.session_state.used_examples
        for i in range(len(EXAMPLE_POOL)):
            if i not in excluded:
                return i
        return None  # pool exhausted — no fresh question left


    visible_slots = [
        slot for slot in st.session_state.example_slots if slot is not None
    ]

    if visible_slots:

        st.markdown(
            '<div class="teaser">Try one of these, or ask your own '
            'question below:</div>',
            unsafe_allow_html=True
        )

        example_cols = st.columns(len(st.session_state.example_slots))

        for slot_pos, col in enumerate(example_cols):

            idx = st.session_state.example_slots[slot_pos]

            if idx is None:
                continue

            label, question = EXAMPLE_POOL[idx]

            with col:

                if st.button(
                    label,
                    key=f"example_slot_{slot_pos}",
                    use_container_width=True,
                    help=question
                ):
                    st.session_state.pending_query = question

                    # Permanently retire this question, then swap the
                    # slot for a fresh, never-shown one
                    st.session_state.used_examples.add(idx)
                    st.session_state.example_slots[slot_pos] = (
                        next_unused_example()
                    )

                    st.rerun()