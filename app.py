"""
FiniteTrace - Streamlit entry point.

Run with:  python -m streamlit run app.py

The application shell provides branding, navigation, and clearly-labelled
placeholders for features that later modules will build. In the Automata
Builder, regular expressions can be parsed (core/regex_parser.py), turned
into ε-NFAs with Thompson's construction (core/thompson.py) and converted to
DFAs with subset construction (core/converter.py), which the NFA to DFA
Converter tab shows step by step.
"""

import streamlit as st

from core.automata import FiniteAutomaton, display_symbol, state_sort_key
from core.converter import ConversionError, ConversionResult, convert_nfa_to_dfa, format_subset
from core.regex_parser import (
    KIND_LABELS,
    MAX_EXPRESSION_LENGTH,
    ParsedRegex,
    RegexSyntaxError,
    describe_token,
    parse_regex,
)
from core.thompson import ConstructionError, ConstructionResult, construct_nfa
from ui.automaton_view import format_alphabet, render_automaton, state_label
from ui.builder_modes import (
    available_builder_automata,
    current_manual_automaton,
    manual_signature,
    render_exact_mode,
    render_language_mode,
    render_manual_mode,
)
from ui.simulator_view import render_simulator_tab
from ui.visualizer import render_automaton_diagram, render_layout_control

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
            <div class="ft-title">{APP_NAME}</div>
            <div class="ft-subtitle">{SUBTITLE}</div>
            <div class="ft-tagline">{TAGLINE.upper()}<span class="ft-badge">In development · 7 of 10 modules</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info(
        "Build automata from regular expressions, language rules, exact strings or manual "
        "definitions, see their state diagrams, convert NFAs to DFAs, and simulate test strings "
        "with a full trace. Animated simulation is not available yet.",
        icon="🛠️",
    )


# The builder shows the result of the most recent action only. It is stored in
# session state as (action, expression, result-or-error) so it survives reruns.
PARSE_ACTION = "parse"
NFA_ACTION = "nfa"
DFA_ACTION = "dfa"
BUTTON_LABELS = {PARSE_ACTION: "Validate & Parse", NFA_ACTION: "Generate ε-NFA", DFA_ACTION: "Generate DFA"}
PIPELINE_ERRORS = (RegexSyntaxError, ConstructionError, ConversionError)
BUILDER_MODES = ["Regular Expression", "Language Rule", "Exact String", "Manual Automaton"]
CONVERTER_SOURCES = ["From Regular Expression", "From Manual NFA"]


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
    except PIPELINE_ERRORS as error:
        result = error
    st.session_state["builder_outcome"] = (NFA_ACTION, expression, result)


def run_conversion_pipeline(expression: str) -> tuple[ConstructionResult, ConversionResult]:
    """Parse -> Thompson ε-NFA -> subset construction. Raises one of PIPELINE_ERRORS."""
    construction = construct_nfa(parse_regex(expression))
    return construction, convert_nfa_to_dfa(construction.automaton)


def generate_dfa_and_store() -> None:
    """Button callback: run the full pipeline on the Builder input."""
    expression = st.session_state.get("regex_input", "")
    try:
        _, result = run_conversion_pipeline(expression)
    except PIPELINE_ERRORS as error:
        result = error
    st.session_state["builder_outcome"] = (DFA_ACTION, expression, result)


def convert_and_store() -> None:
    """Button callback for the Converter tab, which keeps its own input and result."""
    expression = st.session_state.get("converter_input", "")
    try:
        result = run_conversion_pipeline(expression)
    except PIPELINE_ERRORS as error:
        result = error
    st.session_state["converter_outcome"] = (expression, result)


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
    st.success(
        f"ε-NFA generated with {len(nfa.states)} states and {len(nfa.transition_list())} transitions.",
        icon="✅",
    )
    render_automaton_diagram(nfa, key="builder_nfa", title="State diagram")
    render_nfa_overview(expression, nfa)
    render_construction_steps(result)
    st.caption("Use Generate DFA to convert this ε-NFA, or the NFA to DFA Converter to see each step.")


