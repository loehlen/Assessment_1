"""
Shared building blocks for home.py and pages/chatbot.py.
Change something here and both pages update.

Contents
  1. Case details and page names
  2. AGLC citations
  3. Page setup, session state and navigation
  4. Small HTML helpers
  5. Colours and stylesheet
"""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# ==================================================
# 1. Case details and page names
# ==================================================

CASE_TITLE = "United Brands v Commission"
CASE_NAME = f"{CASE_TITLE} (Case 27/76)"
CASE_CITATION = "27/76, United Brands Co. v Commission (14 February 1978)"
PAGE_ICON = "⚖️"

# On-screen headings only; CASE_TITLE stays plain for the PDF and
# citations (the PDF's font can't draw emoji)
HEADING_TITLE = f"{CASE_TITLE} 🍌"

# The part of the judgment the app covers
FIRST_PARAGRAPH, LAST_PARAGRAPH = 10, 35
COVERED_PARAGRAPHS = f"paragraphs {FIRST_PARAGRAPH}–{LAST_PARAGRAPH}"

# Pages and their subtitles
HOME_PAGE = "home.py"
CHATBOT_PAGE = "pages/chatbot.py"
INTRO_SUBTITLE = "Understanding the Relevant Product Market"
CHATBOT_SUBTITLE = "Relevant Product Market Chatbot"


# ==================================================
# 2. AGLC citations
# ==================================================

EN_DASH = "\u2013"


def aglc_pinpoint(first, last=None):
    """AGLC paragraph pinpoint: [12], or [12]–[13] joined by an
    unspaced en dash."""
    if last is None or first == last:
        return f"[{first}]"
    return f"[{first}]{EN_DASH}[{last}]"


def cite(text, first, last=None):
    """A sentence followed by its AGLC pinpoint, e.g. 'text [12]'."""
    return f"{text} {aglc_pinpoint(first, last)}"


COVERED_PINPOINT = aglc_pinpoint(FIRST_PARAGRAPH, LAST_PARAGRAPH)  # [10]–[35]

EXCERPT = f'Chapter I, Section 1 — "The relevant market" {COVERED_PINPOINT}'


# ==================================================
# 3. Page setup, session state and navigation
# ==================================================

def setup_page(page_title, password_subtitle=None):
    """Call first thing on every page: browser-tab title and icon, the
    app's styles, then the password gate. Nothing below the call runs
    until the password is correct."""
    st.set_page_config(page_title=page_title, page_icon=PAGE_ICON)
    apply_styles()
    require_password(password_subtitle)


def require_password(subtitle=None):
    """Password gate shared by both pages. Once the password is
    entered on either page, the whole app is unlocked for the rest of
    the session. Nothing below the call runs until it is correct.

    The gate sits in a placeholder that is created on every run, even
    once unlocked: the empty placeholder then wipes the old password
    screen straight away, instead of leaving it faded on screen while
    the page underneath loads."""

    gate = st.empty()

    if st.session_state.get("authenticated"):
        return

    with gate.container():
        st.title(HEADING_TITLE)
        if subtitle:
            st.subheader(subtitle)
        teaser("Enter the password to get started.")

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

    st.stop()


def init_state(**defaults):
    """Give session-state keys their starting value on the first run
    only; later runs keep whatever is stored."""
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_home():
    st.switch_page(HOME_PAGE)


def go_to_chatbot(question=None):
    """Open the chatbot; if a question is given, it is asked there
    straight away (after the password, if not yet entered)."""
    if question:
        st.session_state.pending_query = question
    st.switch_page(CHATBOT_PAGE)


# ==================================================
# 4. Small HTML helpers
# ==================================================

def render_html(markup):
    st.markdown(markup, unsafe_allow_html=True)


def page_header(subtitle):
    st.title(HEADING_TITLE)
    st.subheader(subtitle)


