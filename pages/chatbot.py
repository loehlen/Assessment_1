import hashlib
import html
import json
import os
import re
from pathlib import Path

import chromadb
import streamlit as st
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from openai import OpenAI

from shared import (
    CASE_NAME,
    PAGE_ICON,
    aglc_pinpoint,
    apply_styles,
    case_card,
    page_header,
    teaser,
)

load_dotenv()

st.set_page_config(
    page_title="United Brands v Commission — Chatbot",
    page_icon=PAGE_ICON,
)
apply_styles()


# --------------------------------------------------
# Settings
# --------------------------------------------------

ASSISTANT_AVATAR = PAGE_ICON
USER_AVATAR = "🙋‍♀️"

CHUNKS_FOLDER = "Chunks - United Brands v Commission - Relevant Product Market"
N_RESULTS = 3
HOME_PAGE = "home.py"

ANSWER_MODEL = "gpt-4o"
REWRITE_MODEL = "gpt-4o"

# Show a small note under each answer when the automatic check found and
# corrected problems. Useful for testing; set to False to hide it.
SHOW_CHECK_NOTES = True
MAX_REVISIONS = 2

NOT_ADDRESSED_REPLY = (
    "This chatbot covers the relevant product market (paragraphs 10–35), "
    "and the retrieved paragraphs do not address this question."
)

# Each chunk file covers one step of the reasoning. For each file:
# - "paragraphs": range (first, last), shown on the source cards
# - "speaker": whose position the chunk sets out, shown on the cards
#   and given to the model (paragraph text often doesn't name it)
# - "note" (optional): finer attribution for the model where a chunk
#   mixes voices or reads like fact but is a party's evidence
# Keyed by filename, so the mapping can't silently desync if files are
# added, removed or resplit.
CHUNKS = {
    "01_framing_legal_test.txt": {
        "paragraphs": (10, 11),
        "speaker": "The Court",
    },
    "02_applicant_argument_interchangeability.txt": {
        "paragraphs": (12, 13),
        "speaker": "The Court / The applicant",
        "note": (
            "[12] is the Court setting out the question; it records the "
            "applicant's position and states the alternative (a separate "
            "banana market) without attributing that alternative to the "
            "applicant. [13] is the applicant's argument."
        ),
    },
    "03_applicant_evidence_seasonal_data.txt": {
        "paragraphs": (14, 18),
        "speaker": "The applicant",
        "note": (
            "[14]–[17] set out the findings from which the applicant draws "
            "its conclusion in [18]; they are evidence relied on by the "
            "applicant, not findings of the Court. The judgment does not "
            "say who produced the statistics in [14], so describe them only "
            "as relied on by the applicant, never as produced or provided "
            "by it. The FAO studies in [15]–[16] were carried out by the "
            "FAO and quoted by the applicant."
        ),
    },
    "04_commission_rebuttal.txt": {
        "paragraphs": (19, 21),
        "speaker": "The Commission",
    },
    "05_court_test_special_features.txt": {
        "paragraphs": (22, 27),
        "speaker": "The Court",
    },
    "06_court_cross_elasticity_data.txt": {
        "paragraphs": (28, 30),
        "speaker": "The Court",
    },
    "07_court_banana_characteristics.txt": {
        "paragraphs": (31, 33),
        "speaker": "The Court",
    },
    "08_court_conclusion.txt": {
        "paragraphs": (34, 35),
        "speaker": "The Court",
    },
}


