"""
FiniteTrace - Streamlit entry point.

Run with:  python -m streamlit run app.py

The application shell provides branding, navigation, and clearly-labelled
placeholders for features that later modules will build. The regular
expression parser (core/regex_parser.py) is interactive in the Automata Builder.
"""

import streamlit as st

from core.regex_parser import (
    KIND_LABELS,
    MAX_EXPRESSION_LENGTH,
    ParsedRegex,
    RegexSyntaxError,
    describe_token,
    parse_regex,
)

APP_NAME = "FiniteTrace"
TAGLINE = "Visualize. Convert. Simulate."
SUBTITLE = "Interactive Finite Automata Visualizer & Simulator"

# Small amount of CSS, applied only to our own class names (never Streamlit internals).
CUSTOM_CSS = """
<style>
.ft-header { padding: 0.25rem 0 0.75rem 0; }
.ft-title {
    font-size: 2.6rem; font-weight: 800; letter-spacing: -0.02em; margin: 0;
    background: linear-gradient(90deg, #38bdf8, #22d3ee);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
.ft-subtitle { font-size: 1.1rem; color: #cbd5e1; margin: 0.15rem 0 0 0; }
.ft-tagline { font-size: 0.9rem; color: #22d3ee; letter-spacing: 0.08em; margin-top: 0.35rem; }
.ft-badge {
    display: inline-block; padding: 0.1rem 0.55rem; border-radius: 999px;
    border: 1px solid #334155; color: #94a3b8; font-size: 0.75rem; margin-left: 0.4rem;
}
</style>
"""


def render_header() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="ft-header">
            <p class="ft-title">{APP_NAME}</p>
            <p class="ft-subtitle">{SUBTITLE}</p>
            <p class="ft-tagline">{TAGLINE.upper()}<span class="ft-badge">Foundation build</span></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "FiniteTrace is in early development. Regular expressions can be validated and "
        "parsed today; automata generation, conversion and simulation are not available yet.",
        icon="🛠️",
    )


def coming_soon(module: str) -> None:
    st.caption(f"⏳ Coming in {module}")


def parse_and_store() -> None:
    """Button callback: parse the current input and remember the outcome (success or error)."""
    expression = st.session_state.get("regex_input", "")
    try:
        st.session_state["parse_outcome"] = (expression, parse_regex(expression))
    except RegexSyntaxError as error:
        st.session_state["parse_outcome"] = (expression, error)


