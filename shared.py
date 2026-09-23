"""
Shared building blocks for home.py and pages/chatbot.py:
case details, AGLC citation formatting, the password gate, the
stylesheet and small HTML helpers. Change something here and both pages update.
"""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


# --------------------------------------------------
# Case details
# --------------------------------------------------

CASE_TITLE = "United Brands v Commission"
CASE_NAME = "United Brands v Commission (Case 27/76)"
CASE_CITATION = "27/76, United Brands Co. v Commission (14 February 1978)"
PAGE_ICON = "⚖️"


# --------------------------------------------------
# Citation style (AGLC)
# --------------------------------------------------

EN_DASH = "\u2013"


def aglc_pinpoint(first, last=None):
    """AGLC paragraph pinpoint: [12], or [12]–[13] joined by an
    unspaced en dash."""
    if last is None or first == last:
        return f"[{first}]"
    return f"[{first}]{EN_DASH}[{last}]"


EXCERPT = (
    'Chapter I, Section 1 — "The relevant market" '
    f"{aglc_pinpoint(10, 35)}"
)


# --------------------------------------------------
# Small HTML helpers
# --------------------------------------------------

def page_header(subtitle):
    st.title(CASE_TITLE)
    st.subheader(subtitle)


def case_card(excerpt_label="This excerpt"):
    st.markdown(
        f"""
        <div class="case-card">
            <div class="case-row"><span class="case-label">Case</span><span>{CASE_CITATION}</span></div>
            <div class="case-row"><span class="case-label">{excerpt_label}</span><span>{EXCERPT}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def teaser(text):
    st.markdown(f'<div class="teaser">{text}</div>', unsafe_allow_html=True)


def require_password(subtitle=None):
    """Password gate shared by both pages. Once the password is
    entered on either page, the whole app is unlocked for the rest of
    the session. Nothing below the call runs until it is correct."""

    if st.session_state.get("authenticated"):
        return

    st.title(CASE_TITLE)
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


def paragraph_reference(first, last=None):
    st.markdown(
        f'<div class="paragraph-reference">{aglc_pinpoint(first, last)}</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------
# Stylesheet
# --------------------------------------------------

CSS = """
<style>
/* Main buttons (and download buttons, styled the same) */
div.stButton > button,
div.stDownloadButton > button {
    border: 1px solid #E8CDD4;
    border-radius: 8px;
    background-color: white;
    color: #30313D;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover {
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
    border-color: #85525F;
    background-color: #85525F;
    color: white;
}

/* Expanders (click-to-open sections): pink outline, and a light
   pink header when hovered or open, instead of Streamlit's grey */
div[data-testid="stExpander"] details {
    border: 1px solid #E8CDD4 !important;
    border-radius: 8px;
}

div[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] details[open] > summary {
    background-color: #F5E6EA !important;
}

div[data-testid="stExpander"] summary [data-testid="stIconMaterial"] {
    color: #9B6574;
}

div[data-testid="stExpanderDetails"] {
    border-color: #E8CDD4 !important;
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

/* Intro progress bar: white with a pink outline, filling up pink */
.intro-progress {
    height: 12px;
    background-color: white;
    border: 1px solid #9B6574;
    border-radius: 999px;
    overflow: hidden;
    margin: 0.9rem 0;
}

.intro-progress-fill {
    height: 100%;
    background-color: #9B6574;
    border-radius: 999px;
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

/* Chat input submit (arrow) button keeps its own solid fill */
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
"""


def apply_styles():
    st.markdown(CSS, unsafe_allow_html=True)