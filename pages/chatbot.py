"""
Chatbot page: answers questions on paragraphs 10–35 of the judgment
from retrieved chunks (RAG).

How a question is answered
  1. Follow-ups ("Why?", "And the Court?") are rewritten into a
     standalone search query; standalone questions are searched as typed
  2. Hybrid retrieval: the query is searched against whole chunks and
     against single paragraphs. The two rankings are merged with
     reciprocal rank fusion, and the N_RESULTS best chunks are passed
     to the model as whole chunks
  3. The model answers from those chunks only, citing paragraphs
  4. A check finds uncited sentences, sentences that don't name their
     source and flagged phrases, and corrects them in up to
     MAX_REVISIONS passes
  5. Each citation in the answer becomes a label that shows the
     paragraph text on hover (or tap)

Sections
  1. Page setup and settings
  2. Vector store (chunks and paragraphs)
  3. Prompts
  4. Follow-up questions
  5. Answer check
  6. Retrieval and answering
  7. Display helpers
  8. Page flow
"""

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
    HOME_PAGE,
    SUBHEADING_PATTERNS,
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

N_RESULTS = 3              # chunks passed to the model per question
RRF_K = 60                 # reciprocal rank fusion constant (standard value)
ANSWER_MODEL = "gpt-4o"
REWRITE_MODEL = "gpt-4o"
MAX_REVISIONS = 2          # correction passes the answer check may make

# True while testing: shows where each chunk ranked in each search and
# any problems the answer check could not fix. False for users.
SHOW_DEBUG = False

NOT_ADDRESSED_REPLY = (
    "The passages retrieved for this question don't address it. This "
    f"chatbot covers only the relevant product market ({COVERED_PARAGRAPHS}); "
    "if your question is about that, try rephrasing it. The full judgment "
    "is linked under \"Read the judgment\" in the sidebar."
)

# Shown before the first question; display only, never sent to the model
WELCOME_MESSAGE = (
    "Hi! I'm here to help you explore how the Court defined the relevant "
    f"product market in *United Brands*. Ask me anything about paragraphs "
    f"{COVERED_PINPOINT}, or pick a question below to get started."
)

# Shown in the chatbot's bubble while a question is searched and answered
THINKING_HTML = (
    '<div class="thinking">'
    '<span class="thinking-dot"></span>'
    '<span class="thinking-dot"></span>'
    '<span class="thinking-dot"></span>'
    '<span class="thinking-text">Reading the judgment…</span>'
    "</div>"
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
    "Did the Court find that bananas form a market of their own?",
]


# ==================================================
# 2. Vector store (chunks and paragraphs)
#
# The same judgment text is stored at two levels:
#   - whole chunks: each step of the reasoning as one unit, which suits
#     questions about a step as a whole
#   - single paragraphs: a point made in one paragraph is not diluted
#     by the rest of its chunk
# Both are searched, and the model always receives whole chunks, so
# back-references ("these studies", "this particular feature") arrive
# together with the paragraphs they refer to.
# ==================================================

os.environ["CHROMA_OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

CHUNK_COLLECTION = "united_brands_chunks"
PARAGRAPH_COLLECTION = "united_brands_paragraphs"


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


def clean_paragraph(body):
    """One paragraph's text on a single line, without any subheading."""
    for pattern in SUBHEADING_PATTERNS:
        body = pattern.sub(" ", body)
    return one_line(body)


# show_spinner=False: a friendlier spinner is shown below instead
@st.cache_resource(show_spinner=False)
def load_store():
    """Both collections, plus the chunks passed to the model. Returns
    (chunk_collection, paragraph_collection, chunks), where chunks maps
    each file name to its full text and metadata."""
    client = chromadb.PersistentClient(path="./my_chroma_db")
    embedder = embedding_functions.OpenAIEmbeddingFunction(
        model_name="text-embedding-3-large",
    )
    chunk_collection = client.get_or_create_collection(
        name=CHUNK_COLLECTION, embedding_function=embedder
    )
    paragraph_collection = client.get_or_create_collection(
        name=PARAGRAPH_COLLECTION, embedding_function=embedder
    )

    chunks = {}
    folder = Path(CHUNKS_FOLDER)
    if not folder.exists():
        return chunk_collection, paragraph_collection, chunks

    chunk_docs, chunk_metas, chunk_ids = [], [], []
    para_docs, para_metas, para_ids = [], [], []

    for file in sorted(folder.glob("*.txt")):
        text = file.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        metadata = chunk_metadata(file.name)
        chunks[file.name] = {"doc": text, **metadata}

        chunk_docs.append(text)
        chunk_metas.append(metadata)
        chunk_ids.append(file.name)

        _, pairs = split_paragraphs(text)
        for number, body in pairs:
            paragraph = clean_paragraph(body)
            if paragraph:
                para_docs.append(paragraph)
                para_metas.append({"filename": file.name, "paragraph": int(number)})
                para_ids.append(f"{file.name}#{number}")

    if chunk_docs:
        chunk_collection.upsert(documents=chunk_docs, metadatas=chunk_metas, ids=chunk_ids)
    if para_docs:
        paragraph_collection.upsert(documents=para_docs, metadatas=para_metas, ids=para_ids)

    return chunk_collection, paragraph_collection, chunks


with st.spinner("Getting the judgment ready for your questions…"):
    chunk_collection, paragraph_collection, chunks = load_store()

client = OpenAI()


def ask_model(model, messages, **options):
    """One model call (temperature 0); returns the reply text."""
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0, **options
    )
    return response.choices[0].message.content