def render_parse_success(parsed: ParsedRegex) -> None:
    st.success("Valid expression", icon="✅")
    alphabet = ", ".join(sorted(parsed.alphabet)) if parsed.alphabet else "∅ (no input symbols)"

    with st.container(border=True):
        first, second = st.columns(2)
        with first:
            st.markdown("**Regular expression**")
            st.code(parsed.original, language=None, wrap_lines=True)
            st.markdown("**Explicit concatenation**")
            st.code(parsed.explicit_form, language=None, wrap_lines=True)
        with second:
            st.markdown("**Alphabet Σ**")
            st.code("{" + alphabet + "}", language=None, wrap_lines=True)
            st.markdown("**Postfix expression**")
            st.code(parsed.postfix_form, language=None, wrap_lines=True)
        st.caption(
            "Postfix (reverse Polish) notation writes each operator after its operands, so the "
            "expression can be evaluated left to right with a stack and needs no parentheses. "
            "'.' is concatenation; escaped symbols such as \\| are literal characters."
        )

    st.markdown("**Postfix token sequence**")
    rows = [
        {
            "Step": step,
            "Token": token.display,
            "Type": KIND_LABELS[token.kind],
            "Meaning": describe_token(token),
        }
        for step, token in enumerate(parsed.postfix, start=1)
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def render_parse_error(expression: str, error: RegexSyntaxError) -> None:
    st.error(str(error), icon="⚠️")
    if error.position is not None:
        # Point at the offending character underneath the expression.
        st.code(expression + "\n" + " " * (error.position - 1) + "^", language=None)
    st.caption("Fix the expression above and press Validate & Parse again.")


def render_parse_outcome() -> None:
    outcome = st.session_state.get("parse_outcome")
    if outcome is None:
        return
    expression, result = outcome
    # Only show results for the text currently in the input box, never stale ones.
    if expression != st.session_state.get("regex_input", ""):
        st.caption("The expression has changed. Press Validate & Parse to check it.")
        return
    if isinstance(result, RegexSyntaxError):
        render_parse_error(expression, result)
    else:
        render_parse_success(result)


def render_builder() -> None:
    st.subheader("Automata Builder")
    st.write("Define a regular language and generate an equivalent ε-NFA or DFA.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Input method**")
            st.radio(
                "Input method",
                ["Regular expression", "Language rule", "Exact string", "Manual definition"],
                horizontal=True,
                label_visibility="collapsed",
                disabled=True,
            )
            coming_soon("Module 05 (language rules, exact strings & manual input)")
            st.text_input(
                "Regular expression",
                placeholder="(a|b)*abb",
                key="regex_input",
                help="Operators: | union, . or juxtaposition for concatenation, * + ? postfix repetition, "
                "( ) grouping, ε or λ for the empty string, \\ to escape an operator. "
                f"Maximum {MAX_EXPRESSION_LENGTH} characters.",
            )
            st.button("Validate & Parse", key="parse_button", type="primary", on_click=parse_and_store)
    with right:
        with st.container(border=True):
            st.markdown("**Generate automaton**")
            st.segmented_control("Target machine", ["ε-NFA", "DFA"], disabled=True)
            st.button("Generate automaton", disabled=True)
            coming_soon("Module 03 (NFA construction) and Module 04 (DFA conversion)")
        with st.container(border=True):
            st.markdown("**State diagram**")
            st.write("A generated diagram and its transition table will appear here.")
            coming_soon("Module 07")

    render_parse_outcome()


def render_simulator() -> None:
    st.subheader("String Simulator")
    st.write("Run a test string through a DFA or NFA and follow the active states step by step.")

    left, right = st.columns([2, 3], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Test input**")
            st.text_input("Test string", placeholder="e.g. aabb", disabled=True)
            controls = st.columns(4)
            for column, label in zip(controls, ["▶ Play", "⏸ Pause", "⏭ Step", "↺ Reset"]):
                column.button(label, disabled=True, width="stretch")
            coming_soon("Module 06 (engine) and Module 08 (animation)")
    with right:
        with st.container(border=True):
            st.markdown("**Trace**")
            st.write(
                "Active states, the transitions taken for each symbol, and the final "
                "accepted/rejected verdict will be shown here."
            )
            st.caption("No simulation has been run.")


def render_converter() -> None:
    st.subheader("NFA to DFA Converter")
    st.write("Convert an NFA into an equivalent DFA using subset construction.")

    steps = [
        ("1. Source NFA", "The NFA being converted, including any ε-transitions."),
        ("2. ε-closures", "The set of states reachable from each state using only ε-moves."),
        ("3. Subset construction", "Each new DFA state as a set of NFA states, built symbol by symbol."),
        ("4. Resulting DFA", "The converted DFA, its state mapping and transition table."),
    ]
    columns = st.columns(len(steps))
    for column, (title, description) in zip(columns, steps):
        with column.container(border=True):
            st.markdown(f"**{title}**")
            st.write(description)
    coming_soon("Module 04")


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("#### About")
        st.write(
            "FiniteTrace is an open-source tool for building, visualizing, converting "
            "and simulating finite automata (DFA and NFA)."
        )
        st.markdown("#### How it will work")
        st.markdown(
            "- **Build**: enter a regular expression, a language rule, an exact string, "
            "or a manual transition table.\n"
            "- **Convert**: turn an NFA into a DFA with subset construction, showing ε-closures.\n"
            "- **Simulate**: step through a test string and see whether it is accepted."
        )
        st.markdown("#### Status")
        st.write("Module 02 of 10 complete: regular expression parser.")


def main() -> None:
    st.set_page_config(page_title=f"{APP_NAME} - {TAGLINE}", page_icon="🔁", layout="wide")
    render_sidebar()
    render_header()

    builder_tab, simulator_tab, converter_tab = st.tabs(
        ["Automata Builder", "String Simulator", "NFA to DFA Converter"]
    )
    with builder_tab:
        render_builder()
    with simulator_tab:
        render_simulator()
    with converter_tab:
        render_converter()


main()
