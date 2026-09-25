"""
Intro page: a short step-by-step introduction to the case, followed
by a link to the chatbot.

The content is written once (STEPS) and used three times: the steps
themselves, the "whole introduction" summary on the last step, and the
downloadable PDF. So the PDF never contains anything the app doesn't show.

Sections
  1. Page setup
  2. Intro content (STEPS)
  3. Showing a step
  4. The guess (step 2) and the reveal (last step)
  5. PDF
  6. Page flow: sidebar, welcome screen, current step, navigation
"""

import io
from xml.sax.saxutils import escape

import streamlit as st
import streamlit.components.v1 as components
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from shared import (
    CASE_CITATION,
    CASE_TITLE,
    COVERED_PINPOINT,
    EXCERPT,
    INTRO_SUBTITLE,
    PALETTE,
    banana,
    case_card,
    cite,
    go_to_chatbot,
    init_state,
    judgment_sidebar_section,
    page_header,
    render_html,
    setup_page,
    sidebar_label,
    sidebar_nav,
    teaser,
)


# ==================================================
# 1. Page setup
# ==================================================

setup_page(CASE_TITLE)  # nothing below runs until the password is correct

PDF_FILE_NAME = "United_Brands_relevant_product_market_introduction.pdf"


# ==================================================
# 2. Intro content
#
# Each step has:
#   title    step indicator and heading
#   teaser   optional hook line (on screen only)
#   ask      optional question for the "Ask the chatbot" button
#            (left out where the chatbot can't answer, e.g. background)
#   blocks   the content, in order
#
# Block types:
#   background    uncited context, the case card and a note
#   text          a short paragraph
#   box           highlighted box: label, text and optional bullets
#   label         a small bold heading
#   points        bullet points, each (bold lead, text)
#   details       click-to-open section: label, then "paragraphs"
#                 and/or "bullets"
#   side_by_side  two click-to-open sections next to each other
#
# Like the chatbot's answers, every sentence reporting the judgment
# names its source and ends with a pinpoint.
# ==================================================

