"""
Chatbot page: answers questions on paragraphs 10–35 of the judgment
from retrieved chunks (RAG).

How a question is answered
  1. Follow-ups ("Why?", "And the Court?") are rewritten into a
     standalone search query; standalone questions are searched as typed
  2. The closest chunks are retrieved from the Chroma vector store
  3. The model answers from those chunks only, citing paragraphs
  4. A silent check finds uncited sentences and banned phrases, and
     corrects them in up to MAX_REVISIONS passes
  5. Each citation in the answer becomes a label that shows the
     paragraph text on hover (or tap)

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
    ASSISTANT_AVATAR,
    CASE_NAME,
    CASE_TITLE,
    CHATBOT_SUBTITLE,
    CHUNKS_FOLDER,
    COVERED_PARAGRAPHS,
    COVERED_PINPOINT,
    aglc_pinpoint,
    chunk_html,
    compact_header,
    html_safe,
    init_state,
    judgment_sidebar_section,
    muted_note,
    one_line,
    page_header,
    render_html,
    setup_page,
    sidebar_label,
    sidebar_nav,
    split_paragraphs,
)

# ==================================================
# 1. Page setup and settings
# ==================================================

# Same password as home.py: entering it once unlocks both pages
setup_page(f"{CASE_TITLE} — Chatbot", password_subtitle=CHATBOT_SUBTITLE)

# The user has no avatar: their questions are pink bubbles instead
USER_AVATAR = None

N_RESULTS = 3              # chunks retrieved per question
ANSWER_MODEL = "gpt-4o"
REWRITE_MODEL = "gpt-4o"
MAX_REVISIONS = 2          # correction passes the answer check may make

NOT_ADDRESSED_REPLY = (
    f"This chatbot covers the relevant product market ({COVERED_PARAGRAPHS}), "
    "and the retrieved paragraphs do not address this question."
)

# Shown before the first question; display only, never sent to the model
WELCOME_MESSAGE = (
    "Hi! I'm here to help you explore how the Court defined the relevant "
    f"product market in *United Brands*. Ask me anything about paragraphs "
    f"{COVERED_PINPOINT}, or pick a question below to get started."
)

# First visit only: a short pause, the welcome types itself out, then the
# starter questions appear one by one (in seconds)
WELCOME_START_DELAY = 0.3
WELCOME_WORD_DELAY = 0.04
WELCOME_BUTTON_DELAY = 0.25

# Each chunk file covers one step of the reasoning, keyed by file name:
#   paragraphs  range (first, last), shown on the source cards
#   speaker     whose position the chunk sets out (for the model only)
#   note        optional finer attribution, where a chunk mixes voices
#               or reads like fact but is a party's evidence
CHUNKS = {
    "01_framing_legal_test.txt": {"paragraphs": (10, 11), "speaker": "The Court"},
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
    "04_commission_rebuttal.txt": {"paragraphs": (19, 21), "speaker": "The Commission"},
    "05_court_test_special_features.txt": {"paragraphs": (22, 27), "speaker": "The Court"},
    "06_court_cross_elasticity_data.txt": {"paragraphs": (28, 30), "speaker": "The Court"},
    "07_court_banana_characteristics.txt": {"paragraphs": (31, 33), "speaker": "The Court"},
    "08_court_conclusion.txt": {"paragraphs": (34, 35), "speaker": "The Court"},
}

# Buttons under the welcome, before the first question only
STARTER_QUESTIONS = [
    "What did the applicant argue about bananas and other fresh fruit?",
    "How did the Commission respond to the applicant's argument?",
    "What did the Court decide about the relevant product market?",
]

# ==================================================
# 2. Vector store
# ==================================================

os.environ["CHROMA_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

def chunk_metadata(file_name):
    """Paragraph range, speaker and note for a chunk, from CHUNKS."""
    info = CHUNKS.get(file_name)

    if info:
        paragraphs = aglc_pinpoint(*info["paragraphs"])
        speaker = info["speaker"]
        note = info.get("note", "")
    else:
        paragraphs, speaker, note = "", "", ""
        st.warning(f"No entry for {file_name} in CHUNKS — add its paragraph range and speaker.")

    return {
        "source": CASE_NAME,
        "filename": file_name,
        "paragraphs": paragraphs,
        "speaker": speaker,
        "note": note,
    }

# show_spinner=False: a friendlier spinner is shown below instead
@st.cache_resource(show_spinner=False)
def get_collection():
    client = chromadb.PersistentClient(path="./my_chroma_db")
    collection = client.get_or_create_collection(
        name="united_brands_relevant_market",
        embedding_function=embedding_functions.OpenAIEmbeddingFunction(
            model_name="text-embedding-3-large",
        ),
    )

    folder = Path(CHUNKS_FOLDER)
    if not folder.exists():
        return collection

    documents, metadatas, ids = [], [], []
    for file in sorted(folder.glob("*.txt")):
        text = file.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            documents.append(text)
            metadatas.append(chunk_metadata(file.name))
            ids.append(hashlib.md5(file.name.encode()).hexdigest())

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    return collection

with st.spinner("Getting the judgment ready for your questions…"):
    collection = get_collection()

client = OpenAI()

def ask_model(model, messages, **options):
    """One model call (temperature 0); returns the reply text."""
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0, **options
    )
    return response.choices[0].message.content

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

4. Layout
- If the answer has more than two sentences, write it in short
  paragraphs separated by a blank line. Start a new paragraph when the
  answer moves to a different party (the applicant, the Commission,
  the Court) or to a different point.
- Plain prose only: no headings, bullet points or bold text.

5. Citation (AGLC)
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
banana consumption in the Federal Republic of Germany [15].

The Court found only a relative degree of substitutability between
bananas and apples [29]."
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

Change nothing else: keep every attribution, qualifier, citation,
all other wording and the paragraph breaks exactly as they are.
Return only the corrected answer.
"""

