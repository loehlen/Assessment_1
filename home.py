import streamlit as st

from shared import (
    PAGE_ICON,
    aglc_pinpoint,
    apply_styles,
    case_card,
    page_header,
    paragraph_reference,
    teaser,
)

st.set_page_config(page_title="United Brands v Commission", page_icon=PAGE_ICON)
apply_styles()


# --------------------------------------------------
# Step state
# --------------------------------------------------

TOTAL_STEPS = 5
CHATBOT_PAGE = "pages/chatbot.py"

if "intro_step" not in st.session_state:
    st.session_state.intro_step = 1


def go_next():
    st.session_state.intro_step = min(st.session_state.intro_step + 1, TOTAL_STEPS)


def go_back():
    st.session_state.intro_step = max(st.session_state.intro_step - 1, 1)


step = st.session_state.intro_step


# --------------------------------------------------
# Title (shown throughout)
# --------------------------------------------------

page_header("Understanding the Relevant Product Market")

# Hook copy only shows on the very first step
if step == 1:
    st.write(
        """
        Was Chiquita's banana business operating in a market of its own —
        or just one player among many in the broader fresh fruit market?
        """
    )

st.divider()

st.markdown(
    f'<div class="step-indicator">Step {step} of {TOTAL_STEPS}</div>',
    unsafe_allow_html=True,
)

progress_col, skip_col = st.columns([5, 1])

with progress_col:
    st.progress(step / TOTAL_STEPS)

with skip_col:
    if st.button("Skip intro →", key="skip_intro", use_container_width=True):
        st.switch_page(CHATBOT_PAGE)


# --------------------------------------------------
# Step 1 — Background: about this judgment
# --------------------------------------------------

if step == 1:

    st.header("About this case")

    st.write(
        """
        Quick context before the market-definition analysis: United Brands
        Company ("UBC"), the world's largest banana group, sold bananas
        under the "Chiquita" brand. In 1975 the Commission decided that UBC
        had abused a dominant position, and UBC brought an action before
        the Court of Justice seeking annulment of that decision. Before the
        Court could rule on whether any abuse had occurred, it first had to
        determine whether UBC held a dominant position at all — which meant
        defining the relevant market first.
        """
    )

    case_card()


# --------------------------------------------------
# Step 2 — The market-definition question
# --------------------------------------------------

elif step == 2:

    st.header("The market-definition question")

    teaser(
        "So which is it — bananas as one fruit among many, "
        "or bananas as their own market?"
    )

    with st.expander("What exactly did the Court have to determine?"):

        st.write(
            """
            Did bananas form part of the broader market for fresh fruit,
            or did bananas constitute a sufficiently distinct market of
            their own?
            """
        )

        st.write(
            """
            The Court approached this question by examining whether bananas
            were reasonably interchangeable with other fresh fruit.
            """
        )

        paragraph_reference(12)


# --------------------------------------------------
# Step 3 — The opposing views
# --------------------------------------------------

elif step == 3:

    st.header("The opposing views")

    st.write(
        """
        The applicant and the Commission took different positions on whether
        bananas belonged to the same market as other fresh fruit.
        """
    )

    left, right = st.columns(2)

    with left:

        with st.expander("Applicant's argument"):

            st.write(
                """
                The applicant argued that bananas were reasonably
                interchangeable with other kinds of fresh fruit.
                """
            )

            st.write(
                """
                It pointed to the fact that bananas and other fresh fruit
                were sold in the same shops and displayed on the same shelves,
                had comparable prices, and satisfied the same consumer needs.
                """
            )

            paragraph_reference(12, 13)

    with right:

        with st.expander("Commission's response"):

            st.write(
                """
                The Commission argued that the demand for bananas was distinct
                from the demand for other fresh fruit.
                """
            )

            st.write(
                """
                It relied on the particular qualities of bananas and argued
                that the effects of other fruit on banana prices and availability
                were ineffective, brief or spasmodic.
                """
            )

            paragraph_reference(19, 21)


# --------------------------------------------------
# Step 4 — The Court's assessment
# --------------------------------------------------