# ==================================================
# 3. Prompts
#
# General rules for reporting a judgment: none of them refers to this
# case's facts, parties' arguments or paragraph numbers.
# ==================================================

SYSTEM_PROMPT = f"""
You are a legal research assistant for {CASE_NAME},
{COVERED_PARAGRAPHS} (the relevant product market). Answer only from
the retrieved paragraphs supplied with each question, never from
outside knowledge.

Fidelity
- Report only what the paragraphs say. Every sentence must be
  supported by the paragraph it cites; leave out anything you cannot
  cite. No inferences, conclusions or summaries of your own.
- Paraphrase closely. Keep every qualifier and scope word (e.g. "only",
  "very", "even", "too", "sufficiently", "mainly", "not exceeding"),
  and add none of your own.
- Reproduce lists as the paragraph gives them: keep "such as … etc."
  where the paragraph has it, and never open a closed list with
  "including" or "such as".
- Don't join statements with causal words ("because", "as", "so",
  "due to", "which means", "indicating") unless the paragraph itself
  states that link. You may follow the judgment's own back-references
  ("these studies", "this feature", "these months") to what they
  refer to.

Attribution
- Open every sentence that reports the judgment by naming its source:
  the applicant, the Commission, the Court, or a piece of evidence
  (e.g. "According to the studies relied on by the applicant, …").
  Never open it with "This", "These", "It", "However" or "Although".
- Follow each chunk's "Source:" and "Note:" lines. Where a paragraph
  reports what studies or statistics show, attribute the content to
  them, even within the Court's reasoning, and don't say who produced
  them unless the paragraph does.
- A statement of what must be shown ("for X to be …, it must be
  possible …") sets a test; it is not a finding. Report it as the
  requirement the Court set, and report findings separately, where a
  paragraph states them.
- Where the paragraphs contain another party's or the Court's response
  to the same point, report it too, without weighing it.

Answering
- Answer the question asked, not an earlier one. An "Interpreted as:"
  line explains a follow-up. For "why", give only reasons a paragraph
  itself states.
- If the question assumes something that a retrieved paragraph
  contradicts, correct it before anything else, in one sentence that
  cites the paragraph stating the actual position (e.g. "Contrary to
  the question, the Court found that Y [n]."). Never cite a paragraph
  that only records the assumption, such as a party's argument, for
  the correction.
- You only see the passages retrieved for this question, not the
  whole judgment. Never conclude from a missing passage that the Court
  or the judgment did not decide, say or address something; only a
  retrieved paragraph that states the opposite can show that.
- The chatbot covers only the relevant product market. If a question
  is about something outside it (e.g. the geographic market or
  whether there was an abuse), report what the retrieved paragraphs
  say that bears on it, with citations, then say in one sentence that
  the rest is outside this chatbot's scope. Never answer from outside
  knowledge.
- If the question asks about several things and the passages cover
  only some of them, answer those and name the part that isn't
  covered in one closing sentence. Add no such sentence when the
  answer is complete. If the passages don't cover the question at
  all, reply only, once: "{NOT_ADDRESSED_REPLY}"
- Ask for clarification only if the question could refer to more than
  one point in the paragraphs.

Format
- Lead with the direct answer. Plain prose, no headings, bullets or
  bold; short paragraphs, starting a new one for each party or point.
- Cite (AGLC) after every sentence that reports the judgment, using
  the specific paragraph(s): [29], [28]–[30], [23], [26]. Don't cite a
  statement that something isn't covered.
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
  relies on words such as "that", "it", "they", "them", "and the
  Court?" or a bare "why?".

For a FOLLOW-UP, write one standalone search query:
- Replace ONLY the words that point back ("it", "them", "that", "and
  the Court?") with the SPECIFIC subject they refer to (which party,
  argument, fruit, figure or piece of evidence), named concretely.
- Keep the rest of the user's wording. Don't add any other terms from
  the conversation, and in particular no terms taken from the
  assistant's earlier answers (e.g. "substitutability",
  "interchangeability", "cross-elasticity") unless the user used them.
  Such terms belong to one party's reasoning and pull the search
  towards that party.
- For a bare "why?", name the specific point being asked about.
- Don't answer the question, don't add conclusions that aren't in the
  conversation, and never add the case name.

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

Conversation: the user asked what the Court found about peaches and
table grapes; the assistant described the seasonal substitutability
the studies showed in West Germany.
Latest message: What did the Commission say about them?
Output: {"standalone": false, "query": "What did the Commission say about peaches and table grapes?"}

Conversation: the user asked about peaches and table grapes; the
assistant described their effect on banana prices in the summer
months.
Latest message: What did the Court find about seasonal substitution?
Output: {"standalone": true}
"""


