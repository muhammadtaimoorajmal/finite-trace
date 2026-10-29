"""
String Simulator tab: pick an automaton, enter a test string, and see the
verdict with a step-by-step trace from core/simulator.py.

Three sources, each in its own tab with its own inputs and result:
    Regular Expression   build an ε-NFA or DFA directly from an expression
    Builder Automaton    any still-valid result from the Automata Builder
    Converted DFA        any still-valid DFA from the NFA to DFA Converter

A result is stored with the inputs that produced it (source, automaton and
test string) and shown only while those inputs are unchanged.
"""

import streamlit as st

from core.automata import DFA, NFA, FiniteAutomaton
from core.converter import ConversionError, format_subset, regex_to_dfa
from core.regex_parser import MAX_EXPRESSION_LENGTH, RegexSyntaxError
from core.simulator import MAX_SIMULATION_LENGTH, SimulationError, SimulationResult, simulate
from core.thompson import ConstructionError, regex_to_nfa
from ui.automaton_view import format_alphabet, format_states
from ui.visualizer import render_automaton_diagram

SIMULATION_ERRORS = (RegexSyntaxError, ConstructionError, ConversionError, SimulationError)
SIMULATOR_SOURCES = ["Regular Expression", "Builder Automaton", "Converted DFA"]
MAX_EDGES_SHOWN = 12

TEST_STRING_HELP = (
    "Characters are read literally, one at a time, and must be in the automaton's alphabet. "
    "Leave the field empty to test the empty string ε; typing 'ε' is treated as an ordinary "
    f"(unsupported) character. Maximum {MAX_SIMULATION_LENGTH} characters."
)


def _shown(text: str) -> str:
    return f"'{text}'" if text else "ε (empty string)"


def _format_edges(edges) -> str:
    if not edges:
        return "—"
    parts = [f"{source}→{target}" for source, _, target in edges[:MAX_EDGES_SHOWN]]
    more = f" … +{len(edges) - MAX_EDGES_SHOWN} more" if len(edges) > MAX_EDGES_SHOWN else ""
    return ", ".join(parts) + more


def _trace_rows(result: SimulationResult) -> list[dict]:
    rows = []
    if result.machine_type == DFA:
        for step in result.steps:
            (state,) = step.active_after
            rows.append({
                "Step": step.index,
                "Position": step.position or "—",
                "Read": step.symbol if step.symbol is not None else "Start",
                "From": next(iter(step.active_before)) if step.active_before else "—",
                "To": state,
                "Explanation": step.explanation,
            })
        return rows
    formatted: dict = {}  # active sets repeat; format each distinct set once

    def subset(states) -> str:
        if states not in formatted:
            formatted[states] = format_subset(states)
        return formatted[states]

    for step in result.steps:
        rows.append({
            "Step": step.index,
            "Read": step.symbol if step.symbol is not None else "Start",
            "Active before": subset(step.active_before) if step.index else "—",
            "Symbol transitions": _format_edges(step.symbol_edges),
            "move": subset(step.moved_to),
            "ε-transitions": _format_edges(step.epsilon_edges),
            "Active after ε-closure": subset(step.active_after),
        })
    return rows


def render_simulation_result(source: str, automaton: FiniteAutomaton, result: SimulationResult, *, key: str) -> None:
    if result.accepted:
        st.success(f"**Accepted**: {result.explanation.removeprefix('Accepted: ')}", icon="✅")
    else:
        st.warning(f"**Rejected**: {result.explanation.removeprefix('Rejected: ')}", icon="❌")

    with st.container(border=True):
        columns = st.columns(4)
        columns[0].metric("Machine type", result.machine_type)
        columns[1].metric("Input length", len(result.input_string))
        columns[2].metric("Steps", len(result.steps))
        columns[3].metric("Final active states", len(result.final_states))
        fields = [
            ("Source", source),
            ("Test string", _shown(result.input_string)),
            ("Alphabet Σ", format_alphabet(automaton)),
            ("Initial state", result.initial_state),
            ("Accepting states", format_states(result.accepting_states) or "none"),
            ("Final active state(s)", format_subset(result.final_states)),
        ]
        left, right = st.columns(2)
        for index, (label, value) in enumerate(fields):
            with left if index % 2 == 0 else right:
                st.markdown(f"**{label}**")
                st.code(value, language=None, wrap_lines=True)

    render_automaton_diagram(automaton, key=key, title="Simulated automaton")
    st.caption("Static diagram of the automaton above. Highlighting of active states during "
               "simulation arrives in Module 08; the trace table shows every step now.")

    caption = (
        "A DFA is always in exactly one state; each row follows its single transition."
        if result.machine_type == DFA else
        "An NFA follows every possible path at once. Each row shows the active states, the symbol "
        "transitions taken (move), the ε-transitions used, and the active set after ε-closure."
    )
    with st.expander(f"Step-by-step trace ({len(result.steps)} steps)", expanded=len(result.steps) <= 30):
        st.caption(caption)
        st.dataframe(_trace_rows(result), hide_index=True, width="stretch")