STEPS = [

    # Step 1: background (outside [10]–[35], so no Ask button)
    {
        "title": "A little background",
        "teaser": "First, who was involved and how did the case reach the Court?",
        "blocks": [
            {
                "type": "background",
                "text": (
                    "The Commission decided that United Brands Company (UBC), "
                    "which sold bananas under the “Chiquita” brand, had "
                    "abused a dominant position. UBC asked the European "
                    "Court of Justice to annul that decision."
                ),
                "note": (
                    f"Background from outside {COVERED_PINPOINT}; "
                    "the chatbot does not cover it."
                ),
            },
        ],
    },

    # Step 2: [10], [12]
    {
        "title": "The market-definition question",
        "blocks": [
            {
                "type": "text",
                "text": cite(
                    "To decide whether UBC held a dominant position, the "
                    "Court first had to define the market, by product and "
                    "by geography.",
                    10,
                ),
            },
            {
                "type": "details",
                "label": "The two possibilities",
                "paragraphs": [
                    cite(
                        "A. One fresh fruit market: bananas are reasonably "
                        "interchangeable with other fresh fruit, as the "
                        "applicant maintained.",
                        12,
                    ),
                    cite(
                        "B. A separate banana market, sufficiently "
                        "homogeneous and distinct from other fresh fruit.",
                        12,
                    ),
                ],
            },
        ],
        "ask": "What did the Court say about how the relevant market must be defined?",
    },

    # Step 3: [13]–[17], [19]–[21]
    # The conclusions ([18] and the Commission's) are in the headings
    {
        "title": "The parties' positions",
        "blocks": [
            {
                "type": "side_by_side",
                "items": [
                    {
                        "label": "The applicant: one fresh fruit market",
                        "bullets": [
                            cite(
                                "Bananas compete with other fresh fruit: "
                                "same shops, same shelves, comparable prices, "
                                "eaten as a dessert or between meals.",
                                13,
                            ),
                            cite(
                                "It relied on statistics and FAO studies "
                                "showing that banana spending and prices are "
                                "lower when other fresh fruit is plentiful.",
                                14, 17,
                            ),
                        ],
                    },
                    {
                        "label": "The Commission: a distinct banana market",
                        "bullets": [
                            cite(
                                "Demand for bananas is distinct, especially "
                                "as they are a very important part of the "
                                "diet of certain sections of the community.",
                                19,
                            ),
                            cite(
                                "The banana's specific qualities induce "
                                "customers not to readily accept other fruit "
                                "as a substitute.",
                                20,
                            ),
                            cite(
                                "The studies the applicant quoted show only "
                                "a very weak, brief and spasmodic influence "
                                "of other fruit on banana prices and "
                                "availability.",
                                21,
                            ),
                        ],
                    },
                ],
            },
        ],
        "ask": (
            "How did the Commission respond to the applicant's argument "
            "that bananas and other fresh fruit form one market?"
        ),
    },

    # Step 4: [22]
    {
        "title": "The Court's test",
        "teaser": "What would make bananas a market of their own?",
        "blocks": [
            {
                "type": "box",
                "label": "The test",
                "text": (
                    "Bananas form a market of their own only if special "
                    "features set them apart from other fruit, so that:"
                ),
                "bullets": [
                    "other fruit can replace them only to a limited extent, and",
                    cite("competition from other fruit is hardly perceptible.", 22),
                ],
            },
        ],
        "ask": (
            "What special features did the Court rely on to distinguish "
            "bananas from other fruit?"
        ),
    },

    # Step 5: [27]–[29], [31], [34]–[35]
    # On screen, hidden until the reveal button is clicked; the summary
    # and the PDF always show it.
    {
        "title": "The Court's answer",
        "teaser": "Did bananas pass the test?",
        "blocks": [
            {
                "type": "box",
                "label": "Conclusion",
                "text": (
                    cite(
                        "A very large number of consumers with a constant "
                        "need for bananas are not noticeably or even "
                        "appreciably enticed away by other fresh fruit.",
                        34,
                    )
                    + " "
                    + cite(
                        "The banana market is sufficiently distinct from "
                        "the other fresh fruit markets.",
                        35,
                    )
                ),
            },
            {"type": "label", "text": "Why the Court decided this"},
            {
                "type": "points",
                "items": [
                    (
                        "All year round:",
                        cite(
                            "bananas are always available in sufficient "
                            "quantities, so substitutability is assessed "
                            "over the whole year, not season by season.",
                            27,
                        ),
                    ),
                    (
                        "Little substitution:",
                        cite(
                            "the studies on the Court's file show seasonal "
                            "substitutability only with peaches and table "
                            "grapes, in West Germany. Oranges are not "
                            "interchangeable with bananas, and apples only "
                            "to a relative degree.",
                            28, 29,
                        ),
                    ),
                    (
                        "Special features:",
                        cite(
                            "appearance, taste, softness, seedlessness, easy "
                            "handling and a constant level of production "
                            "enable bananas to satisfy the constant needs of "
                            "the very young, the old and the sick.",
                            31,
                        ),
                    ),
                ],
            },
        ],
        "ask": (
            "Why did the Court assess substitutability over the whole year "
            "rather than season by season?"
        ),
    },
]

TOTAL_STEPS = len(STEPS)

# The guess on step 2, answered on the last step
GUESS_STEP = 2
GUESS_OPTIONS = ["A. The fresh fruit market", "B. A separate banana market"]
CORRECT_GUESS = GUESS_OPTIONS[1]


# ==================================================
# 3. Showing a step
#
# compact=True is the version inside the summary expander: no teaser,
# and click-to-open sections shown open (Streamlit doesn't allow
# expanders inside expanders).
# ==================================================

def bullet_list(items):
    return "\n".join(f"- {item}" for item in items)


def render_details(item, compact):
    def body():
        for paragraph in item.get("paragraphs", []):
            st.write(paragraph)
        if item.get("bullets"):
            st.markdown(bullet_list(item["bullets"]))

    if compact:
        st.markdown(f"*{item['label']}*")
        body()
    else:
        with st.expander(item["label"]):
            body()


def render_box(block):
    bullets = ""
    if block.get("bullets"):
        bullets = (
            '<ul style="margin: 0.4rem 0 0 0;">'
            + "".join(f"<li>{bullet}</li>" for bullet in block["bullets"])
            + "</ul>"
        )
    render_html(
        f'<div class="conclusion-box"><strong>{block["label"]}:</strong> '
        f"{block['text']}{bullets}</div>"
    )