# ==================================================
# 4. Follow-up questions
#
# Clearly standalone questions are searched exactly as typed. Anything
# else goes to the rewriter, which rewrites genuine follow-ups only.
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
    """True if the question is long enough, has no continuing opener
    and no word that refers back to the conversation."""
    words = re.findall(r"[a-z']+", query.lower())

    if len(words) < MIN_STANDALONE_WORDS:
        return False
    if words[0] in FOLLOW_UP_OPENERS or " ".join(words[:2]) in FOLLOW_UP_OPENERS:
        return False
    return not any(word in FOLLOW_UP_MARKERS for word in words)

def make_search_query(query, history):
    """Return (search_query, was_rewritten). Falls back to the original
    question if anything goes wrong."""
    if not history or clearly_standalone(query):
        return query, False

    conversation = "\n".join(f"{m['role']}: {m['content']}" for m in history[-4:])

    try:
        reply = ask_model(
            REWRITE_MODEL,
            [
                {"role": "system", "content": REWRITE_PROMPT},
                {
                    "role": "user",
                    "content": f"Conversation so far:\n{conversation}\n\nLatest message: {query}",
                },
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(reply)

        if data.get("standalone", True):
            return query, False

        rewritten = (data.get("query") or "").strip()
        if not rewritten or rewritten == query.strip():
            return query, False
        return rewritten, True

    except Exception:
        return query, False

# ==================================================
# 5. Answer check: find what the prompt can't reliably prevent, then
# correct it in up to MAX_REVISIONS targeted passes
# ==================================================

FLAGGED_PHRASES = [
    "including", "such as", "therefore", "thus",
    "this suggests", "this shows", "this indicates", "in other words",
]

CITATION_PATTERN = re.compile(r"\[\d+\]")

def find_issues(answer):
    """A list of problems in the answer (empty if none)."""
    if answer.strip().startswith(NOT_ADDRESSED_REPLY[:40]):
        return []

    issues = [
        f'The answer uses "{phrase}".'
        for phrase in FLAGGED_PHRASES
        if re.search(rf"\b{re.escape(phrase)}\b", answer.lower())
    ]

    # Questions and "not addressed" sentences need no citation
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", answer.strip()):
        is_question = sentence.rstrip().endswith("?")
        is_not_addressed = "address" in sentence.lower()
        if not is_question and not is_not_addressed and not CITATION_PATTERN.search(sentence):
            issues.append(f'This sentence has no paragraph citation: "{sentence}"')

    return issues

def revise_answer(answer, context, question, issues):
    """One correction pass. Returns (text, succeeded)."""
    try:
        revised = ask_model(
            ANSWER_MODEL,
            [
                {"role": "system", "content": REVISE_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Retrieved paragraphs:\n\n{context}\n\n"
                        f"Question:\n\n{question}\n\n"
                        f"Draft answer:\n\n{answer}\n\n"
                        "Problems found:\n- " + "\n- ".join(issues)
                    ),
                },
            ],
        ).strip()
        return (revised or answer), bool(revised)

    except Exception:
        return answer, False

def check_and_correct(answer, context, question):
    """Silently check the answer and correct it if needed."""
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
    """The N_RESULTS closest chunks, closest first (shown now and
    stored with the answer)."""
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
    """A chunk headed by its speaker (and note, if any)."""
    header = []
    if source.get("speaker"):
        header.append(f"Source: {source['speaker']}")
    if source.get("note"):
        header.append(f"Note: {source['note']}")
    return "\n".join(header + [source["doc"]])

def generate_answer(history, context, question_block):
    """Ask the model, then check and correct its answer."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {
            "role": "user",
            "content": f"Retrieved context:\n\n{context}\n\nQuestion:\n\n{question_block}",
        },
    ]
    answer = ask_model(ANSWER_MODEL, messages)
    return check_and_correct(answer, context, question_block)

def answer_question(query):
    """One question, start to finish: show it, search, answer, show
    the answer and store both in the conversation."""
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(query)

    # Recent history, without the question just asked or extra keys
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[-6:-1]
    ]

    with st.spinner("Understanding your question…"):
        search_query, was_rewritten = make_search_query(query, history)

    try:
        sources = retrieve_sources(search_query)
    except Exception:
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.error("Something went wrong retrieving relevant passages. Please try asking again.")
        st.stop()

    shown_query = search_query if was_rewritten else None
    context = "\n\n---\n\n".join(chunk_for_model(s) for s in sources)
    question_block = query
    if was_rewritten:
        question_block += f"\n\nInterpreted as: {search_query}"

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            with st.spinner("Reading the paragraphs…"):
                answer = generate_answer(history, context, question_block)
            render_answer(answer, sources)
            render_sources(sources, shown_query)
        except Exception:
            st.error("Something went wrong generating a response. Please try again in a moment.")
            st.stop()

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources, "search_query": shown_query}
    )

# ==================================================
# 7. Display helpers
# ==================================================

# A pinpoint in an answer: [29], or a range [28]–[30]
PINPOINT_PATTERN = re.compile(r"\[(\d+)\](?:\s*[–-]\s*\[(\d+)\])?")

def paragraph_texts(sources):
    """{paragraph number: text} for every retrieved paragraph."""
    texts = {}
    for source in sources:
        _, pairs = split_paragraphs(source.get("doc", ""))
        for number, text in pairs:
            texts[int(number)] = one_line(text)
    return texts

def render_answer(answer, sources):
    """The answer, with every pinpoint turned into a pink label that
    shows the paragraph text on hover or tap (plain label if the
    paragraph wasn't retrieved)."""
    texts = paragraph_texts(sources)

    def to_label(match):
        first = int(match.group(1))
        last = int(match.group(2) or first)
        pinpoint = match.group(0)

        numbers = [n for n in range(first, last + 1) if n in texts]
        if not numbers:
            return f'<span class="cite">{pinpoint}</span>'

        paragraphs = "".join(
            f'<span class="cite-paragraph"><b>[{n}]</b> {html_safe(texts[n])}</span>'
            for n in numbers
        )
        return (
            f'<span class="cite" tabindex="0">{pinpoint}'
            f'<span class="cite-pop"><span class="cite-pop-inner">{paragraphs}</span></span>'
            f"</span>"
        )

    render_html(PINPOINT_PATTERN.sub(to_label, answer))

def render_sources(sources, search_query=None):
    """The "Sources" expander: one card per retrieved chunk, closest
    match first, laid out like the judgment. Shows the rewritten search
    query, if there was one."""
    pinpoints = [s["paragraphs"] for s in sources if s.get("paragraphs")]

    with st.expander(" · ".join(["Sources"] + pinpoints)):
        if search_query:
            muted_note(f"Searched for: {html.escape(search_query)}")

        for rank, source in enumerate(sources, start=1):
            title = " · ".join(p for p in [f"Match {rank}", source.get("paragraphs")] if p)
            # One line: Streamlit reads indented lines as a code block
            render_html(
                f'<div class="chunk-card"><div class="chunk-title">{title}</div>'
                f'{chunk_html(source.get("doc", ""))}</div>'
            )

def show_past_message(message):
    """Replay one stored message, with citation labels and sources."""
    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR

    with st.chat_message(message["role"], avatar=avatar):
        if message["role"] == "assistant" and message.get("sources"):
            render_answer(message["content"], message["sources"])
            render_sources(message["sources"], message.get("search_query"))
        else:
            st.write(message["content"])

def type_out(text):
    """Yield the text word by word, so st.write_stream 'types' it."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(WELCOME_WORD_DELAY)

def show_welcome():
    """Welcome bubble with the starter questions underneath. Animated
    on the first visit only, so it doesn't replay on every click."""
    animate = not st.session_state.welcome_shown

    if animate:
        time.sleep(WELCOME_START_DELAY)  # let the password screen clear

    # The key gives the container the CSS class st-key-welcome
    with st.container(key="welcome"):
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

# Sidebar first, so it doesn't wait for the welcome animation
sidebar_nav()

sidebar_label("Conversation")
if st.sidebar.button("Reset conversation", key="reset", use_container_width=True):
    st.session_state.messages = []
    st.rerun()
st.sidebar.caption("Clears the chat so you can start afresh.")

judgment_sidebar_section()

# Read the question before drawing the header, so the header knows
# whether a conversation is under way (the input stays pinned to the
# bottom wherever it is called)
query = st.chat_input("Ask a question about the relevant product market...")

if not query and st.session_state.pending_query:
    query = st.session_state.pending_query
    st.session_state.pending_query = None

# Full header and welcome before the first question, a one-line header
# after. The placeholder is cleared as soon as a question is asked, so
# the welcome doesn't linger while the answer loads.
top = st.empty()
with top.container():
    if st.session_state.messages or query:
        compact_header(CHATBOT_SUBTITLE)
    else:
        page_header(CHATBOT_SUBTITLE)
        show_welcome()

for message in st.session_state.messages:
    show_past_message(message)

if query:
    answer_question(query)
 
