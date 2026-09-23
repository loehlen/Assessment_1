"""
Chatbot page: answers questions on paragraphs 10–35 of the judgment
from retrieved chunks (RAG).

How a question is answered
  1. Follow-ups ("Why?", "And the Court?") are rewritten into a
     standalone search query; standalone questions are searched as typed
  2. The closest chunks are retrieved from the Chroma vector store
  3. The model answers from those chunks only, citing paragraphs
  4. A silent check finds uncited sentences and banned phrases,
     and corrects them in up to MAX_REVISIONS passes

Sections
  1. Page setup and settings
  2. Vector store
  3. Prompts
  4. Follow-up questions
  5. Answer check
  6. Retrieval and answering
  7. Display helpers
  8. Page flow
"""

import hashlib
import html
import json
import os
import re
import time
from pathlib import Path

import chromadb
import streamlit as st
from chromadb.utils import embedding_functions
from openai import OpenAI

from shared import (
    CASE_NAME,
    CASE_TITLE,
    CHATBOT_SUBTITLE,
    COVERED_PARAGRAPHS,
    COVERED_PINPOINT,
    PAGE_ICON,
    aglc_pinpoint,
    compact_header,
    go_home,
    init_state,
    muted_note,
    page_header,
    render_html,
    setup_page,
)


# ==================================================
# 1. Page setup and settings
# ==================================================

# Password shared with home.py: entering it once unlocks both pages
setup_page(f"{CASE_TITLE} — Chatbot", password_subtitle=CHATBOT_SUBTITLE)

ASSISTANT_AVATAR = PAGE_ICON
USER_AVATAR = "🙋‍♀️"

CHUNKS_FOLDER = "Chunks - United Brands v Commission - Relevant Product Market"
N_RESULTS = 3

ANSWER_MODEL = "gpt-4o"
REWRITE_MODEL = "gpt-4o"

# How many correction passes the silent answer check may make
MAX_REVISIONS = 2

NOT_ADDRESSED_REPLY = (
    f"This chatbot covers the relevant product market ({COVERED_PARAGRAPHS}), "
    "and the retrieved paragraphs do not address this question."
)

# Shown as a chat bubble from the assistant before the first question.
# Display only: it is never stored in the conversation or sent to the model.
WELCOME_MESSAGE = (
    "Hi! I'm here to help you explore how the Court defined the relevant "
    f"product market in *United Brands*. Ask me anything about paragraphs "
    f"{COVERED_PINPOINT}, or pick a question below to get started."
)

# The welcome message types itself out word by word, then the starter
# questions appear one after another (first visit only). In seconds:
WELCOME_WORD_DELAY = 0.04
WELCOME_BUTTON_DELAY = 0.25

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

# Starter questions, shown as buttons under the welcome message before
# the first question only. Each button shows the question exactly as it
# will be asked.
STARTER_QUESTIONS = [
    "What did the applicant argue about bananas and other fresh fruit?",
    "How did the Commission respond to the applicant's argument?",
    "What did the Court decide about the relevant market?",
]


# ==================================================
# 2. Vector store
# ==================================================

