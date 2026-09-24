"""
Shared building blocks for home.py and pages/chatbot.py.
Change something here and both pages update.

Contents
  1. Case details and page names
  2. The banana icon
  3. AGLC citations
  4. Page setup, session state and navigation
  5. Small HTML helpers
  6. The judgment text (pop-up and source cards)
  7. Sidebar
  8. Colours and stylesheet
"""

import base64
import html
import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ==================================================
# 1. Case details and page names
# ==================================================

CASE_TITLE = "United Brands v Commission"
CASE_NAME = f"{CASE_TITLE} (Case 27/76)"
CASE_CITATION = "27/76, United Brands Co. v Commission (14 February 1978)"

# The part of the judgment the app covers
FIRST_PARAGRAPH, LAST_PARAGRAPH = 10, 35
COVERED_PARAGRAPHS = f"paragraphs {FIRST_PARAGRAPH}–{LAST_PARAGRAPH}"

# Pages and their sidebar names. Streamlit's automatic page list is
# switched off in .streamlit/config.toml; sidebar_nav() replaces it.
HOME_PAGE = "home.py"
CHATBOT_PAGE = "pages/chatbot.py"
HOME_PAGE_NAME = "Introduction"
CHATBOT_PAGE_NAME = "Chatbot"
INTRO_SUBTITLE = "Understanding the Relevant Product Market"
CHATBOT_SUBTITLE = "Relevant Product Market Chatbot"

# The judgment: the chunk files (read by both the vector store and the
# judgment pop-up, so they always match), the original pages as a PDF,
# and the full judgment on EUR-Lex
CHUNKS_FOLDER = "Chunks - United Brands v Commission - Relevant Product Market"
JUDGMENT_PDF = "United_Brands_judgment_paras_10-35.pdf"
JUDGMENT_PDF_DOWNLOAD_NAME = "United_Brands_v_Commission_paras_10-35.pdf"
EUR_LEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:61976CJ0027"


# ==================================================
# 2. The banana icon
#
# One line-drawn banana in the accent pink: next to every page title
# (BANANA_SVG), as the browser-tab icon and as the chatbot's avatar
# (the PNGs). A missing PNG falls back to an emoji.
# ==================================================

BANANA_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#9B6574" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<path d="M17.2 6.2 C 19.6 13.6 13.4 20.6 4.2 18.4 C 3.4 18.2 3.3 17.2 '
    '4.1 16.9 C 10.6 15.3 15 11.4 15.4 6.4 Z" fill="#F3E3E8"/>'
    '<path d="M15.4 6.4 L 17.2 6.2 L 16.9 3.6 L 15.7 3.8 Z" fill="#9B6574"/>'
    '<path d="M8.6 16.4 C 12 15.2 14.6 12.8 16.1 9.8" stroke-width="1" '
    'opacity="0.5"/>'
    "</svg>"
)
BANANA_SRC = "data:image/svg+xml;base64," + base64.b64encode(BANANA_SVG.encode()).decode()


def image_or(path, fallback):
    """The image file if it's in the repo, otherwise the fallback."""
    return path if Path(path).exists() else fallback


PAGE_ICON = image_or("banana_icon.png", "⚖️")
ASSISTANT_AVATAR = image_or("banana_avatar.png", "⚖️")


def banana(size_class="title-icon"):
    """The banana as an inline image, for use inside HTML."""
    return f'<img class="{size_class}" src="{BANANA_SRC}" alt="">'


# ==================================================
# 3. AGLC citations
# ==================================================

def aglc_pinpoint(first, last=None):
    """[12], or a range [12]–[13] joined by an unspaced en dash."""
    if last is None or first == last:
        return f"[{first}]"
    return f"[{first}]–[{last}]"


def cite(text, first, last=None):
    """A sentence followed by its pinpoint, e.g. 'text [12]'."""
    return f"{text} {aglc_pinpoint(first, last)}"


COVERED_PINPOINT = aglc_pinpoint(FIRST_PARAGRAPH, LAST_PARAGRAPH)  # [10]–[35]
EXCERPT = f'Chapter I, Section 1 — "The relevant market" {COVERED_PINPOINT}'


# ==================================================
# 4. Page setup, session state and navigation
# ==================================================

def setup_page(page_title, password_subtitle=None):
    """Call first on every page: tab title and icon, styles, then the
    password gate. Nothing below the call runs until it is passed."""
    st.set_page_config(page_title=page_title, page_icon=PAGE_ICON)
    apply_styles()
    require_password(password_subtitle)