# --------------------------------------------------
# Password
# --------------------------------------------------

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:

    page_header("Relevant Product Market Chatbot")
    teaser("Enter the password to access the chatbot.")

    password_input = st.text_input(
        label="Password",
        type="password",
        placeholder="Enter password",
    )

    if password_input:
        if password_input == os.environ["PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()  # nothing below runs until the password is correct


# --------------------------------------------------
# Vector store
# --------------------------------------------------

os.environ["CHROMA_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]


@st.cache_resource
def get_collection():

    client = chromadb.PersistentClient(path="./my_chroma_db")

    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        model_name="text-embedding-3-large",
    )

    collection = client.get_or_create_collection(
        name="united_brands_relevant_market",
        embedding_function=openai_ef,
    )

    folder = Path(CHUNKS_FOLDER)

    if folder.exists():

        with st.spinner("Loading case materials..."):

            documents, metadatas, ids = [], [], []

            for file in sorted(folder.glob("*.txt")):

                text = file.read_text(encoding="utf-8", errors="ignore").strip()

                if not text:
                    continue

                info = CHUNKS.get(file.name)

                if info:
                    paragraphs = aglc_pinpoint(*info["paragraphs"])
                    speaker = info["speaker"]
                    note = info.get("note", "")
                else:
                    paragraphs, speaker, note = "", "", ""
                    st.warning(
                        f"No entry for {file.name} in CHUNKS — "
                        "add its paragraph range and speaker."
                    )

                documents.append(text)
                metadatas.append({
                    "source": CASE_NAME,
                    "filename": file.name,
                    "paragraphs": paragraphs,
                    "speaker": speaker,
                    "note": note,
                })
                ids.append(hashlib.md5(file.name.encode()).hexdigest())

            if documents:
                collection.upsert(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )

    return collection


collection = get_collection()
client = OpenAI()


# --------------------------------------------------
# Follow-up questions
#
# Step 1 (code): a question that clearly stands on its own is searched
#   exactly as typed and never sent to the rewriter.
# Step 2 (model): anything else is classified by the rewriter; only
#   genuine follow-ups are rewritten into a standalone search query.
# --------------------------------------------------

# Words that usually point back to something earlier in the conversation
FOLLOW_UP_MARKERS = {
    "that", "this", "these", "those", "it", "its",
    "they", "them", "their", "he", "him", "his", "she", "her",
}

# Openings that usually continue the previous question
FOLLOW_UP_OPENERS = {"and", "but", "so", "also", "then", "what about"}

MIN_STANDALONE_WORDS = 6


def clearly_standalone(query):
    """True if the question plainly stands on its own: long enough, no
    continuing opener, and no word that refers back to the conversation.
    Anything else is left to the rewriter to classify."""

    words = re.findall(r"[a-z']+", query.lower())

    if len(words) < MIN_STANDALONE_WORDS:
        return False

    if words[0] in FOLLOW_UP_OPENERS or " ".join(words[:2]) in FOLLOW_UP_OPENERS:
        return False

    return not any(word in FOLLOW_UP_MARKERS for word in words)


REWRITE_PROMPT = """
You prepare search queries for a chatbot that searches paragraphs
10–35 of a court judgment on whether bananas form a separate product
market.

First decide whether the user's latest message is STANDALONE or a
FOLLOW-UP:
- STANDALONE: it names its own subject and makes sense without the
  conversation, even if it relates to a topic discussed earlier. Never
  narrow or extend a standalone message with the earlier topic.
- FOLLOW-UP: it only makes sense with the conversation, because it
  relies on words such as "that", "it", "they", "and the Court?" or a
  bare "why?".

For a FOLLOW-UP, write one standalone search query that replaces those
references with the SPECIFIC subject from the conversation (which
party, which argument, which fruit, figure or piece of evidence),
named concretely. Don't answer the question, don't add conclusions
that aren't in the conversation, and never add the case name.

Respond in JSON only, in one of these two forms:
{"standalone": true}
{"standalone": false, "query": "<rewritten query>"}

Examples

Conversation: the user asked what the applicant said about oranges;
the assistant said the applicant relied on FAO studies showing some
easing of banana prices during the "orange season".
Latest message: And the Court?
Output: {"standalone": false, "query": "What did the Court find about oranges and the orange season?"}

Conversation: the user asked what market the applicant argued for; the
assistant said the fresh fruit market, because bananas are reasonably
interchangeable with other fresh fruit.
Latest message: Why?
Output: {"standalone": false, "query": "Why did the applicant argue that bananas are reasonably interchangeable with other fresh fruit?"}

Conversation: the user asked about peaches and table grapes; the
assistant described their effect on banana prices in the summer
months.
Latest message: What did the Court find about seasonal substitution?
Output: {"standalone": true}
"""


def make_search_query(query, history):
    """Return (search_query, was_rewritten).

    First questions and clearly standalone questions are searched
    exactly as typed. Only follow-ups are rewritten. If anything goes
    wrong, fall back to the original question.
    """

    if not history or clearly_standalone(query):
        return query, False

    conversation = "\n".join(
        f"{message['role']}: {message['content']}" for message in history[-4:]
    )

    try:
        response = client.chat.completions.create(
            model=REWRITE_MODEL,
            messages=[
                {"role": "system", "content": REWRITE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Conversation so far:\n{conversation}\n\n"
                        f"Latest message: {query}"
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        data = json.loads(response.choices[0].message.content)

        if data.get("standalone", True):
            return query, False

        rewritten = (data.get("query") or "").strip()

        if not rewritten or rewritten == query.strip():
            return query, False

        return rewritten, True

    except Exception:
        return query, False


# --------------------------------------------------
# Answer check: find the problems the prompt can't reliably prevent,
# then correct them in up to MAX_REVISIONS targeted passes
# --------------------------------------------------

FLAGGED_PHRASES = [
    "including", "such as", "therefore", "thus",
    "this suggests", "this shows", "this indicates", "in other words",
]

CITATION_PATTERN = re.compile(r"\[\d+\]")


def find_issues(answer):
    """Return a list of problems, each {"label": short, "detail": full}.
    Empty if none were found."""

    if answer.strip().startswith(NOT_ADDRESSED_REPLY[:40]):
        return []

    issues = []
    lowered = answer.lower()

    for phrase in FLAGGED_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            issues.append({
                "label": f"'{phrase}'",
                "detail": f'The answer uses "{phrase}".',
            })

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", answer.strip())

    for sentence in sentences:
        is_question = sentence.rstrip().endswith("?")
        is_not_addressed = "address" in sentence.lower()
        if not is_question and not is_not_addressed and not CITATION_PATTERN.search(sentence):
            issues.append({
                "label": "uncited sentence",
                "detail": f'This sentence has no paragraph citation: "{sentence}"',
            })

    return issues


REVISE_PROMPT = """
You correct answers written by a legal research assistant. You receive
the retrieved paragraphs, the question, a draft answer and a list of
problems found in it. Fix ONLY those problems:

- A sentence without a paragraph citation: add the correct citation
  from the paragraphs in AGLC format ([29], [28]–[30], [23], [26]), or
  delete the sentence if no paragraph supports it.
- "including" or "such as": remove the word and reproduce the list
  exactly as the paragraph gives it, unless the paragraph itself uses
  that word.
- "therefore", "thus", "this suggests", "this shows", "this
  indicates", "in other words": remove the connector. Keep a causal
  link only if the cited paragraph itself states it, and then
  attribute it (e.g. "The Court stated that, since …").

Change nothing else: keep every attribution, qualifier, citation and
all other wording. Return only the corrected answer.
"""


def revise_answer(answer, context, question, issues):
    """One correction pass targeted at the listed issues.
    Returns (text, succeeded)."""

    try:
        response = client.chat.completions.create(
            model=ANSWER_MODEL,
            messages=[
                {"role": "system", "content": REVISE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Retrieved paragraphs:\n\n{context}\n\n"
                        f"Question:\n\n{question}\n\n"
                        f"Draft answer:\n\n{answer}\n\n"
                        "Problems found:\n- "
                        + "\n- ".join(issue["detail"] for issue in issues)
                    ),
                },
            ],
            temperature=0,
        )
        revised = response.choices[0].message.content.strip()
        return (revised or answer), bool(revised)

    except Exception:
        return answer, False


def check_and_correct(answer, context, question):
    """Check the answer; if problems are found, correct them in up to
    MAX_REVISIONS passes. Returns (final_answer, note or None)."""

    first_issues = find_issues(answer)

    if not first_issues:
        return answer, None

    issues = first_issues
    call_failed = False

    for _ in range(MAX_REVISIONS):
        answer, succeeded = revise_answer(answer, context, question, issues)
        if not succeeded:
            call_failed = True
            break
        issues = find_issues(answer)
        if not issues:
            break

    found = ", ".join(dict.fromkeys(i["label"] for i in first_issues))
    note = f"Automatic check: {len(first_issues)} issue(s) found ({found})"

    if call_failed:
        note += " → correction call failed; answer shown unrevised."
    elif issues:
        remaining = ", ".join(dict.fromkeys(i["label"] for i in issues))
        note += f" → revised; still present: {remaining}."
    else:
        note += " → revised."

    return answer, note


# --------------------------------------------------
# Header
# --------------------------------------------------

page_header("Relevant Product Market Chatbot")
case_card(excerpt_label="Covers")
teaser(
    "Ask questions about how the Court determined the relevant product "
    "market. The chatbot covers paragraphs 10–35 only."
)
st.divider()


# --------------------------------------------------
# Session state & sidebar
# --------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

if st.sidebar.button("← Back to case overview"):
    st.switch_page(HOME_PAGE)

if st.sidebar.button("Reset conversation"):
    st.session_state.messages = []
    st.rerun()


# --------------------------------------------------
# Conversation display
# --------------------------------------------------

def render_sources(sources, search_query=None):
    """Render the 'Retrieved chunks used for this answer' expander.
    If the question was rewritten for retrieval, show what was searched."""

    with st.expander("Retrieved chunks used for this answer"):

        if search_query:
            st.markdown(
                '<div class="paragraph-reference">Searched for: '
                f"{html.escape(search_query)}</div>",
                unsafe_allow_html=True,
            )

        for rank, source in enumerate(sources, start=1):

            parts = [f"Match {rank}", source.get("speaker"), source.get("paragraphs")]
            title = " · ".join(part for part in parts if part)

            st.markdown(
                f"""
                <div class="chunk-card">
                    <div class="chunk-title">{title}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.caption(source.get("doc", ""))


for message in st.session_state.messages:

    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR

    # Replay the retrieved-chunks expander for past assistant answers too
    if message["role"] == "assistant" and message.get("sources"):
        render_sources(message["sources"], message.get("search_query"))

    with st.chat_message(message["role"], avatar=avatar):
        st.write(message["content"])
        if SHOW_CHECK_NOTES and message.get("check_note"):
            st.caption(message["check_note"])


# --------------------------------------------------
# System prompt
# --------------------------------------------------

SYSTEM_PROMPT = f"""
You are a legal research assistant on the relevant PRODUCT market in
{CASE_NAME}, paragraphs 10–35. Answer ONLY from the retrieved
paragraphs provided with each question.

1. Source fidelity
- Every sentence reporting the judgment must be directly supported by
  a cited paragraph. If you cannot cite it, leave it out.
- Report only what the paragraphs expressly say. No inferences,
  interpretations, conclusions or implications of your own (e.g. no
  "this suggests", "this shows", "therefore"), and no outside knowledge.
- Paraphrase closely. Keep every qualifier and scope word exactly as
  the paragraph has it (e.g. "only", "mainly", "very", "too", "even",
  "not readily", "falling", "not exceeding"). Never drop or soften
  them, and never add qualifiers of your own (e.g. don't call
  something "limited" unless the paragraph does).
- When a paragraph lists items (e.g. "certain characteristics, A, B
  and C" or "consisting of X, Y and Z"), reproduce the list as given.
  Never introduce it with "including" or "such as", which would turn
  a closed list into an open one.
- If the paragraphs don't address the question, reply only:
  "{NOT_ADDRESSED_REPLY}" Don't summarise what the paragraphs contain
  instead. If they address only part of the question, answer that part
  and say the rest isn't addressed. Never make anything up.

2. Attribution
- Each retrieved chunk begins with a "Source:" line stating whose
  position its paragraphs set out, and sometimes a "Note:" line that
  attributes individual paragraphs more precisely. Follow the Note
  where there is one, and never attribute a statement to anyone else.
- Every sentence must OPEN by naming its source: "The applicant
  argued…", "The Commission submitted…", "The Court found…".
- For evidence, name who relied on it: "According to the statistics
  relied on by the applicant, …", "The Court referred to two FAO
  studies…". Don't say who produced, provided or carried out a piece
  of evidence unless the paragraphs or the Note expressly say so.
  This applies even when the question asks what the evidence
  "shows": never restate a party's evidence in the judgment's own
  words without naming that party first.
- If the paragraphs contain another party's or the Court's response
  to the same point, report it too, without weighing it yourself.

3. Answering the question asked
- Follow-up questions may come with an "Interpreted as:" line. Use it
  to understand what the user means.
- Answer the question actually asked, not the previous one. Never
  simply repeat an earlier answer.
- If the question asks "why", report only reasons that a paragraph
  itself states as reasons (e.g. with "since", "owing to", "because",
  or a legal test such as "for … it must be possible …"). Never create
  a causal link between separate paragraphs yourself. If no retrieved
  paragraph states a reason, say so.
- Ask the user to clarify only if the question could reasonably refer
  to more than one point in the paragraphs. Otherwise, answer it.

4. Citation (AGLC)
Each paragraph in the context starts with its number, e.g. "[29]".
Cite the specific paragraph(s) after EVERY sentence that reports the
judgment, even when consecutive sentences rely on the same paragraph.
Don't open with an uncited introductory or summary sentence: start
directly with a cited statement. Never cite a whole chunk's range,
and never cite a statement that something is not addressed:
- one paragraph: [29]
- consecutive: [28]–[30] (en dash, no spaces)
- non-consecutive: [23], [26]

Example
Q: "What did the FAO studies show about apples?"
Good: "The applicant relied on FAO studies which, it submitted, show
that the price of apples has a statistically appreciable impact on
banana consumption in the Federal Republic of Germany [15]. The Court
found only a relative degree of substitutability between bananas and
apples [29]."
Bad: "FAO studies show that apple prices affect banana consumption
[15]. This shows that apples and bananas compete in the same market."
(Presents the applicant's evidence as fact and adds an uncited
inference.)
"""


# --------------------------------------------------
# Search / RAG response
# --------------------------------------------------

query = st.chat_input("Ask a question about the relevant product market...")

if not query and st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None


if query:

    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(query)

    # Recent history (excluding the question just asked), stripped of
    # extra keys (like "sources") — used for rewriting and answering
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[-6:-1]
    ]

    # Follow-ups ("How did the Court respond to that?", "Why?") are
    # rewritten into standalone questions before searching; standalone
    # questions are searched exactly as typed
    with st.spinner("Understanding your question..."):
        search_query, was_rewritten = make_search_query(query, history)

    # Retrieve relevant chunks
    try:
        results = collection.query(query_texts=[search_query], n_results=N_RESULTS)

    except Exception:
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.error(
                "Something went wrong retrieving relevant passages. "
                "Please try asking again."
            )
        st.stop()

    # Plain list of sources, displayed now AND stored with the answer
    sources = [
        {
            "paragraphs": meta.get("paragraphs"),
            "speaker": meta.get("speaker"),
            "note": meta.get("note"),
            "doc": doc,
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]

    render_sources(sources, search_query if was_rewritten else None)

    # Each chunk is headed by its speaker (and an attribution note where
    # a chunk needs one); paragraph numbers are inside the chunk text
    def chunk_for_model(source):
        header = []
        if source.get("speaker"):
            header.append(f"Source: {source['speaker']}")
        if source.get("note"):
            header.append(f"Note: {source['note']}")
        return "\n".join(header + [source["doc"]])

    context = "\n\n---\n\n".join(chunk_for_model(s) for s in sources)

    question_block = query
    if was_rewritten:
        question_block += f"\n\nInterpreted as: {search_query}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append(
        {
            "role": "user",
            "content": (
                f"Retrieved context:\n\n{context}\n\n"
                f"Question:\n\n{question_block}"
            ),
        }
    )

    # Generate the answer, check it, and correct it if needed
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):

        try:
            with st.spinner("Generating response..."):

                response = client.chat.completions.create(
                    model=ANSWER_MODEL,
                    messages=messages,
                    temperature=0,
                )
                answer = response.choices[0].message.content

                answer, check_note = check_and_correct(
                    answer, context, question_block
                )

            st.write(answer)

            if SHOW_CHECK_NOTES and check_note:
                st.caption(check_note)

        except Exception:
            st.error(
                "Something went wrong generating a response. "
                "Please try again in a moment."
            )
            st.stop()

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "search_query": search_query if was_rewritten else None,
            "check_note": check_note,
        }
    )


# --------------------------------------------------
# Example questions — rendered last so they sit below the full
# conversation, directly above the chat input. Each click retires
# that question and swaps in a fresh one from the pool.
# --------------------------------------------------

EXAMPLE_POOL = [
    (
        "Applicant's argument",
        "What argument did the applicant make about the "
        "interchangeability of bananas with other fresh fruit?",
    ),
    (
        "Commission's response",
        "How did the Commission respond to the applicant's "
        "argument about interchangeability?",
    ),
    (
        "Court's reasoning",
        "What characteristics of bananas did the Court rely on "
        "in reaching its conclusion?",
    ),
    (
        "Seasonal substitution",
        "What did the Court find about seasonal substitution "
        "between bananas and other fresh fruit?",
    ),
    (
        "Cross-elasticity evidence",
        "What evidence did the Court consider regarding "
        "cross-elasticity between bananas and other fruit?",
    ),
    (
        "Overall conclusion",
        "What was the Court's overall conclusion on whether "
        "bananas form a distinct market?",
    ),
]

NUM_EXAMPLE_SLOTS = 3

if "example_slots" not in st.session_state:
    st.session_state.example_slots = list(range(NUM_EXAMPLE_SLOTS))

# Every question ever clicked, so it can never resurface
if "used_examples" not in st.session_state:
    st.session_state.used_examples = set()


def next_unused_example():
    shown = {s for s in st.session_state.example_slots if s is not None}
    excluded = shown | st.session_state.used_examples
    for i in range(len(EXAMPLE_POOL)):
        if i not in excluded:
            return i
    return None  # pool exhausted


if any(s is not None for s in st.session_state.example_slots):

    teaser("Try one of these, or ask your own question below:")

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
                help=question,
            ):
                st.session_state.pending_query = question
                st.session_state.used_examples.add(idx)
                st.session_state.example_slots[slot_pos] = next_unused_example()
                st.rerun()