def render_block(block, compact=False):
    kind = block["type"]

    if kind == "background":
        st.write(block["text"])
        case_card()
        st.caption(block["note"])
    elif kind == "text":
        st.write(block["text"])
    elif kind == "box":
        render_box(block)
    elif kind == "label":
        st.markdown(f"**{block['text']}**")
    elif kind == "points":
        st.markdown(bullet_list(f"**{lead}** {text}" for lead, text in block["items"]))
    elif kind == "details":
        render_details(block, compact)
    elif kind == "side_by_side":
        columns = st.columns(len(block["items"]))
        for column, item in zip(columns, block["items"]):
            with column:
                render_details(item, compact)


def render_step(step_data, compact=False):
    if not compact and step_data.get("teaser"):
        teaser(step_data["teaser"])
    for block in step_data["blocks"]:
        render_block(block, compact)


def progress_bar(fraction):
    """Pink-outlined bar that fills up step by step (replaces
    st.progress, whose colours can't be set reliably)."""
    render_html(
        '<div class="intro-progress">'
        f'<div class="intro-progress-fill" style="width: {fraction:.0%};"></div>'
        "</div>"
    )


def ask_button(step_data):
    if not step_data.get("ask"):
        return
    st.write("")
    st.caption(f"Want to dig deeper? Try: “{step_data['ask']}”")
    if st.button("Ask the chatbot about this →", key="ask_step"):
        go_to_chatbot(step_data["ask"])


# ==================================================
# 4. The guess (step 2) and the reveal (last step)
#
# The guess is saved under its own key, because Streamlit forgets a
# widget's value once the widget is off screen.
# ==================================================

GUESS_NOTE = "Noted. The last step reveals the answer."


def save_guess():
    st.session_state.market_guess = st.session_state.guess_widget
    st.session_state.answer_revealed = False


def guess_question():
    """The guess, with a note that fades in once a choice is made.

    The radio is always drawn with the same settings (index=None), so
    Streamlit keeps recognising it: a changing index would make it look
    like a new widget and redraw it on every choice. A saved guess is
    put back through its key when the user returns to this step.

    The note is always there, but invisible until a guess is made, so
    its space is reserved and nothing below it jumps when it appears.
    It fades in with the soft-fade-in animation from the stylesheet."""
    st.markdown("**What do you think?** Which market did the Court find?")

    saved = st.session_state.market_guess
    if saved and st.session_state.get("guess_widget") is None:
        st.session_state.guess_widget = saved

    st.radio(
        "Your guess",
        GUESS_OPTIONS,
        index=None,
        key="guess_widget",
        on_change=save_guess,
        label_visibility="collapsed",
    )

    if st.session_state.market_guess:
        note_style = "animation: soft-fade-in 0.3s ease-out;"
    else:
        note_style = "visibility: hidden;"
    render_html(
        f'<div class="teaser" style="text-align: left; {note_style}">{GUESS_NOTE}</div>'
    )


def reveal_answer():
    st.session_state.answer_revealed = True
    st.session_state.celebrate = st.session_state.market_guess == CORRECT_GUESS


def reveal_section():
    """The guess and the reveal button. Returns True once revealed."""
    guess = st.session_state.market_guess

    if guess:
        teaser(f"You guessed: <em>{guess[3:].lower()}</em>.")

    if st.session_state.answer_revealed:
        return True

    label = "Find out if you were right →" if guess else "Reveal the Court's answer →"
    st.button(label, on_click=reveal_answer, type="primary", key="reveal")
    return False


def reveal_verdict():
    """Whether the guess was right (nothing if there was no guess)."""
    guess = st.session_state.market_guess

    if guess == CORRECT_GUESS:
        teaser(f'{banana("inline-icon")}<strong>Correct! Bananas are a market of their own.</strong>')
    elif guess:
        teaser("<strong>Not quite. The Court went the other way.</strong>")


def celebrate_if_due():
    """Balloons once, straight after a correct reveal."""
    if st.session_state.celebrate:
        st.balloons()
        st.session_state.celebrate = False


# ==================================================
# 5. PDF, built from the same STEPS content
# ==================================================

PDF_ACCENT = colors.HexColor(PALETTE["accent"])
PDF_TINT = colors.HexColor(PALETTE["tint"])
PDF_CARD = colors.HexColor(PALETTE["card"])
PDF_BORDER = colors.HexColor(PALETTE["card-border"])
PDF_TEXT = colors.HexColor(PALETTE["text"])
PDF_MUTED = colors.HexColor(PALETTE["muted"])


def pdf_style(name, size, leading, colour=PDF_TEXT, bold=False, **extra):
    font = "Helvetica-Bold" if bold else "Helvetica"
    return ParagraphStyle(
        name, fontName=font, fontSize=size, leading=leading, textColor=colour, **extra
    )