def compact_header(subtitle):
    """One-line header for once a conversation is under way, so the
    full title and case card don't push the chat down."""
    render_html(
        f'<div class="compact-header">'
        f'<span class="compact-title">{HEADING_TITLE}</span>'
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
    render_html(
        "".join(f'<div class="teaser"{style}>{text}</div>' for text in paragraphs)
    )


def muted_note(text):
    """Small grey line, e.g. a paragraph reference or 'Searched for: …'."""
    render_html(f'<div class="paragraph-reference">{text}</div>')


def paragraph_reference(first, last=None):
    muted_note(aglc_pinpoint(first, last))


# ==================================================
# 5. Colours and stylesheet
#
# Every colour is defined once here. The stylesheet uses them as
# CSS variables (var(--accent)); home.py uses them for the PDF.
# ==================================================

PALETTE = {
    "accent": "#9B6574",         # primary buttons, labels, focus rings
    "accent-dark": "#85525F",    # accent on hover
    "tint": "#F8F0F2",           # hovered / open / highlighted backgrounds
    "nav-highlight": "#F3EAED",  # current page in the sidebar
    "border": "#EEE2E6",         # buttons and expanders
    "border-hover": "#E3D2D8",
    "card": "#FCF9FA",           # cards and the user's chat bubble
    "card-border": "#ECE5E8",
    "text": "#30313D",
    "text-soft": "#4A4A52",      # teaser lines
    "muted": "#8A7C81",          # small notes and references
}

CSS_VARIABLES = (
    ":root {\n"
    + "".join(f"    --{name}: {value};\n" for name, value in PALETTE.items())
    + "}\n"
)

STYLESHEET = """
/* Main buttons (and download buttons, styled the same) */
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

/* Pressed / just-clicked / keyboard-focused buttons keep the same
   subtle tint (some Streamlit versions use a strong pink here) */
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

/* Primary button */
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

/* Expanders (click-to-open sections): pink outline, and a light
   pink header when hovered or open, instead of Streamlit's grey */
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

/* Sidebar page links: soft highlight for the current page
   (Streamlit's default is a strong pink derived from the accent) */
a[data-testid="stSidebarNavLink"][aria-current="page"],
a[data-testid="stSidebarNavLink"]:hover {
    background-color: var(--nav-highlight) !important;
}

/* Small paragraph references and notes */
.paragraph-reference {
    color: var(--muted);
    font-size: 0.85rem;
    margin-top: 0.2rem;
}

/* Step progress indicator */
.step-indicator {
    color: var(--accent);
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
}

/* Hook / teaser line */
.teaser {
    font-size: 1.02rem;
    color: var(--text-soft);
    margin-bottom: 0.6rem;
}

/* Conclusion / court-holding box */
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

/* Intro progress bar: white with a pink outline, filling up pink */
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

/* Background/case-info card */
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

/* Chat: the user's questions in a subtle pink bubble (Streamlit
   hard-codes a grey one), and pink rings around the avatars */
div[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
    background-color: var(--card);
}

div[data-testid="stChatMessage"] > div:first-child {
    border-color: var(--border) !important;
}

/* One-line chatbot header, shown once a conversation has started */
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

/* --------------------------------------------------
   Citations in chatbot answers: a small pink label that
   opens the paragraph text on hover, or on tap (the label
   is focusable, so tapping it on a phone opens it too).
   -------------------------------------------------- */

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

/* The box sits just above the label. Its transparent bottom padding
   bridges the gap, so moving the mouse up onto it keeps it open. */
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

/* Retrieved-chunk cards inside the chatbot's "sources" expander */
.chunk-card {
    background-color: var(--card);
    border: 1px solid var(--card-border);
    border-left: 3px solid var(--accent);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.6rem;
}

.chunk-card .chunk-title {
    color: var(--accent);
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

/* Chat input submit (arrow) button keeps its own solid fill */
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

/* Justified ("Blocksatz") body text throughout the app, chat included */
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