REVISE_PROMPT = """
You correct a draft answer written by a legal research assistant. You
receive the retrieved paragraphs, the question, the draft and a list
of problems found in it. Fix ONLY those problems:

- A sentence without a citation: add the correct paragraph citation
  in AGLC format ([29], [28]–[30], [23], [26]), or delete the sentence
  if no paragraph supports it.
- A sentence that doesn't name its source: rewrite its opening so it
  names who says it (the applicant, the Commission, the Court, or a
  piece of evidence), as the cited paragraph attributes it.
- A flagged word or phrase: remove it. For "including", "includes" or
  "such as", reproduce the list exactly as the paragraph gives it.
  For a connector ("therefore", "however", "indicating", "due to" …),
  keep a causal link only if the cited paragraph itself states it.

Change nothing else: keep every attribution, qualifier, citation, all
other wording and the paragraph breaks. Return only the corrected
answer.
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

# Flagged only if the retrieved paragraphs don't use the phrase
# themselves (e.g. "such as" is fine where the judgment says "such as")
FLAGGED_PHRASES = [
    "including", "include", "includes", "such as",
    "therefore", "thus", "however", "due to", "in other words",
    "this suggests", "this shows", "this indicates", "indicating",
    "this means", "which means", "which allows", "allowing",
]

# Sentence openings that don't name a source
UNATTRIBUTED_OPENERS = {
    "this", "these", "that", "those", "it", "they", "such",
    "although", "even", "consequently",
}

CITATION_PATTERN = re.compile(r"\[\d+\]")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
NOT_COVERED_PATTERN = re.compile(r"\b(address|cover|scope)", re.IGNORECASE)


def contains(phrase, text):
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def find_issues(answer, source_text=""):
    """A list of problems in the answer (empty if none)."""
    if answer.strip().startswith(NOT_ADDRESSED_REPLY[:40]):
        return []

    answer_lower, source_lower = answer.lower(), source_text.lower()
    issues = [
        f'The answer uses "{phrase}", which the paragraphs do not use.'
        for phrase in FLAGGED_PHRASES
        if contains(phrase, answer_lower) and not contains(phrase, source_lower)
    ]

    for sentence in SENTENCE_BREAK.split(answer.strip()):
        sentence = sentence.strip()
        # Questions and "not covered" sentences need no citation or speaker
        if not sentence or sentence.endswith("?") or NOT_COVERED_PATTERN.search(sentence):
            continue

        if not CITATION_PATTERN.search(sentence):
            issues.append(f'This sentence has no paragraph citation: "{sentence}"')

        first_word = re.match(r"[A-Za-z']+", sentence)
        if first_word and first_word.group(0).lower() in UNATTRIBUTED_OPENERS:
            issues.append(f'This sentence does not name its source: "{sentence}"')

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


def check_and_correct(answer, context, question, source_text):
    """Check the answer and correct it if needed. Returns (answer,
    remaining issues), so problems that survive can be shown in debug
    mode instead of failing silently."""
    issues = find_issues(answer, source_text)

    for _ in range(MAX_REVISIONS):
        if not issues:
            break
        answer, succeeded = revise_answer(answer, context, question, issues)
        if not succeeded:
            break
        issues = find_issues(answer, source_text)

    return answer, issues


# ==================================================
# 6. Retrieval and answering
# ==================================================

def rank_by_chunk(text):
    """All chunks, closest whole chunk first."""
    results = chunk_collection.query(
        query_texts=[text], n_results=chunk_collection.count()
    )
    return [meta.get("filename") for meta in results["metadatas"][0]]


def rank_by_paragraph(text):
    """All chunks, ordered by their closest paragraph. Returns
    (order, best), where best maps each chunk to that paragraph."""
    results = paragraph_collection.query(
        query_texts=[text], n_results=paragraph_collection.count()
    )
    order, best = [], {}
    for meta in results["metadatas"][0]:
        name = meta.get("filename")
        if name not in best:
            best[name] = meta.get("paragraph")
            order.append(name)
    return order, best


def position(order, name):
    """1-based position of a chunk in a ranking, or None."""
    return order.index(name) + 1 if name in order else None


def retrieve_sources(search_query):
    """Hybrid retrieval: rank the chunks by whole-chunk search and by
    paragraph search, merge the two rankings with reciprocal rank
    fusion, and return the N_RESULTS best chunks. Each source records
    its positions, for debug mode."""
    if chunk_collection.count() == 0 or paragraph_collection.count() == 0:
        raise RuntimeError("The vector store is empty.")

    chunk_order = rank_by_chunk(search_query)
    paragraph_order, best = rank_by_paragraph(search_query)

    # Reciprocal rank fusion: 1 / (k + rank) from each ranking, added up
    scores = {}
    for order in (chunk_order, paragraph_order):
        for rank, name in enumerate(order, start=1):
            scores[name] = scores.get(name, 0) + 1 / (RRF_K + rank)

    ranked = sorted(
        (name for name in scores if name in chunks),
        key=lambda name: (-scores[name], position(chunk_order, name) or 99),
    )

    return [
        {
            "paragraphs": chunks[name].get("paragraphs"),
            "speaker": chunks[name].get("speaker"),
            "note": chunks[name].get("note"),
            "doc": chunks[name]["doc"],
            "chunk_rank": position(chunk_order, name),
            "paragraph_rank": position(paragraph_order, name),
            "matched": aglc_pinpoint(best[name]) if name in best else None,
        }
        for name in ranked[:N_RESULTS]
    ]


def chunk_for_model(source):
    """A chunk headed by its speaker (and note, if any)."""
    header = []
    if source.get("speaker"):
        header.append(f"Source: {source['speaker']}")
    if source.get("note"):
        header.append(f"Note: {source['note']}")
    return "\n".join(header + [source["doc"]])


def generate_answer(history, context, question_block, source_text):
    """Ask the model, then check and correct its answer. Returns
    (answer, remaining issues)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {
            "role": "user",
            "content": f"Retrieved context:\n\n{context}\n\nQuestion:\n\n{question_block}",
        },
    ]
    answer = ask_model(ANSWER_MODEL, messages)
    return check_and_correct(answer, context, question_block, source_text)


