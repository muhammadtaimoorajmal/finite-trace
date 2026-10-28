"""
FiniteTrace - Streamlit entry point.

Run with:  python -m streamlit run app.py

The application shell provides branding, navigation, and clearly-labelled
placeholders for features that later modules will build. In the Automata
Builder, regular expressions can be parsed (core/regex_parser.py) and turned
into ε-NFAs with Thompson's construction (core/thompson.py).
"""

import streamlit as st

from core.automata import display_symbol, state_sort_key
from core.regex_parser import (
    KIND_LABELS,
    MAX_EXPRESSION_LENGTH,
    ParsedRegex,
    RegexSyntaxError,
    describe_token,
    parse_regex,
)
from core.thompson import ConstructionError, ConstructionResult, construct_nfa

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
        "FiniteTrace is in early development. Regular expressions can be parsed and turned "
        "into ε-NFAs today; DFA conversion, diagrams and simulation are not available yet.",
        icon="🛠️",
    )


def coming_soon(module: str) -> None:
    st.caption(f"⏳ Coming in {module}")


# The builder shows the result of the most recent action only. It is stored in
# session state as (action, expression, result-or-error) so it survives reruns.
PARSE_ACTION = "parse"
NFA_ACTION = "nfa"


def parse_and_store() -> None:
    """Button callback: parse the current input and remember the outcome (success or error)."""
    expression = st.session_state.get("regex_input", "")
    try:
        result = parse_regex(expression)
    except RegexSyntaxError as error:
        result = error
    st.session_state["builder_outcome"] = (PARSE_ACTION, expression, result)


def generate_nfa_and_store() -> None:
    """Button callback: parse and run Thompson's construction on the current input."""
    expression = st.session_state.get("regex_input", "")
    try:
        result = construct_nfa(parse_regex(expression))
    except (RegexSyntaxError, ConstructionError) as error:
        result = error
    st.session_state["builder_outcome"] = (NFA_ACTION, expression, result)


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


def render_nfa_success(expression: str, result: ConstructionResult) -> None:
    nfa = result.automaton
    transitions = nfa.transition_list()
    epsilon_count = sum(1 for _, symbol, _ in transitions if symbol is None)
    accepting = ", ".join(sorted(nfa.accepting_states, key=state_sort_key))
    alphabet = ", ".join(sorted(nfa.alphabet)) if nfa.alphabet else "∅ (no input symbols)"

    st.success(f"ε-NFA generated with {len(nfa.states)} states and {len(transitions)} transitions.", icon="✅")

    st.markdown("#### NFA summary")
    with st.container(border=True):
        first, second, third = st.columns(3)
        first.metric("States", len(nfa.states))
        second.metric("Transitions", len(transitions))
        third.metric("ε-transitions", epsilon_count)
        left, right = st.columns(2)
        with left:
            st.markdown("**Regular expression**")
            st.code(expression, language=None, wrap_lines=True)
            st.markdown("**Initial state**")
            st.code(nfa.initial_state, language=None)
        with right:
            st.markdown("**Alphabet Σ**")
            st.code("{" + alphabet + "}", language=None, wrap_lines=True)
            st.markdown("**Accepting state**")
            st.code(accepting, language=None)
        st.markdown("**States**")
        st.code("{" + ", ".join(nfa.sorted_states()) + "}", language=None, wrap_lines=True)

    st.markdown("#### Transitions")
    st.caption("One row per arrow. ε marks an epsilon transition, which moves without reading input.")
    rows = [
        {"Source": source, "Symbol": display_symbol(symbol), "Destination": destination}
        for source, symbol, destination in transitions
    ]
    st.dataframe(rows, hide_index=True, width="stretch")

    st.markdown("#### Construction steps")
    st.caption(
        "Thompson's construction reads the postfix expression left to right. Each symbol "
        "pushes a small fragment; each operator pops its operands and pushes a combined fragment."
    )
    step_rows = [
        {
            "Step": step.number,
            "Token": step.token,
            "Operation": step.operation,
            "Fragment": f"{step.fragment.start} → {step.fragment.end}",
            "Stack": step.stack_depth,
            "Explanation": step.explanation,
        }
        for step in result.steps
    ]
    st.dataframe(step_rows, hide_index=True, width="stretch")
    st.caption("A state diagram for this NFA arrives in Module 07; DFA conversion in Module 04.")


def render_builder_error(expression: str, error: ValueError, button: str) -> None:
    st.error(str(error), icon="⚠️")
    position = getattr(error, "position", None)
    if position is not None:
        # Point at the offending character underneath the expression.
        st.code(expression + "\n" + " " * (position - 1) + "^", language=None)
    st.caption(f"Fix the expression above and press {button} again.")


def render_builder_outcome() -> None:
    outcome = st.session_state.get("builder_outcome")
    if outcome is None:
        return
    action, expression, result = outcome
    # Only show results for the text currently in the input box, never stale ones.
    if expression != st.session_state.get("regex_input", ""):
        st.caption("The expression has changed. Press Validate & Parse or Generate ε-NFA to update the result.")
        return
    button = "Validate & Parse" if action == PARSE_ACTION else "Generate ε-NFA"
    if isinstance(result, ValueError):
        render_builder_error(expression, result, button)
    elif action == PARSE_ACTION:
        render_parse_success(result)
    else:
        render_nfa_success(expression, result)


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
            st.button("Validate & Parse", key="parse_button", on_click=parse_and_store)
    with right:
        with st.container(border=True):
            st.markdown("**Generate automaton**")
            st.button(
                "Generate ε-NFA",
                key="generate_nfa_button",
                type="primary",
                on_click=generate_nfa_and_store,
                help="Parse the expression and build an equivalent ε-NFA with Thompson's construction.",
            )
            st.button("Generate DFA", disabled=True)
            coming_soon("Module 04 (DFA conversion)")
        with st.container(border=True):
            st.markdown("**State diagram**")
            st.write("A graphical state diagram will appear here.")
            coming_soon("Module 07")

    render_builder_outcome()


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
        st.write("Module 03 of 10 complete: ε-NFA construction (Thompson's algorithm).")


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