os.environ["CHROMA_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]


def chunk_metadata(file_name):
    """Metadata stored with each chunk: its paragraph range, speaker
    and attribution note, taken from CHUNKS."""
    info = CHUNKS.get(file_name)

    if info:
        paragraphs = aglc_pinpoint(*info["paragraphs"])
        speaker = info["speaker"]
        note = info.get("note", "")
    else:
        paragraphs, speaker, note = "", "", ""
        st.warning(
            f"No entry for {file_name} in CHUNKS — "
            "add its paragraph range and speaker."
        )

    return {
        "source": CASE_NAME,
        "filename": file_name,
        "paragraphs": paragraphs,
        "speaker": speaker,
        "note": note,
    }


# show_spinner=False hides Streamlit's default "Running
# get_collection()" message; a friendlier spinner is shown below
@st.cache_resource(show_spinner=False)
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

    if not folder.exists():
        return collection

    documents, metadatas, ids = [], [], []

    for file in sorted(folder.glob("*.txt")):

        text = file.read_text(encoding="utf-8", errors="ignore").strip()

        if not text:
            continue

        documents.append(text)
        metadatas.append(chunk_metadata(file.name))
        ids.append(hashlib.md5(file.name.encode()).hexdigest())

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    return collection


with st.spinner("Getting the judgment ready for your questions…"):
    collection = get_collection()

client = OpenAI()


# ==================================================
# 3. Prompts
# ==================================================

SYSTEM_PROMPT = f"""
You are a legal research assistant on the relevant PRODUCT market in
{CASE_NAME}, {COVERED_PARAGRAPHS}. Answer ONLY from the retrieved
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


# ==================================================
# 4. Follow-up questions
#
# Step 1 (code): a question that clearly stands on its own is searched
#   exactly as typed and never sent to the rewriter.
# Step 2 (model): anything else is classified by the rewriter; only
#   genuine follow-ups are rewritten into a standalone search query.
# ==================================================

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


# ==================================================
# 5. Answer check: find the problems the prompt can't reliably
# prevent, then correct them in up to MAX_REVISIONS targeted passes
# ==================================================

FLAGGED_PHRASES = [
    "including", "such as", "therefore", "thus",
    "this suggests", "this shows", "this indicates", "in other words",
]

CITATION_PATTERN = re.compile(r"\[\d+\]")


def find_issues(answer):
    """Return a list of problems found in the answer, each as a
    description for the correction pass. Empty if none were found."""

    if answer.strip().startswith(NOT_ADDRESSED_REPLY[:40]):
        return []

    issues = []
    lowered = answer.lower()

    for phrase in FLAGGED_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            issues.append(f'The answer uses "{phrase}".')

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", answer.strip())

    for sentence in sentences:
        is_question = sentence.rstrip().endswith("?")
        is_not_addressed = "address" in sentence.lower()
        if not is_question and not is_not_addressed and not CITATION_PATTERN.search(sentence):
            issues.append(f'This sentence has no paragraph citation: "{sentence}"')

    return issues


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
                        + "\n- ".join(issues)
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
    MAX_REVISIONS passes. Runs silently and returns the final answer."""

    issues = find_issues(answer)

    for _ in range(MAX_REVISIONS):
        if not issues:
            break
        answer, succeeded = revise_answer(answer, context, question, issues)
        if not succeeded:
            break
        issues = find_issues(answer)

    return answer


# ==================================================
# 6. Retrieval and answering
# ==================================================

def retrieve_sources(search_query):
    """The N_RESULTS closest chunks, as a plain list of sources
    (displayed now AND stored with the answer)."""
    results = collection.query(query_texts=[search_query], n_results=N_RESULTS)
    return [
        {
            "paragraphs": meta.get("paragraphs"),
            "speaker": meta.get("speaker"),
            "note": meta.get("note"),
            "doc": doc,
        }
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


def chunk_for_model(source):
    """Each chunk is headed by its speaker (and an attribution note
    where a chunk needs one); paragraph numbers are inside the text."""
    header = []
    if source.get("speaker"):
        header.append(f"Source: {source['speaker']}")
    if source.get("note"):
        header.append(f"Note: {source['note']}")
    return "\n".join(header + [source["doc"]])


def generate_answer(history, context, question_block):
    """Ask the model, then check and correct its answer."""
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

    response = client.chat.completions.create(
        model=ANSWER_MODEL,
        messages=messages,
        temperature=0,
    )
    answer = response.choices[0].message.content

    return check_and_correct(answer, context, question_block)


def answer_question(query):
    """The whole round trip for one question: show it, search, answer,
    check, show the answer and store both in the conversation."""

    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(query)

    # Recent history (excluding the question just asked), stripped of
    # extra keys (like "sources") — used for rewriting and answering
    history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages[-6:-1]
    ]

    # Follow-ups are rewritten into standalone questions before
    # searching; standalone questions are searched exactly as typed
    with st.spinner("Understanding your question..."):
        search_query, was_rewritten = make_search_query(query, history)

    try:
        sources = retrieve_sources(search_query)
    except Exception:
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.error(
                "Something went wrong retrieving relevant passages. "
                "Please try asking again."
            )
        st.stop()

    shown_query = search_query if was_rewritten else None

    context = "\n\n---\n\n".join(chunk_for_model(s) for s in sources)

    question_block = query
    if was_rewritten:
        question_block += f"\n\nInterpreted as: {search_query}"

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            with st.spinner("Generating response..."):
                answer = generate_answer(history, context, question_block)
            st.write(answer)
            render_sources(sources, shown_query)

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
            "search_query": shown_query,
        }
    )