elif step == 4:

    st.header("The Court's assessment")

    st.markdown(
        """
        <div class="conclusion-box">
        <strong>Conclusion:</strong> the Court held that the banana market was
        sufficiently distinct from the other fresh fruit markets.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("How did the Court reach this conclusion?")

    with st.expander("The Court's market-definition approach"):

        st.write(
            """
            The Court examined whether bananas were sufficiently interchangeable
            with other fresh fruit and whether there was a sufficiently distinct
            market for bananas.
            """
        )

        paragraph_reference(22, 27)

    with st.expander("Substitutability between bananas and other fruit"):

        st.write(
            """
            The Court examined whether other fresh fruit could exert sufficient
            competitive pressure on bananas.

            It considered seasonal substitutability and evidence concerning
            the degree of substitutability.
            """
        )

        paragraph_reference(28, 30)

    with st.expander("Characteristics of bananas and consumer choice"):

        st.write(
            """
            The Court also considered the particular characteristics of bananas,
            including their appearance, taste, softness, seedlessness and ease
            of handling, as well as a constant level of production.

            These characteristics were relevant to the Court's assessment of
            whether consumers would switch to other fresh fruit.
            """
        )

        paragraph_reference(31, 33)

    with st.expander("The Court's overall conclusion"):

        st.write(
            """
            Taking these factors together, the Court concluded that a very large
            number of consumers having a constant need for bananas were not
            noticeably or even appreciably enticed away from bananas by the
            arrival of other fresh fruit on the market.

            The banana market was therefore sufficiently distinct from the
            other fresh fruit markets.
            """
        )

        paragraph_reference(34, 35)


# --------------------------------------------------
# Step 5 — Explore the judgment
# --------------------------------------------------

elif step == 5:

    st.header("Explore the market-definition analysis")

    st.write(
        f"""
        The chatbot lets you dig deeper into any of the arguments, evidence
        or reasoning covered above — ask it to explain a step, compare the
        parties' positions, or point you to a specific paragraph in
        {aglc_pinpoint(10, 35)} of the judgment.
        """
    )

    with st.expander("Read the full introduction in one place"):

        st.markdown("**About this case**")
        case_card()

        st.markdown("**The relevant market**")
        st.write(
            f"""
            In order to determine whether a company holds a dominant position,
            the relevant market first has to be defined, from both the product
            and geographic points of view. {aglc_pinpoint(10, 11)}
            """
        )

        st.markdown("**The market-definition question**")
        st.write(
            f"""
            Did bananas form part of the broader market for fresh fruit, or
            did bananas constitute a sufficiently distinct market of their
            own? The Court approached this by examining whether bananas were
            reasonably interchangeable with other fresh fruit.
            {aglc_pinpoint(12)}
            """
        )

        st.markdown("**The opposing views**")
        st.write(
            f"""
            *Applicant:* bananas were reasonably interchangeable with other
            fresh fruit — sold in the same shops, at comparable prices,
            satisfying the same needs. {aglc_pinpoint(12, 13)}

            *Commission:* demand for bananas was distinct, given the
            particular qualities of bananas; other fruit's effect on banana
            prices and availability was ineffective, brief or spasmodic.
            {aglc_pinpoint(19, 21)}
            """
        )

        st.markdown("**The Court's assessment**")
        st.write(
            f"""
            The Court examined interchangeability and distinctness
            {aglc_pinpoint(22, 27)}, seasonal substitutability
            {aglc_pinpoint(28, 30)}, and the banana's particular
            characteristics and their effect on consumer choice
            {aglc_pinpoint(31, 33)}. It concluded that a very large number of
            consumers having a constant need for bananas were not noticeably
            or even appreciably enticed away from bananas by the arrival of
            other fresh fruit, so the banana market was sufficiently distinct
            from the other fresh fruit markets. {aglc_pinpoint(34, 35)}
            """
        )


# --------------------------------------------------
# Navigation
# --------------------------------------------------

st.write("")
nav_back, nav_spacer, nav_next = st.columns([1, 3, 1])

with nav_back:
    st.button(
        "← Back",
        on_click=go_back,
        disabled=(step == 1),
        use_container_width=True,
    )

with nav_next:
    if step < TOTAL_STEPS:
        st.button(
            "Continue →",
            on_click=go_next,
            type="primary",
            use_container_width=True,
        )
    elif st.button("Go to the chatbot →", type="primary", use_container_width=True):
        st.switch_page(CHATBOT_PAGE)