def require_password(subtitle=None):
    """Password gate for both pages: entering it once unlocks the whole
    app for the session.

    The placeholder is created on every run, even once unlocked, so the
    old password screen is wiped at once instead of lingering faded."""
    gate = st.empty()

    if st.session_state.get("authenticated"):
        return

    with gate.container():
        app_title()
        if subtitle:
            app_subtitle(subtitle)
        teaser("Enter the password to get started.")

        password = st.text_input(
            label="Password", type="password", placeholder="Enter password"
        )
        if password:
            if password == os.environ["PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    st.stop()


def init_state(**defaults):
    """Set session-state defaults on the first run only."""
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to_chatbot(question=None):
    """Open the chatbot; a given question is asked there straight away."""
    if question:
        st.session_state.pending_query = question
    st.switch_page(CHATBOT_PAGE)


# ==================================================
# 5. Small HTML helpers
# ==================================================

def render_html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def html_safe(text):
    """Escape HTML characters, plus those Streamlit would read as
    italics, bold, code or maths."""
    text = html.escape(text)
    for char, entity in (("*", "&#42;"), ("_", "&#95;"), ("$", "&#36;"), ("`", "&#96;")):
        text = text.replace(char, entity)
    return text


def app_title():
    """The case name with the banana (st.title can't show an image)."""
    render_html(f'<h1 class="app-title">{CASE_TITLE}{banana()}</h1>')


def app_subtitle(text):
    """Smaller pink line under the title (replaces st.subheader)."""
    render_html(f'<div class="app-subtitle">{text}</div>')


def page_header(subtitle):
    app_title()
    app_subtitle(subtitle)


def compact_header(subtitle):
    """One-line header once a conversation is under way."""
    render_html(
        f'<div class="compact-header">'
        f'<span class="compact-title">{CASE_TITLE}{banana("compact-icon")}</span>'
        f'<span class="compact-subtitle">{subtitle} · {COVERED_PINPOINT}</span>'
        f"</div>"
    )


def case_card(excerpt_label="This excerpt"):
    render_html(
        f"""
        <div class="case-card">
            <div class="case-row"><span class="case-label">Case</span><span>{CASE_CITATION}</span></div>
            <div class="case-row"><span class="case-label">{excerpt_label}</span><span>{EXCERPT}</span></div>
        </div>
        """
    )


def teaser(*paragraphs, align_left=False):
    """One or more hook lines. align_left=True suits short lines,
    where justified text leaves wide gaps."""
    style = ' style="text-align: left;"' if align_left else ""
    render_html("".join(f'<div class="teaser"{style}>{text}</div>' for text in paragraphs))


def muted_note(text):
    """Small grey line, e.g. 'Searched for: …'."""
    render_html(f'<div class="paragraph-reference">{text}</div>')


# ==================================================
# 6. The judgment text
#
# Every chunk file holds paragraphs that each start with "[n]". The
# helpers below split them up and lay them out like the report, for the
# judgment pop-up and the chatbot's source cards.
# ==================================================

CHAPTER_HEADING = "Chapter I — The existence of a dominant position"
SECTION_HEADING = "Section 1 — The relevant market"

# Subheadings between paragraphs, keyed by the paragraph they precede.
# The pop-up adds them itself, so any copy inside a chunk file is removed.
JUDGMENT_SUBHEADINGS = {
    12: "Paragraph 1. The Product Market",
}

PARAGRAPH_MARKER = re.compile(r"\[(\d+)\]")


def one_line(text):
    """Collapse all whitespace (line breaks included) to single spaces."""
    return " ".join(text.split())


def split_paragraphs(text):
    """Split text at its [n] markers. Returns the text before the first
    marker, and a list of (number, paragraph text) pairs."""
    parts = PARAGRAPH_MARKER.split(text)
    # parts = [text before the first marker, "10", text, "11", text, ...]
    return parts[0], list(zip(parts[1::2], parts[2::2]))


def subheading_pattern(heading):
    """Matches a subheading whatever its spacing, case or full stops."""
    words = [re.escape(word.rstrip(".")) + r"\.?" for word in heading.split()]
    return re.compile(r"\s*".join(words), re.IGNORECASE)


SUBHEADING_PATTERNS = [subheading_pattern(h) for h in JUDGMENT_SUBHEADINGS.values()]


@st.cache_data(show_spinner=False)
def load_judgment_paragraphs():
    """{paragraph number: text} from all chunk files, in order."""
    folder = Path(CHUNKS_FOLDER)
    paragraphs = {}

    if not folder.exists():
        return paragraphs

    for file in sorted(folder.glob("*.txt")):
        _, pairs = split_paragraphs(file.read_text(encoding="utf-8", errors="ignore"))
        for number, body in pairs:
            for pattern in SUBHEADING_PATTERNS:
                body = pattern.sub(" ", body)
            paragraphs[int(number)] = one_line(body)

    return dict(sorted(paragraphs.items()))


@st.cache_data(show_spinner=False)
def load_judgment_pdf():
    """The original pages as bytes, or None if the file is missing."""
    path = Path(JUDGMENT_PDF)
    return path.read_bytes() if path.exists() else None


def heading_html(heading):
    """Chapter headings bold, section headings italic, anything else
    as a pink subheading."""
    text = html_safe(heading)
    if heading.lower().startswith("chapter"):
        return f'<div class="judgment-heading">{text}</div>'
    if heading.lower().startswith("section"):
        return f'<div class="judgment-subheading"><em>{text}</em></div>'
    return f'<div class="judgment-subheading">{text}</div>'


def paragraph_row(number, text):
    """One paragraph with its number in the margin."""
    return (
        f'<div class="judgment-paragraph">'
        f'<span class="judgment-number">{number}</span>'
        f'<span class="judgment-text">{html_safe(text)}</span>'
        f"</div>"
    )


# The HTML is joined into one line: Streamlit would read indented
# lines inside markdown as a code block.

def judgment_html(paragraphs):
    """The whole covered text, for the pop-up."""
    rows = [heading_html(CHAPTER_HEADING), heading_html(SECTION_HEADING)]
    for number, text in paragraphs.items():
        if number in JUDGMENT_SUBHEADINGS:
            rows.append(heading_html(JUDGMENT_SUBHEADINGS[number]))
        rows.append(paragraph_row(number, text))
    return '<div class="judgment">' + "".join(rows) + "</div>"


def chunk_html(doc):
    """One chunk file, for a source card: its headings (the lines
    before the first [n]), then its paragraphs."""
    before, pairs = split_paragraphs(doc)
    rows = [heading_html(one_line(line)) for line in before.splitlines() if line.strip()]
    rows += [paragraph_row(number, one_line(body)) for number, body in pairs]
    return '<div class="judgment chunk-text">' + "".join(rows) + "</div>"


@st.dialog(f"{CASE_TITLE} · {COVERED_PINPOINT}", width="large")
def show_judgment():
    """The pop-up. Closing it returns to the page exactly as it was."""
    st.caption(CASE_CITATION)

    paragraphs = load_judgment_paragraphs()
    if paragraphs:
        render_html(judgment_html(paragraphs))
    else:
        st.warning(f'The judgment text could not be found in "{CHUNKS_FOLDER}".')

    st.divider()

    pdf = load_judgment_pdf()
    if pdf:
        st.download_button(
            "Download the original pages (PDF)",
            data=pdf,
            file_name=JUDGMENT_PDF_DOWNLOAD_NAME,
            mime="application/pdf",
            key="judgment_pdf",
            use_container_width=True,
        )
        st.caption(f"The judgment as reported, pages 270–273, {COVERED_PINPOINT}.")
    else:
        st.caption("The original pages (PDF) are not available at the moment.")

    render_html(
        f'<a class="judgment-link" href="{EUR_LEX_URL}" target="_blank">'
        f"Read the full judgment on EUR-Lex ↗</a>"
    )
    st.caption(f"The chatbot covers {COVERED_PINPOINT} only, not the rest of the judgment.")


# ==================================================
# 7. Sidebar (same layout on both pages: page links, then sections
# with a pink label, a full-width button and a caption)
# ==================================================

def sidebar_nav():
    """Links to both pages under their proper names."""
    with st.sidebar:
        st.page_link(HOME_PAGE, label=HOME_PAGE_NAME)
        st.page_link(CHATBOT_PAGE, label=CHATBOT_PAGE_NAME)


def sidebar_label(text):
    """Small uppercase pink label above a sidebar section."""
    st.sidebar.markdown(f'<div class="sidebar-label">{text}</div>', unsafe_allow_html=True)


def judgment_sidebar_section():
    """Opens the judgment pop-up."""
    sidebar_label("The judgment")
    if st.sidebar.button("Read the judgment", key="open_judgment", use_container_width=True):
        show_judgment()
    st.sidebar.caption(f"The text of {COVERED_PINPOINT}, with the original pages to download.")


# ==================================================
# 8. Colours and stylesheet
#
# Every colour is defined once here. The stylesheet uses them as CSS
# variables (var(--accent)); home.py uses them for the PDF.
# ==================================================

PALETTE = {
    "accent": "#9B6574",         # primary buttons, labels, focus rings
    "accent-dark": "#85525F",    # accent on hover
    "tint": "#F8F0F2",           # hovered / open / highlighted backgrounds
    "nav-highlight": "#F3EAED",  # current page in the sidebar
    "border": "#EEE2E6",         # buttons and expanders
    "border-hover": "#E3D2D8",
    "card": "#FCF9FA",           # cards
    "card-border": "#ECE5E8",
    "text": "#30313D",
    "text-soft": "#4A4A52",      # teaser lines
    "muted": "#8A7C81",          # small notes and references
    "backdrop": "#F8F0F2B3",     # veil behind the pop-up (B3 = 70% opacity)
}

# Recolours Streamlit's balloons into shades of the accent mauve:
# grey first, then a warm tone rotated round to pink
BALLOON_FILTER = "grayscale(1) sepia(1) hue-rotate(295deg) saturate(0.8) brightness(1.02)"

CSS_VARIABLES = (
    ":root {\n"
    + "".join(f"    --{name}: {value};\n" for name, value in PALETTE.items())
    + f"    --balloon-filter: {BALLOON_FILTER};\n"
    + "}\n"
)

STYLESHEET = """
/* ---------- Title with the banana ---------- */

h1.app-title {
    padding-top: 0;
    padding-bottom: 0.2rem;
}

.app-subtitle {
    color: var(--accent);
    font-size: 1.2rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    margin: 0 0 1.4rem 0;
}

.title-icon {
    height: 0.85em;
    width: auto;
    margin-left: 0.3em;
    vertical-align: -0.04em;
}

.compact-icon {
    height: 1em;
    width: auto;
    margin-left: 0.3em;
    vertical-align: -0.12em;
}

.inline-icon {
    height: 1.15em;
    width: auto;
    margin-right: 0.3em;
    vertical-align: -0.2em;
}

/* ---------- Buttons (download buttons styled the same) ---------- */

div.stButton button,
div.stDownloadButton button {
    border: 1px solid var(--border);
    border-radius: 8px;
    background-color: white;
    color: var(--text);
}

div.stButton button:hover,
div.stDownloadButton button:hover {
    border-color: var(--border-hover);
    background-color: var(--tint);
    color: var(--text);
}

/* Pressed / focused buttons keep the subtle tint */
div.stButton button:not([kind="primary"]):active,
div.stButton button:not([kind="primary"]):focus,
div.stButton button:not([kind="primary"]):focus-visible,
div.stDownloadButton button:active,
div.stDownloadButton button:focus,
div.stDownloadButton button:focus-visible {
    border-color: var(--border-hover) !important;
    background-color: var(--tint) !important;
    color: var(--text) !important;
    box-shadow: none !important;
    outline: none !important;
}

div.stButton button:not([kind="primary"]):focus:not(:hover):not(:active),
div.stDownloadButton button:focus:not(:hover):not(:active) {
    background-color: white !important;
    border-color: var(--border) !important;
}

div.stButton button[kind="primary"] {
    border: 1px solid var(--accent);
    background-color: var(--accent);
    color: white;
}

div.stButton button[kind="primary"]:hover {
    border-color: var(--accent-dark);
    background-color: var(--accent-dark);
    color: white;
}

/* ---------- Expanders: pink outline and light pink header ---------- */

div[data-testid="stExpander"] details {
    border: 1px solid var(--border) !important;
    border-radius: 8px;
}

div[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] details[open] > summary {
    background-color: var(--tint) !important;
}

div[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    color: var(--accent);
}

div[data-testid="stExpanderDetails"] {
    border-color: var(--border) !important;
}

/* ---------- Sidebar ---------- */

a[data-testid="stPageLink-NavLink"] {
    border-radius: 8px;
}

a[data-testid="stPageLink-NavLink"]:hover,
a[data-testid="stPageLink-NavLink"][aria-current="page"] {
    background-color: var(--nav-highlight) !important;
}

a[data-testid="stPageLink-NavLink"][aria-current="page"] p {
    font-weight: 600;
}

.sidebar-label {
    color: var(--accent);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 1.4rem 0 0.1rem 0;
}

/* ---------- Intro page ---------- */

.paragraph-reference {
    color: var(--muted);
    font-size: 0.85rem;
    margin-top: 0.2rem;
}

.step-indicator {
    color: var(--accent);
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}

.teaser {
    font-size: 1.02rem;
    color: var(--text-soft);
    margin-bottom: 0.6rem;
}

.conclusion-box {
    background-color: var(--tint);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 8px;
    padding: 1rem 1.2rem;
    color: var(--text);
    margin: 1rem 0;
}

.conclusion-box strong {
    color: var(--accent);
}

/* Progress bar: white with a pink outline, filling up pink */
.intro-progress {
    height: 12px;
    background-color: white;
    border: 1px solid var(--accent);
    border-radius: 999px;
    overflow: hidden;
    margin: 0.9rem 0;
}

.intro-progress-fill {
    height: 100%;
    background-color: var(--accent);
    border-radius: 999px;
}

.case-card {
    background-color: var(--card);
    border: 1px solid var(--card-border);
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
    color: var(--accent);
    font-weight: 600;
    min-width: 110px;
}

/* Balloons after a correct guess, recoloured mauve */
div[data-testid="stBalloons"],
div.stBalloons {
    filter: var(--balloon-filter);
    opacity: 0.9;
}

/* ---------- Chat layout ----------
   The user's questions: right-aligned pink bubbles, no avatar.
   The chatbot's answers: plain text with the banana avatar. */

div[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
    width: fit-content;
    max-width: 85%;
    margin-left: auto;
    padding: 0.55rem 1rem;
    background-color: var(--tint);
    border: 1px solid var(--border);
    border-radius: 16px 16px 4px 16px;
}

div[data-testid="stChatMessage"]:has([aria-label="Chat message from user"])
    [data-testid^="stChatMessageAvatar"] {
    display: none;
}

/* Short chat text (questions, welcome) left-aligned, not justified */
div[data-testid="stChatMessage"]:has([aria-label="Chat message from user"])
    [data-testid="stMarkdownContainer"] p,
.st-key-welcome [data-testid="stMarkdownContainer"] p {
    text-align: left;
}

div[data-testid="stChatMessage"]:not(:has([aria-label="Chat message from user"])) {
    background-color: transparent;
    padding-left: 0;
    padding-right: 0;
}

/* Starter questions as small pink "chips" */
div[class*="st-key-starter_"] button {
    min-height: 0;
    padding: 0.3rem 0.95rem;
    border: 1px solid var(--border-hover);
    border-radius: 999px;
    background-color: white;
    color: var(--accent);
    font-size: 0.9rem;
}

div[class*="st-key-starter_"] button p {
    font-size: 0.9rem;
    text-align: left;
}

div[class*="st-key-starter_"] button:hover {
    background-color: var(--tint);
    border-color: var(--accent);
    color: var(--accent-dark);
}

/* Sources under an answer: a quiet footnote */
div[data-testid="stChatMessage"] div[data-testid="stExpander"] details {
    border-color: var(--card-border) !important;
}

div[data-testid="stChatMessage"] div[data-testid="stExpander"] summary p {
    color: var(--muted);
    font-size: 0.85rem;
}

.compact-header {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.3rem 0.8rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 1rem;
}

.compact-header .compact-title {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text);
}

.compact-header .compact-subtitle {
    font-size: 0.95rem;
    color: var(--accent);
    font-weight: 600;
}

/* ---------- Citation labels in answers ----------
   Show the paragraph text on hover, or on tap (the label is
   focusable). The box's transparent bottom padding bridges the gap,
   so moving the mouse onto it keeps it open. */

.cite {
    position: relative;
    display: inline-block;
    padding: 0 0.3rem;
    border-radius: 5px;
    background-color: var(--tint);
    color: var(--accent);
    font-size: 0.88em;
    font-weight: 600;
    line-height: 1.5;
    text-indent: 0;
    cursor: pointer;
    outline: none;
}

.cite:hover,
.cite:focus {
    background-color: var(--accent);
    color: white;
}

.cite-pop {
    display: none;
    position: absolute;
    left: 0;
    bottom: 100%;
    z-index: 1000;
    width: min(440px, 75vw);
    padding-bottom: 6px;
    cursor: auto;
}

.cite:hover .cite-pop,
.cite:focus .cite-pop,
.cite:focus-within .cite-pop {
    display: block;
}

.cite-pop-inner {
    display: block;
    max-height: 280px;
    overflow-y: auto;
    padding: 0.7rem 0.9rem;
    background-color: white;
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(48, 49, 61, 0.14);
    color: var(--text);
    font-size: 0.85rem;
    font-weight: 400;
    line-height: 1.55;
    text-align: justify;
    text-justify: inter-word;
    white-space: normal;
}

.cite-pop-inner .cite-speaker {
    display: block;
    color: var(--muted);
    font-size: 0.78rem;
    margin-bottom: 0.2rem;
}

.cite-pop-inner .cite-paragraph {
    display: block;
}

.cite-pop-inner .cite-paragraph + .cite-paragraph {
    margin-top: 0.6rem;
}

.cite-pop-inner b {
    color: var(--accent);
}

/* ---------- Source cards in the "Sources" expander ---------- */

.chunk-card {
    background-color: var(--card);
    border: 1px solid var(--card-border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    padding: 0.8rem 1.1rem 0.3rem 1.1rem;
    margin-bottom: 0.8rem;
}

.chunk-card .chunk-title {
    color: var(--accent);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
}

.chunk-card .chunk-text {
    font-size: 0.9rem;
}

.chunk-card .judgment-heading,
.chunk-card .judgment-subheading {
    margin: 0 0 0.5rem 0;
}

.chunk-card .judgment-heading {
    font-size: 0.95rem;
}

/* ---------- Judgment text, laid out like the report ---------- */

.judgment {
    color: var(--text);
    line-height: 1.6;
}

.judgment-heading {
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 0.3rem;
}

.judgment-subheading {
    color: var(--accent);
    font-weight: 600;
    margin: 0.9rem 0 0.6rem 0;
}

.judgment-paragraph {
    display: flex;
    gap: 0.9rem;
    margin-bottom: 0.8rem;
}

.judgment-number {
    flex: 0 0 1.8rem;
    color: var(--accent);
    font-weight: 600;
    font-size: 0.9rem;
    padding-top: 0.1rem;
}

.judgment-text {
    text-align: justify;
    text-justify: inter-word;
}

a.judgment-link {
    color: var(--accent);
    font-weight: 600;
    text-decoration: none;
}

a.judgment-link:hover {
    color: var(--accent-dark);
    text-decoration: underline;
}

/* Backdrop behind the pop-up: the soft veil from PALETTE instead of
   Streamlit's strong tint ("background", because Streamlit uses the
   shorthand) */
div[data-testid="stDialog"] {
    background: var(--backdrop) !important;
}

/* ---------- Chat input and password field ----------
   Exactly one pink ring, drawn by the outer container only; every
   element inside has no border, shadow or outline of its own. */

div[data-testid="stChatInput"],
div[data-testid="stTextInput"] > div {
    border-color: var(--card-border) !important;
    box-shadow: none !important;
}

div[data-testid="stChatInput"]:hover,
div[data-testid="stChatInput"]:focus-within,
div[data-testid="stTextInput"] > div:hover,
div[data-testid="stTextInput"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 1px var(--accent) !important;
}

div[data-testid="stChatInput"] *,
div[data-testid="stTextInput"] * {
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
}

div[data-testid="stChatInput"] textarea,
div[data-testid="stTextInput"] input {
    caret-color: var(--accent) !important;
}

/* The send (arrow) button keeps its solid fill */
div[data-testid="stChatInput"] button {
    background-color: var(--accent) !important;
    border-color: var(--accent) !important;
    color: white !important;
}

div[data-testid="stChatInput"] button:hover,
div[data-testid="stChatInput"] button:focus,
div[data-testid="stChatInput"] button:active {
    background-color: var(--accent-dark) !important;
    border-color: var(--accent-dark) !important;
    color: white !important;
}

div[data-testid="stChatInput"] button svg {
    fill: white !important;
    color: white !important;
}

/* Justified body text throughout the app */
[data-testid="stMarkdownContainer"] p,
.case-card,
.teaser,
.conclusion-box {
    text-align: justify;
    text-justify: inter-word;
}
"""

CSS = f"\n<style>\n{CSS_VARIABLES}{STYLESHEET}</style>\n"


def apply_styles():
    render_html(CSS)