# ==================================================
# 7. Display helpers
# ==================================================

def first_paragraph(source):
    """The first paragraph number of a source, e.g. 12 for [12]–[13],
    for listing sources in the order they appear in the judgment."""
    match = re.search(r"\d+", source.get("paragraphs") or "")
    return int(match.group()) if match else 0


def render_sources(sources, search_query=None):
    """The sources expander under an answer. Its label lists the
    paragraphs used, in judgment order, so students can see where the
    answer comes from without opening it. If the question was
    rewritten for retrieval, show what was searched."""

    pinpoints = [
        s["paragraphs"]
        for s in sorted(sources, key=first_paragraph)
        if s.get("paragraphs")
    ]
    label = " · ".join(["Sources"] + pinpoints)

    with st.expander(label):

        if search_query:
            muted_note(f"Searched for: {html.escape(search_query)}")

        for rank, source in enumerate(sources, start=1):

            parts = [f"Match {rank}", source.get("speaker"), source.get("paragraphs")]
            title = " · ".join(part for part in parts if part)

            render_html(
                f"""
                <div class="chunk-card">
                    <div class="chunk-title">{title}</div>
                </div>
                """
            )

            st.caption(source.get("doc", ""))


def show_past_message(message):
    """Replay one stored message, including the retrieved-chunks
    expander for past assistant answers."""

    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR

    with st.chat_message(message["role"], avatar=avatar):
        st.write(message["content"])

        if message["role"] == "assistant" and message.get("sources"):
            render_sources(message["sources"], message.get("search_query"))


def type_out(text):
    """Yield the text word by word, with a short pause after each, so
    st.write_stream shows it being 'typed'."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(WELCOME_WORD_DELAY)


def show_welcome():
    """Before the first question: a welcome bubble from the assistant,
    with the starter questions underneath as possible replies.
    Clicking one asks it straight away.

    On the first visit the message types itself out and the questions
    appear one after another; after that (every later rerun), it all
    shows at once, so the animation doesn't replay on every click."""

    animate = not st.session_state.welcome_shown

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        if animate:
            st.write_stream(type_out(WELCOME_MESSAGE))
        else:
            st.write(WELCOME_MESSAGE)

    for position, question in enumerate(STARTER_QUESTIONS):
        if animate:
            time.sleep(WELCOME_BUTTON_DELAY)
        if st.button(question, key=f"starter_{position}"):
            st.session_state.pending_query = question
            st.rerun()

    st.session_state.welcome_shown = True


# ==================================================
# 8. Page flow
# ==================================================

init_state(
    messages=[],
    pending_query=None,    # set by the intro page or a starter question
    welcome_shown=False,   # the welcome animation has played once
)

# Sidebar first: Streamlit draws the page in code order, so this keeps
# the sidebar from waiting for the welcome animation
if st.sidebar.button("← Back to case overview"):
    go_home()

if st.sidebar.button("Reset conversation"):
    st.session_state.messages = []
    st.rerun()

# Read the question first, so the header already knows whether a
# conversation is under way (the chat input stays pinned to the bottom
# of the page wherever it is called)
query = st.chat_input("Ask a question about the relevant product market...")

if not query and st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None

# Before the first question: full header, welcome message and starter
# questions. Once a conversation is under way: a one-line header only.
if st.session_state.messages or query:
    compact_header(CHATBOT_SUBTITLE)
else:
    page_header(CHATBOT_SUBTITLE)
    show_welcome()

for message in st.session_state.messages:
    show_past_message(message)

if query:
    answer_question(query)