PDF_STYLES = {
    "title": pdf_style("title", 20, 24, bold=True, spaceAfter=4),
    "subtitle": pdf_style("subtitle", 13, 17, PDF_ACCENT, spaceAfter=14),
    "heading": pdf_style(
        "heading", 13.5, 17, PDF_ACCENT, bold=True,
        spaceBefore=14, spaceAfter=6, keepWithNext=1,
    ),
    "label": pdf_style(
        "label", 10.5, 14, bold=True, spaceBefore=4, spaceAfter=3, keepWithNext=1,
    ),
    "body": pdf_style("body", 10.5, 15, alignment=TA_JUSTIFY, spaceAfter=6),
    "note": pdf_style("note", 8.5, 11.5, PDF_MUTED, spaceAfter=6),
}


def pdf_text(text, style="body"):
    return Paragraph(escape(text), PDF_STYLES[style])


def pdf_panel(flowables, background, left_border=None):
    """A shaded box around some flowables."""
    table = Table([[flowables]], colWidths=["100%"])
    commands = [
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.6, PDF_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if left_border:
        commands.append(("LINEBEFORE", (0, 0), (0, -1), 3, left_border))
    table.setStyle(TableStyle(commands))
    return KeepTogether([table, Spacer(1, 7)])


def pdf_bullets(paragraphs):
    return ListFlowable(
        [ListItem(paragraph, leftIndent=12) for paragraph in paragraphs],
        bulletType="bullet",
        bulletColor=PDF_ACCENT,
        bulletFontSize=9,
        leftIndent=12,
    )


def pdf_details(item):
    flowables = [pdf_text(item["label"], "label")]
    flowables += [pdf_text(paragraph) for paragraph in item.get("paragraphs", [])]
    if item.get("bullets"):
        flowables.append(pdf_bullets([pdf_text(b) for b in item["bullets"]]))
    return pdf_panel(flowables, PDF_CARD)


def pdf_case_card():
    rows = [
        [pdf_text("Case", "label"), pdf_text(CASE_CITATION)],
        [pdf_text("This excerpt", "label"), pdf_text(EXCERPT)],
    ]
    table = Table(rows, colWidths=[28 * mm, None])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return pdf_panel([table], PDF_CARD)


def pdf_box(block):
    flowables = [Paragraph(
        f'<font color="{PALETTE["accent"]}"><b>{escape(block["label"])}:</b>'
        f"</font> {escape(block['text'])}",
        PDF_STYLES["body"],
    )]
    if block.get("bullets"):
        flowables.append(pdf_bullets([pdf_text(b) for b in block["bullets"]]))
    return pdf_panel(flowables, PDF_TINT, left_border=PDF_ACCENT)


def pdf_block(block):
    """One content block as a list of PDF flowables."""
    kind = block["type"]

    if kind == "background":
        return [pdf_text(block["text"]), pdf_case_card(), pdf_text(block["note"], "note")]
    if kind == "text":
        return [pdf_text(block["text"])]
    if kind == "box":
        return [pdf_box(block)]
    if kind == "label":
        return [pdf_text(block["text"], "label")]
    if kind == "points":
        return [pdf_bullets([
            Paragraph(f"<b>{escape(lead)}</b> {escape(text)}", PDF_STYLES["body"])
            for lead, text in block["items"]
        ])]
    if kind == "details":
        return [pdf_details(block)]
    if kind == "side_by_side":
        return [pdf_details(item) for item in block["items"]]
    return []


def pdf_footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(PDF_MUTED)
    canvas.drawString(document.leftMargin, 12 * mm, f"{CASE_TITLE} — {INTRO_SUBTITLE}")
    canvas.drawRightString(A4[0] - document.rightMargin, 12 * mm, f"Page {document.page}")
    canvas.restoreState()


@st.cache_data
def build_intro_pdf(steps):
    """The full introduction as PDF bytes. Cached; rebuilt whenever
    STEPS changes."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title=f"{CASE_TITLE} — {INTRO_SUBTITLE}",
        author=CASE_TITLE,
    )

    story = [
        pdf_text(CASE_TITLE, "title"),
        pdf_text(f"{INTRO_SUBTITLE}: introduction", "subtitle"),
    ]
    for number, step_data in enumerate(steps, start=1):
        story.append(pdf_text(f"{number}. {step_data['title']}", "heading"))
        for block in step_data["blocks"]:
            story.extend(pdf_block(block))

    document.build(story, onFirstPage=pdf_footer, onLaterPages=pdf_footer)
    return buffer.getvalue()


def pdf_download_button(key):
    st.download_button(
        "Download the introduction (PDF)",
        data=build_intro_pdf(STEPS),
        file_name=PDF_FILE_NAME,
        mime="application/pdf",
        key=key,
        use_container_width=True,
    )


# ==================================================
# 6. Page flow
#
# The main area has three fixed slots, in the same place on every
# screen: the title, the progress area (empty on the welcome screen)
# and the stage (the step's content and the navigation buttons).
#
# When the step changes, Streamlit swaps the new step's pieces into
# the stage one by one, so for a split second parts of the old step
# are still there. The step's container fades in from invisible at
# exactly that moment (step_container), so the swap happens unseen
# and the new step appears as a whole.
#
# The page scrolls to the top the moment a navigation button is
# clicked, before Streamlit redraws, so a tall step (such as step 2)
# doesn't leave the next one half-scrolled.
# ==================================================

# Step 0 is the welcome screen; steps 1 to TOTAL_STEPS are the intro
init_state(intro_step=0, market_guess=None, answer_revealed=False, celebrate=False)

# Buttons that change the step (their keys are set in show_welcome and
# show_navigation); clicking one scrolls the page to the top
NAVIGATION_BUTTONS = ".st-key-start_intro, .st-key-nav_next, .st-key-nav_back"

# Scrolling to the top. Streamlit has no built-in way to do this, so a
# tiny invisible frame adds a small script to the page, once:
#   - it scrolls to the top as soon as a navigation button is clicked,
#     before Streamlit redraws
#   - it provides introScrollToTop(), which the frame also calls when
#     the page opens (e.g. when arriving from the chatbot page)
# The script is added to the page itself rather than kept in the
# frame, so it keeps working whatever happens to the frame. The page
# scrolls in a different element depending on the Streamlit version,
# so all the likely ones are tried. If the page doesn't accept the
# added script, the frame scrolls the page itself.
SCROLL_SCRIPT = """
<script>
const page = window.parent.document;

const helperCode = `
    window.introScrollToTop = function () {
        const scrollers = [
            '[data-testid="stMain"]',
            "section.main",
            '[data-testid="stAppViewContainer"]',
        ];
        for (const selector of scrollers) {
            const element = document.querySelector(selector);
            if (element) element.scrollTo({ top: 0, behavior: "instant" });
        }
        window.scrollTo({ top: 0, behavior: "instant" });
    };
    document.addEventListener("click", function (event) {
        if (event.target.closest("NAVIGATION_BUTTONS")) {
            window.introScrollToTop();
        }
    }, true);
`;

if (!page.getElementById("intro-scroll-helper")) {
    const helper = page.createElement("script");
    helper.id = "intro-scroll-helper";
    helper.textContent = helperCode;
    page.head.appendChild(helper);
}

if (window.parent.introScrollToTop) {
    window.parent.introScrollToTop();
} else {
    for (const selector of ['[data-testid="stMain"]', "section.main",
                            '[data-testid="stAppViewContainer"]']) {
        const element = page.querySelector(selector);
        if (element) element.scrollTo({ top: 0, behavior: "instant" });
    }
    window.parent.scrollTo({ top: 0, behavior: "instant" });
}
</script>
""".replace("NAVIGATION_BUTTONS", NAVIGATION_BUTTONS)


def install_scroll_helper():
    """The invisible frame that adds the scroll script (see
    SCROLL_SCRIPT). It sits at the bottom of the sidebar, which looks
    the same on every screen of this page, so the frame loads once when
    the page opens and isn't rebuilt on every click."""
    with st.sidebar:
        components.html(SCROLL_SCRIPT, height=0)


def go_to_step(target):
    """Navigation callback. Goes to a given step rather than "one
    further", so a double click on Continue can't skip a step."""
    st.session_state.intro_step = min(max(target, 0), TOTAL_STEPS)


def step_container(stage, step):
    """The container for one step's content (step 0 is the welcome),
    inside the stage. It fades in from invisible when the step changes
    (CSS: st-key-stepa_ and st-key-stepb_), which hides the moment in
    which Streamlit swaps the old step's pieces for the new ones.
    Neighbouring steps take turns between "a" and "b", so the animation
    changes with every step and the fade replays even though Streamlit
    reuses the container. Within a step the key stays the same, so
    clicking a guess, the reveal or an expander doesn't replay it."""
    parity = "a" if step % 2 else "b"
    return stage.container(key=f"step{parity}_{step}")


def show_sidebar():
    """Page links, the PDF download and the judgment pop-up, with the
    invisible scroll helper at the very bottom."""
    sidebar_nav()

    sidebar_label("The introduction")
    with st.sidebar:
        pdf_download_button(key="pdf_sidebar")
        st.caption("The whole introduction in one document, with paragraph citations.")

    judgment_sidebar_section()
    install_scroll_helper()


def show_welcome():
    teaser(
        "Welcome! This chatbot covers an absolute classic of European "
        "competition law: how the European Court of Justice decided "
        "whether bananas form a market of their own.",
        "Before we get into the chatbot, let's first explore what the "
        "case is about.",
        align_left=True,
    )
    st.caption(f"{TOTAL_STEPS} short steps · about 3 minutes")

    st.write("")
    # Skip on the left, the main action on the right
    skip_col, _, start_col = st.columns([1.2, 1.6, 1.6])
    with skip_col:
        if st.button("Skip to the chatbot", key="skip_welcome", use_container_width=True):
            go_to_chatbot()
    with start_col:
        st.button(
            "Let's explore the case →",
            key="start_intro",
            on_click=go_to_step,
            args=(1,),
            type="primary",
            use_container_width=True,
        )


def show_progress(step, current):
    """Step indicator and progress bar, with a skip button until the
    last step. The skip button's column stays on the last step (empty),
    so the bar keeps its width and just fills up."""
    st.divider()
    render_html(
        f'<div class="step-indicator">Step {step} of {TOTAL_STEPS} · {current["title"]}</div>'
    )

    progress_col, skip_col = st.columns([5, 1])
    with progress_col:
        progress_bar(step / TOTAL_STEPS)
    if step < TOTAL_STEPS:
        with skip_col:
            if st.button("Skip intro →", key="skip_intro", use_container_width=True):
                go_to_chatbot()


def show_current_step(step, current):
    """The step's content. On the last step, the Court's answer, the
    Ask button and the summary stay hidden until revealed, then fade in
    together (CSS: st-key-revealed)."""
    st.header(current["title"])

    if step < TOTAL_STEPS:
        render_step(current)
        if step == GUESS_STEP:
            st.write("")
            guess_question()
        ask_button(current)
        return

    if current.get("teaser"):
        teaser(current["teaser"])
    if not reveal_section():
        return

    with st.container(key="revealed"):
        reveal_verdict()
        for block in current["blocks"]:
            render_block(block)
        celebrate_if_due()
        ask_button(current)
        show_summary_and_pdf()


def show_summary_and_pdf():
    """Last step: the whole introduction in one place, and the PDF."""
    st.divider()

    with st.expander("Read the whole introduction in one place"):
        for number, step_data in enumerate(STEPS, start=1):
            st.markdown(f"#### {number}. {step_data['title']}")
            render_step(step_data, compact=True)

    pdf_download_button(key="pdf_final")

    st.write("")
    teaser(
        "Ready to dig deeper? The chatbot answers questions on the full "
        f"reasoning in {COVERED_PINPOINT}."
    )


def show_navigation(step):
    st.write("")
    nav_back, _, nav_next = st.columns([1, 2, 1.4])

    with nav_back:
        st.button(
            "← Back",
            key="nav_back",
            on_click=go_to_step,
            args=(step - 1,),
            use_container_width=True,
        )

    with nav_next:
        if step < TOTAL_STEPS:
            st.button(
                "Continue →",
                key="nav_next",
                on_click=go_to_step,
                args=(step + 1,),
                type="primary",
                use_container_width=True,
            )
        elif st.button(
            "Go to the chatbot →",
            key="nav_chatbot",
            type="primary",
            use_container_width=True,
        ):
            go_to_chatbot()


# Clamp, in case the number of steps changed during a session
step = min(max(st.session_state.intro_step, 0), TOTAL_STEPS)
st.session_state.intro_step = step

show_sidebar()

# The three slots (see the note at the top of this section)
page_header(INTRO_SUBTITLE)
progress_area = st.container()
stage = st.container()

if step == 0:
    with step_container(stage, 0):
        show_welcome()
    st.stop()  # nothing below runs on the welcome screen

current = STEPS[step - 1]

with progress_area:
    show_progress(step, current)

with step_container(stage, step):
    show_current_step(step, current)
    show_navigation(step)