def answer_question(query):
    """One question, start to finish: show it, search, answer, show
    the answer and store both in the conversation.

    The chatbot's bubble appears straight away with a quiet "thinking"
    indicator, which the answer replaces when it is ready; the answer
    then fades in (CSS: .st-key-new_answer)."""
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(query)

    # Recent history, without the question just asked or extra keys
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[-6:-1]
    ]

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        waiting = st.empty()
        with waiting.container():
            render_html(THINKING_HTML)

        try:
            search_query, was_rewritten = make_search_query(query, history)
            sources = retrieve_sources(search_query)
        except Exception:
            waiting.error("Something went wrong retrieving relevant passages. Please try asking again.")
            st.stop()

        shown_query = search_query if was_rewritten else None
        context = "\n\n---\n\n".join(chunk_for_model(s) for s in sources)
        source_text = "\n".join(s["doc"] for s in sources)
        question_block = query
        if was_rewritten:
            question_block += f"\n\nInterpreted as: {search_query}"

        try:
            answer, issues = generate_answer(history, context, question_block, source_text)
        except Exception:
            waiting.error("Something went wrong generating a response. Please try again in a moment.")
            st.stop()

        waiting.empty()
        with st.container(key="new_answer"):
            render_answer(answer, sources)
            render_sources(sources, shown_query, issues)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "search_query": shown_query,
            "issues": issues,
        }
    )