def render_nfa_overview(expression: str, nfa: FiniteAutomaton) -> None:
    """Summary metrics, key states and the full transition table of an NFA."""
    transitions = nfa.transition_list()
    epsilon_count = sum(1 for _, symbol, _ in transitions if symbol is None)
    accepting = ", ".join(sorted(nfa.accepting_states, key=state_sort_key))
    alphabet = format_alphabet(nfa)

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
            st.code(alphabet, language=None, wrap_lines=True)
            st.markdown("**Accepting state**")
            st.code(accepting, language=None)
        st.markdown("**States**")
        st.code("{" + ", ".join(nfa.sorted_states()) + "}", language=None, wrap_lines=True)

    st.markdown("#### NFA transitions")
    st.caption("One row per arrow. ε marks an epsilon transition, which moves without reading input.")
    rows = [
        {"Source": source, "Symbol": display_symbol(symbol), "Destination": destination}
        for source, symbol, destination in transitions
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def render_construction_steps(result: ConstructionResult) -> None:
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


def state_role(conversion: ConversionResult, state: str) -> str:
    dfa = conversion.dfa
    roles = []
    if state == dfa.initial_state:
        roles.append("Initial")
    if state in dfa.accepting_states:
        roles.append("Accepting")
    if state == conversion.dead_state:
        roles.append("Dead (empty subset)")
    return ", ".join(roles) or "—"


def render_dfa_summary(source_label: str, source: str, conversion: ConversionResult) -> None:
    dfa = conversion.dfa
    st.markdown("#### DFA summary")
    with st.container(border=True):
        first, second, third, fourth = st.columns(4)
        first.metric("DFA states", len(dfa.states))
        second.metric("Transitions", len(dfa.transition_list()))
        third.metric("Accepting", len(dfa.accepting_states))
        fourth.metric("Dead state", conversion.dead_state or "None")
        left, right = st.columns(2)
        with left:
            st.markdown(f"**{source_label}**")
            st.code(source, language=None, wrap_lines=True)
            st.markdown("**Initial state**")
            st.code(dfa.initial_state, language=None)
        with right:
            st.markdown("**Alphabet Σ**")
            st.code(format_alphabet(dfa), language=None, wrap_lines=True)
            st.markdown("**Accepting states**")
            accepting = ", ".join(sorted(dfa.accepting_states, key=state_sort_key))
            st.code(accepting or "none (the DFA accepts no strings)", language=None, wrap_lines=True)
        st.caption(
            f"{len(conversion.state_mapping)} reachable subsets of NFA states were discovered. "
            "The DFA is equivalent to the NFA by construction but is not minimized."
        )


def render_state_mapping(conversion: ConversionResult) -> None:
    st.markdown("#### DFA states as sets of NFA states")
    rows = [
        {"DFA state": state_label(conversion.dfa, name), "NFA states": format_subset(subset),
         "Type": state_role(conversion, name)}
        for name, subset in conversion.state_mapping.items()
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


def render_dfa_transition_table(conversion: ConversionResult) -> None:
    dfa = conversion.dfa
    st.markdown("#### DFA transition table")
    if not dfa.alphabet:
        st.info(
            "The alphabet is empty, so the DFA has no transitions. It accepts the empty string "
            "if and only if its initial state is accepting.",
            icon="ℹ️",
        )
        return
    st.caption("→ marks the initial state and ★ accepting states. Each cell is the single next state.")
    symbols = sorted(dfa.alphabet)
    rows = []
    for state in dfa.sorted_states():
        row = {"State": state_label(dfa, state)}
        for symbol in symbols:
            (row[symbol],) = dfa.transitions[(state, symbol)]
        rows.append(row)
    st.dataframe(rows, hide_index=True, width="stretch")


def render_dfa_success(expression: str, conversion: ConversionResult) -> None:
    dfa = conversion.dfa
    st.success(
        f"DFA generated with {len(dfa.states)} states. Structural validation passed: "
        "every state has exactly one transition per symbol.",
        icon="✅",
    )
    render_automaton_diagram(dfa, key="builder_dfa", title="State diagram")
    render_dfa_summary("Regular expression", expression, conversion)
    render_state_mapping(conversion)
    render_dfa_transition_table(conversion)
    st.caption("See the NFA to DFA Converter tab for the step-by-step subset construction.")


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
        st.caption("The expression has changed. Press a button above to update the result.")
        return
    if isinstance(result, ValueError):
        render_builder_error(expression, result, BUTTON_LABELS[action])
    elif action == PARSE_ACTION:
        render_parse_success(result)
    elif action == NFA_ACTION:
        render_nfa_success(expression, result)
    else:
        render_dfa_success(expression, result)


def render_builder() -> None:
    st.subheader("Automata Builder")
    st.write("Define a regular language or an automaton, then inspect the resulting ε-NFA or DFA.")
    # Tabs keep every mode's inputs rendered, so switching modes never loses them.
    regex_tab, rule_tab, exact_tab, manual_tab = st.tabs(BUILDER_MODES)
    with regex_tab:
        render_regex_mode()
    with rule_tab:
        render_language_mode()
    with exact_tab:
        render_exact_mode()
    with manual_tab:
        render_manual_mode()


def render_regex_mode() -> None:
    left, right = st.columns([3, 2], gap="large")
    with left:
        with st.container(border=True):
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
            st.button(
                "Generate DFA",
                key="generate_dfa_button",
                on_click=generate_dfa_and_store,
                help="Build the ε-NFA, then convert it to an equivalent DFA with subset construction.",
            )
        st.caption("Generated automata are shown below with their state diagram, summary and transition table.")

    render_builder_outcome()


def regex_builder_automata() -> list[tuple[str, FiniteAutomaton]]:
    """The Builder's regex ε-NFA or DFA, if it still matches the expression in the input box."""
    outcome = st.session_state.get("builder_outcome")
    if outcome is None:
        return []
    action, expression, result = outcome
    if expression != st.session_state.get("regex_input", "") or isinstance(result, ValueError):
        return []
    if action == NFA_ACTION:
        return [(f"Regular Expression → ε-NFA: {expression}", result.automaton)]
    if action == DFA_ACTION:
        return [(f"Regular Expression → DFA: {expression}", result.dfa)]
    return []


def converted_dfas() -> list[tuple[str, FiniteAutomaton]]:
    """DFAs from the NFA to DFA Converter whose inputs are unchanged."""
    found = []
    outcome = st.session_state.get("converter_outcome")
    if outcome and outcome[0] == st.session_state.get("converter_input", "") and not isinstance(outcome[1], ValueError):
        found.append((f"Converted from regular expression {outcome[0]}", outcome[1][1].dfa))
    status, nfa = current_manual_automaton()
    outcome = st.session_state.get("converter_manual_outcome")
    if (status == "ok" and outcome and outcome[0] == manual_signature()
            and not isinstance(outcome[1], ValueError)):
        found.append(("Converted from manual NFA", outcome[1][1].dfa))
    return found


def render_simulator() -> None:
    st.subheader("String Simulator")
    render_simulator_tab(regex_builder_automata() + available_builder_automata(), converted_dfas())


def render_subset_construction(conversion: ConversionResult) -> None:
    st.markdown("#### Initial ε-closure")
    st.code(
        f"D0 = ε-closure({{{conversion.nfa_initial_state}}}) = {format_subset(conversion.initial_closure)}",
        language=None,
        wrap_lines=True,
    )
    render_state_mapping(conversion)

    st.markdown("#### Conversion steps")
    st.caption(
        "For each DFA state S and symbol x: move(S, x) follows x-transitions only, then "
        "ε-closure adds every state reachable by ε. The result is the next DFA state; "
        "a subset seen for the first time becomes a new state, and ∅ is the dead state."
    )
    if not conversion.steps:
        st.info("The alphabet is empty, so there are no symbol transitions to compute. D0 is the only DFA state.", icon="ℹ️")
        return
    rows = []
    for step in conversion.steps:
        if not step.is_new_state:
            outcome = "existing"
        elif step.destination_dfa_state == conversion.dead_state:
            outcome = "new (dead state)"
        else:
            outcome = "new"
        rows.append({
            "Step": step.number,
            "From": step.source_dfa_state,
            "Symbol": step.input_symbol,
            "move(S, x)": format_subset(step.move_result),
            "ε-closure": format_subset(step.epsilon_closure_result),
            "To": step.destination_dfa_state,
            "Result": outcome,
        })
    st.dataframe(rows, hide_index=True, width="stretch")
    with st.expander("How subset construction works"):
        st.markdown(
            "1. **Start:** D0 is the ε-closure of the NFA's initial state.\n"
            "2. **Explore:** take the next unprocessed DFA state S (breadth-first) and, for each "
            "symbol x in sorted order, compute ε-closure(move(S, x)).\n"
            "3. **Name:** if that subset is new, give it the next name (D1, D2, …) and queue it; "
            "otherwise reuse its existing name.\n"
            "4. **Accept:** a DFA state is accepting if its subset contains any accepting NFA state.\n"
            "5. **Dead state:** the empty subset ∅ is non-accepting and loops to itself on every symbol."
        )


def render_conversion_outcome() -> None:
    outcome = st.session_state.get("converter_outcome")
    if outcome is None:
        return
    expression, result = outcome
    if expression != st.session_state.get("converter_input", ""):
        st.caption("The expression has changed. Press Convert NFA to DFA to update the result.")
        return
    if isinstance(result, ValueError):
        render_builder_error(expression, result, "Convert NFA to DFA")
        return

    construction, conversion = result
    st.success(
        f"Converted a {len(construction.automaton.states)}-state ε-NFA into a "
        f"{len(conversion.dfa.states)}-state DFA. Structural validation passed.",
        icon="✅",
    )
    with st.container(border=True):
        st.markdown("### A. Original ε-NFA")
        render_automaton_diagram(construction.automaton, key="converter_nfa", title="ε-NFA diagram")
        render_nfa_overview(expression, construction.automaton)
    with st.container(border=True):
        st.markdown("### B. Subset construction")
        render_subset_construction(conversion)
    with st.container(border=True):
        st.markdown("### C. Converted DFA")
        render_automaton_diagram(conversion.dfa, key="converter_dfa", title="DFA diagram")
        st.caption("Each DFA state stands for the set of NFA states listed in section B.")
        render_dfa_summary("Regular expression", expression, conversion)
        render_dfa_transition_table(conversion)


def convert_manual_and_store() -> None:
    """Button callback: convert the validated manual NFA saved by the Automata Builder."""
    status, nfa = current_manual_automaton()
    if status != "ok" or nfa.machine_type != "NFA":
        return  # the button is disabled in this case; nothing to convert
    try:
        result = (nfa, convert_nfa_to_dfa(nfa))
    except ConversionError as error:
        result = error
    st.session_state["converter_manual_outcome"] = (manual_signature(), result)


def render_manual_conversion() -> None:
    status, nfa = current_manual_automaton()
    messages = {
        "none": "No manual automaton yet. In the Automata Builder, open Manual Automaton, "
                "choose NFA, enter its transitions and press Validate & Build.",
        "stale": "The manual automaton's inputs changed after it was built. Press Validate & Build "
                 "in the Automata Builder again before converting.",
        "error": "The current manual automaton is invalid. Fix the error shown in the Automata Builder first.",
    }
    ready = status == "ok" and nfa.machine_type == "NFA"
    with st.container(border=True):
        if status in messages:
            st.info(messages[status], icon="ℹ️")
        elif not ready:
            st.info("The manual automaton is a DFA. It is already deterministic, so there is nothing to convert. "
                    "Choose NFA in the Automata Builder to convert a nondeterministic machine.", icon="ℹ️")
        else:
            st.write(f"Source: manual NFA with {len(nfa.states)} states and alphabet {format_alphabet(nfa)}.")
        st.button("Convert NFA to DFA", key="convert_manual_button", type="primary",
                  disabled=not ready, on_click=convert_manual_and_store)

    outcome = st.session_state.get("converter_manual_outcome")
    if not ready or outcome is None or outcome[0] != manual_signature():
        return
    result = outcome[1]
    if isinstance(result, ValueError):
        st.error(str(result), icon="⚠️")
        return
    nfa, conversion = result
    st.success(
        f"Converted a {len(nfa.states)}-state manual NFA into a {len(conversion.dfa.states)}-state DFA. "
        "Structural validation passed.",
        icon="✅",
    )
    with st.container(border=True):
        st.markdown("### A. Manual NFA")
        render_automaton(nfa, [("Source", "Manual NFA from Automata Builder")], diagram_key="converter_manual_nfa")
    with st.container(border=True):
        st.markdown("### B. Subset construction")
        render_subset_construction(conversion)
    with st.container(border=True):
        st.markdown("### C. Converted DFA")
        render_automaton_diagram(conversion.dfa, key="converter_manual_dfa", title="DFA diagram")
        st.caption("Each DFA state stands for the set of NFA states listed in section B.")
        render_dfa_summary("Source", "Manual NFA from Automata Builder", conversion)
        render_dfa_transition_table(conversion)


def render_converter() -> None:
    st.subheader("NFA to DFA Converter")
    st.write(
        "Convert an NFA into an equivalent DFA with subset construction, step by step. The NFA can "
        "come from a regular expression (via Thompson's construction) or from a manual definition."
    )
    regex_source, manual_source = st.tabs(CONVERTER_SOURCES)
    with regex_source:
        with st.container(border=True):
            st.text_input(
                "Regular Expression",
                placeholder="(0|1)*01",
                key="converter_input",
                help=f"Same syntax as the Automata Builder. Maximum {MAX_EXPRESSION_LENGTH} characters.",
            )
            st.button("Convert NFA to DFA", key="convert_button", type="primary", on_click=convert_and_store)
        render_conversion_outcome()
    with manual_source:
        render_manual_conversion()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.caption(TAGLINE)
        st.markdown("#### About")
        st.write(
            "FiniteTrace is an open-source tool for building, visualizing, converting "
            "and simulating finite automata (DFA and NFA)."
        )
        st.markdown("#### How it works")
        st.markdown(
            "- **Build**: enter a regular expression, a language rule, an exact string, "
            "or a manual transition table.\n"
            "- **Convert**: turn an NFA into a DFA with subset construction, showing ε-closures.\n"
            "- **Simulate**: step through a test string and see whether it is accepted."
        )
        st.markdown("#### Diagrams")
        render_layout_control()
        st.markdown("#### Status")
        st.write("Module 07 of 10 complete: state diagrams for every automaton. "
                 "Animated simulation is planned.")


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