def _render_outcome(outcome_key: str, signature) -> None:
    outcome = st.session_state.get(outcome_key)
    if outcome is None:
        return
    saved_signature, result = outcome
    if saved_signature != signature:
        st.caption("The automaton or test string has changed. Press Simulate String to run it again.")
        return
    if isinstance(result, ValueError):
        st.error(str(result), icon="⚠️")
        return
    source, automaton, simulation = result
    render_simulation_result(source, automaton, simulation, key=outcome_key)


def _test_string_input(key: str) -> None:
    st.text_input("Test string", key=key, placeholder="leave empty for ε", help=TEST_STRING_HELP)


# --- Regular expression source ------------------------------------------------

def _regex_signature():
    return tuple(st.session_state.get(key, "") for key in ("sim_regex", "sim_regex_machine", "sim_regex_text"))


def simulate_regex() -> None:
    expression, machine, text = _regex_signature()
    try:
        automaton = regex_to_dfa(expression) if machine == DFA else regex_to_nfa(expression)
        source = f"Regular expression {expression} → {'DFA (subset construction)' if machine == DFA else 'ε-NFA (Thompson)'}"
        result = (source, automaton, simulate(automaton, text))
    except SIMULATION_ERRORS as error:
        result = error
    st.session_state["sim_regex_outcome"] = (_regex_signature(), result)


def _render_regex_source() -> None:
    with st.container(border=True):
        left, right = st.columns([3, 2])
        with left:
            st.text_input(
                "Regular expression",
                placeholder="(a|b)*abb",
                key="sim_regex",
                help=f"Same syntax as the Automata Builder. Maximum {MAX_EXPRESSION_LENGTH} characters.",
            )
            _test_string_input("sim_regex_text")
        with right:
            st.radio("Machine type", [NFA, DFA], horizontal=True, key="sim_regex_machine",
                     help="NFA: Thompson's ε-NFA. DFA: that NFA converted by subset construction.")
        st.button("Simulate String", key="sim_regex_button", type="primary", on_click=simulate_regex)
    _render_outcome("sim_regex_outcome", _regex_signature())


# --- Builder and converter sources -------------------------------------------

def _render_saved_source(prefix: str, candidates, empty_message: str) -> None:
    """Simulate one of the currently valid saved automata listed in `candidates`."""
    choice_key, text_key, outcome_key = f"{prefix}_choice", f"{prefix}_text", f"{prefix}_outcome"
    labels = [label for label, _ in candidates]
    automata = dict(candidates)

    def signature():
        label = st.session_state.get(choice_key)
        return (label, automata.get(label), st.session_state.get(text_key, ""))

    def run() -> None:
        label, automaton, text = signature()
        if automaton is None:
            return
        try:
            result = (label, automaton, simulate(automaton, text))
        except SimulationError as error:
            result = error
        st.session_state[outcome_key] = (signature(), result)

    with st.container(border=True):
        if not labels:
            st.info(empty_message, icon="ℹ️")
        st.selectbox("Automaton", labels, key=choice_key, disabled=not labels,
                     placeholder="Nothing available yet")
        _test_string_input(text_key)
        st.button("Simulate String", key=f"{prefix}_button", type="primary", disabled=not labels, on_click=run)
    if labels:
        _render_outcome(outcome_key, signature())


def render_simulator_tab(builder_candidates, converted_candidates) -> None:
    st.write(
        "Run a test string through a DFA or NFA and see whether it is accepted, with every "
        "state change recorded."
    )
    with st.expander("How simulation works"):
        st.markdown(
            "- **DFA:** start in the initial state and follow exactly one transition per character.\n"
            "- **NFA:** keep a *set* of active states. For each character, follow every matching "
            "transition from every active state (move), then add all states reachable by ε-transitions "
            "(ε-closure). Step 0 is the ε-closure of the initial state.\n"
            "- **Acceptance:** after the whole input is read, the string is accepted if an active state "
            "is accepting. An NFA whose active set becomes empty rejects.\n"
            "- **Empty string:** leave the test string empty. Characters outside the alphabet "
            "(including a typed 'ε') are reported as invalid input, not as a rejection."
        )
    regex_tab, builder_tab, converted_tab = st.tabs(SIMULATOR_SOURCES)
    with regex_tab:
        _render_regex_source()
    with builder_tab:
        _render_saved_source(
            "sim_builder", builder_candidates,
            "No Builder automaton is available. Generate one in the Automata Builder (ε-NFA or DFA from a "
            "regular expression, a language rule, an exact string or a manual automaton), then come back. "
            "Results whose inputs were edited afterwards are not offered.",
        )
    with converted_tab:
        _render_saved_source(
            "sim_converted", converted_candidates,
            "No converted DFA is available. Convert an NFA in the NFA to DFA Converter first.",
        )
    with st.container(border=True):
        st.markdown("**Animation**")
        controls = st.columns(4)
        for column, label in zip(controls, ["▶ Play", "⏸ Pause", "⏭ Step", "↺ Reset"]):
            column.button(label, disabled=True, width="stretch")
        st.caption("⏳ Step-by-step highlighting on the diagram (play, pause, step, reset) arrives in Module 08; "
                   "the trace table above already shows every step.")