# ==================================================
# 7. Display helpers
# ==================================================

# A pinpoint in an answer: [29], or a range [28]–[30], plus any
# punctuation straight after it (kept on the same line as the label)
PINPOINT_PATTERN = re.compile(r"\[(\d+)\](?:\s*[–-]\s*\[(\d+)\])?([.,;:]?)")


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
        punctuation = match.group(3)
        pinpoint = match.group(0)[: len(match.group(0)) - len(punctuation)]

        numbers = [n for n in range(first, last + 1) if n in texts]
        if not numbers:
            label = f'<span class="cite">{pinpoint}</span>'
        else:
            paragraphs = "".join(
                f'<span class="cite-paragraph"><b>[{n}]</b> {html_safe(texts[n])}</span>'
                for n in numbers
            )
            label = (
                f'<span class="cite" tabindex="0">{pinpoint}'
                f'<span class="cite-pop"><span class="cite-pop-inner">{paragraphs}</span></span>'
                f"</span>"
            )
        return f'<span class="cite-wrap">{label}{punctuation}</span>'

    render_html(PINPOINT_PATTERN.sub(to_label, answer))


def source_title(rank, source):
    """Card title: 'Match 1 · [34]–[35]', plus, in debug mode, where the
    chunk ranked in each search."""
    parts = [f"Match {rank}", source.get("paragraphs")]

    if SHOW_DEBUG:
        if source.get("chunk_rank"):
            parts.append(f"chunk search #{source['chunk_rank']}")
        if source.get("paragraph_rank"):
            via = f" via {source['matched']}" if source.get("matched") else ""
            parts.append(f"paragraph search #{source['paragraph_rank']}{via}")

    return " · ".join(p for p in parts if p)


def render_sources(sources, search_query=None, issues=None):
    """The "Sources" expander: one card per retrieved chunk, best match
    first, laid out like the judgment. Shows the rewritten search query,
    if there was one, and in debug mode any problems the answer check
    could not fix."""
    pinpoints = [s["paragraphs"] for s in sources if s.get("paragraphs")]

    with st.expander(" · ".join(["Sources"] + pinpoints)):
        if search_query:
            muted_note(f"Searched for: {html.escape(search_query)}")

        if SHOW_DEBUG:
            if issues:
                muted_note(
                    "Debug · problems left after the answer check: "
                    + html_safe(" | ".join(issues))
                )
            else:
                muted_note("Debug · answer check: no problems left.")

        for rank, source in enumerate(sources, start=1):
            # One line: Streamlit reads indented lines as a code block
            render_html(
                f'<div class="chunk-card"><div class="chunk-title">{source_title(rank, source)}</div>'
                f'{chunk_html(source.get("doc", ""))}</div>'
            )


def show_past_message(message):
    """Replay one stored message, with citation labels and sources."""
    avatar = USER_AVATAR if message["role"] == "user" else ASSISTANT_AVATAR

    with st.chat_message(message["role"], avatar=avatar):
        if message["role"] == "assistant" and message.get("sources"):
            render_answer(message["content"], message["sources"])
            render_sources(
                message["sources"],
                message.get("search_query"),
                message.get("issues"),
            )
        else:
            st.write(message["content"])


def back_to_intro_link():
    """Small link back to the introduction, under the page title."""
    with st.container(key="back_link"):
        st.page_link(HOME_PAGE, label="← Back to the introduction")


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

    for number, question in enumerate(STARTER_QUESTIONS):
        if animate:
            time.sleep(WELCOME_BUTTON_DELAY)
        if st.button(question, key=f"starter_{number}"):
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
        back_to_intro_link()
    else:
        page_header(CHATBOT_SUBTITLE)
        back_to_intro_link()
        show_welcome()

for message in st.session_state.messages:
    show_past_message(message)

if query:
    answer_question(query)