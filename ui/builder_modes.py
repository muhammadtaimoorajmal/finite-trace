"""
Automata Builder input modes beyond regular expressions: language rules,
exact strings and manual DFA/NFA definitions.

Each mode keeps its own result in session state as (signature, result), where
the signature records the inputs that produced it. A result is shown only
while the current inputs still match its signature, so edited inputs never
display an old automaton.
"""

from typing import Optional

import streamlit as st

from core.automata import DFA, NFA, FiniteAutomaton
from core.language_builder import (
    MAX_COUNT,
    RULES,
    LanguageAutomaton,
    LanguageRuleError,
    as_nfa,
    build_exact_string,
    build_language,
)
from core.manual_builder import ManualInputError, parse_alphabet, parse_and_build
from ui.automaton_view import render_automaton

INPUT_ERRORS = (LanguageRuleError, ManualInputError)
RULE_IDS_BY_LABEL = {label: rule for rule, (label, _) in RULES.items()}

NFA_NOTE = (
    "Shown as an NFA: every DFA is also an NFA whose transitions have exactly one destination "
    "and no ε-moves. This is not a Thompson ε-NFA; use the Regular Expression mode for that."
)


def _show_stale_or_error(outcome, signature, button: str) -> Optional[object]:
    """Return a successful result to display, or render the stale/error message and return None."""
    if outcome is None:
        return None
    saved_signature, result = outcome
    if saved_signature != signature:
        st.caption(f"The inputs have changed. Press {button} to update the result.")
        return None
    if isinstance(result, ValueError):
        st.error(str(result), icon="⚠️")
        st.caption(f"Fix the input above and press {button} again.")
        return None
    return result


def _render_generated(result: LanguageAutomaton, automaton: FiniteAutomaton, details) -> None:
    st.success(f"{automaton.machine_type} generated with {len(automaton.states)} states.", icon="✅")
    render_automaton(automaton, details + [("Description", result.description)], result.state_notes)
    if automaton.machine_type == NFA:
        st.caption(NFA_NOTE)


# ---------------------------------------------------------------------------
# Language rules
# ---------------------------------------------------------------------------

def _language_parameter():
    """The value of the single parameter the selected rule needs (pattern, symbol or count)."""
    rule = RULE_IDS_BY_LABEL[st.session_state.get("lang_rule", next(iter(RULE_IDS_BY_LABEL)))]
    needs = RULES[rule][1]
    if needs == "pattern":
        return rule, needs, st.session_state.get("lang_pattern", "")
    if needs == "symbol":
        return rule, needs, st.session_state.get("lang_symbol", "").strip()
    return rule, needs, (st.session_state.get("lang_symbol", "").strip(), st.session_state.get("lang_count", 0))


def _language_signature():
    rule, _, parameter = _language_parameter()
    return (st.session_state.get("lang_alphabet", ""), rule, parameter, st.session_state.get("lang_output", DFA))


def generate_language() -> None:
    rule, needs, parameter = _language_parameter()
    try:
        alphabet = parse_alphabet(st.session_state.get("lang_alphabet", ""))
        if needs == "pattern":
            result = build_language(rule, alphabet, pattern=parameter)
        elif needs == "symbol":
            result = build_language(rule, alphabet, symbol=parameter)
        else:
            symbol, count = parameter
            result = build_language(rule, alphabet, symbol=symbol, count=count)
    except INPUT_ERRORS as error:
        st.session_state["lang_outcome"] = (_language_signature(), error)
        return
    automaton = as_nfa(result.automaton) if st.session_state.get("lang_output") == NFA else result.automaton
    st.session_state["lang_outcome"] = (_language_signature(), (result, automaton))


def render_language_mode() -> None:
    st.write(
        "Pick a rule and its parameters; FiniteTrace builds a DFA for that language. "
        "Rules are structured choices, not free-form English."
    )
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.text_input("Alphabet", value="0,1", key="lang_alphabet", help="Comma-separated single characters, e.g. a,b or 0,1.")
            label = st.selectbox("Rule", list(RULE_IDS_BY_LABEL), key="lang_rule")
        with right:
            needs = RULES[RULE_IDS_BY_LABEL[label]][1]
            if needs == "pattern":
                st.text_input("Pattern", placeholder="01", key="lang_pattern", help="Every character must be in the alphabet.")
            else:
                st.text_input("Symbol to count", placeholder="0", key="lang_symbol")
                if needs == "count":
                    st.number_input("Number of occurrences k", min_value=0, max_value=MAX_COUNT, value=1, step=1, key="lang_count")
            st.radio("Output", [DFA, NFA], horizontal=True, key="lang_output")
        st.button("Generate Automaton", key="lang_generate", type="primary", on_click=generate_language)

    shown = _show_stale_or_error(st.session_state.get("lang_outcome"), _language_signature(), "Generate Automaton")
    if shown is not None:
        result, automaton = shown
        rule, _, parameter = _language_parameter()
        if isinstance(parameter, tuple):
            parameter = f"symbol '{parameter[0]}', k = {parameter[1]}"
        _render_generated(result, automaton, [("Rule", f"{RULES[rule][0]}: {parameter}")])


# ---------------------------------------------------------------------------
# Exact strings
# ---------------------------------------------------------------------------

def _exact_signature():
    return (
        st.session_state.get("exact_alphabet", ""),
        st.session_state.get("exact_text", ""),
        st.session_state.get("exact_output", DFA),
    )


def generate_exact() -> None:
    try:
        alphabet = parse_alphabet(st.session_state.get("exact_alphabet", ""))
        result = build_exact_string(st.session_state.get("exact_text", ""), alphabet)
    except INPUT_ERRORS as error:
        st.session_state["exact_outcome"] = (_exact_signature(), error)
        return
    automaton = as_nfa(result.automaton) if st.session_state.get("exact_output") == NFA else result.automaton
    st.session_state["exact_outcome"] = (_exact_signature(), (result, automaton))


def render_exact_mode() -> None:
    st.write(
        "Build an automaton that accepts exactly one string. The string is taken literally: "
        "with '|' in the alphabet, a|b means the three characters a, |, b, not a choice."
    )
    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.text_input("Alphabet", value="a,b", key="exact_alphabet", help="Comma-separated single characters.")
            st.text_input(
                "Exact string",
                placeholder="aabb",
                key="exact_text",
                help="Leave empty for the automaton that accepts only the empty string ε.",
            )
        with right:
            st.radio("Output", [DFA, NFA], horizontal=True, key="exact_output")
        st.button("Generate Automaton", key="exact_generate", type="primary", on_click=generate_exact)

    shown = _show_stale_or_error(st.session_state.get("exact_outcome"), _exact_signature(), "Generate Automaton")
    if shown is not None:
        result, automaton = shown
        text = st.session_state.get("exact_text", "")
        _render_generated(result, automaton, [("Exact string", text if text else "ε (empty string)")])


# ---------------------------------------------------------------------------
# Manual DFA / NFA
# ---------------------------------------------------------------------------

MANUAL_FIELDS = ["manual_type", "manual_alphabet", "manual_states", "manual_initial", "manual_accepting", "manual_transitions"]

EXAMPLES = {
    "DFA: even number of 0s": {
        "manual_type": DFA, "manual_alphabet": "0,1", "manual_states": "q0,q1", "manual_initial": "q0",
        "manual_accepting": "q0", "manual_transitions": "q0,0,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1",
    },
    "ε-NFA: exactly a or b": {
        "manual_type": NFA, "manual_alphabet": "a,b", "manual_states": "q0,q1,q2,q3", "manual_initial": "q0",
        "manual_accepting": "q3", "manual_transitions": "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3",
    },
    "NFA: second-to-last symbol is a": {
        "manual_type": NFA, "manual_alphabet": "a,b", "manual_states": "A,B,C", "manual_initial": "A",
        "manual_accepting": "C", "manual_transitions": "A,a,A\nA,b,A\nA,a,B\nB,a,C\nB,b,C",
    },
}


def manual_signature() -> tuple:
    return tuple(st.session_state.get(key, "") for key in MANUAL_FIELDS)


def load_example() -> None:
    example = EXAMPLES.get(st.session_state.get("manual_example"))
    if example:
        st.session_state.update(example)


def build_manual() -> None:
    try:
        result = parse_and_build(*manual_signature())
    except ManualInputError as error:
        result = error
    st.session_state["manual_outcome"] = (manual_signature(), result)


def current_manual_automaton() -> tuple[str, Optional[FiniteAutomaton]]:
    """
    The validated manual automaton if it still matches the form.
    Returns (status, automaton) with status 'ok', 'none', 'stale' or 'error'.
    """
    outcome = st.session_state.get("manual_outcome")
    if outcome is None:
        return "none", None
    signature, result = outcome
    if signature != manual_signature():
        return "stale", None
    if isinstance(result, ValueError):
        return "error", None
    return "ok", result


def render_manual_mode() -> None:
    st.write("Define your own DFA or NFA by listing its states and transitions.")
    with st.expander("Input format and examples"):
        st.markdown(
            "- **Alphabet**: comma-separated single characters, e.g. `a,b`.\n"
            "- **States**: comma-separated names using letters, digits, `_ . - '`, e.g. `q0,q1,q2`.\n"
            "- **Accepting states**: comma-separated; leave empty for an automaton that accepts nothing.\n"
            "- **Transitions**: one `source,symbol,destination` per line. Use `ε` (or `λ`) as the symbol "
            "for an epsilon move (NFA only). Repeat a source and symbol with different destinations for "
            "nondeterminism (NFA only). Identical lines are merged; blank lines and `#` comments are ignored.\n"
            "- A **DFA** must be complete: exactly one transition for every state and symbol.\n"
            "- Limits: 150 states, 20 symbols, 2,000 transition lines, 40-character state names."
        )
        example_column, button_column = st.columns([3, 1], vertical_alignment="bottom")
        example_column.selectbox("Example", list(EXAMPLES), key="manual_example")
        button_column.button("Load example", key="manual_load", on_click=load_example)

    with st.container(border=True):
        left, right = st.columns(2)
        with left:
            st.radio("Machine type", [DFA, NFA], horizontal=True, key="manual_type")
            st.text_input("Alphabet", placeholder="a,b", key="manual_alphabet")
            st.text_input("States", placeholder="q0,q1,q2", key="manual_states")
            st.text_input("Initial state", placeholder="q0", key="manual_initial")
            st.text_input("Accepting states", placeholder="q2", key="manual_accepting")
        with right:
            st.text_area(
                "Transitions (source,symbol,destination)",
                placeholder="q0,a,q1\nq0,b,q0\nq1,ε,q2",
                height=230,
                key="manual_transitions",
            )
        st.button("Validate & Build", key="manual_build", type="primary", on_click=build_manual)

    shown = _show_stale_or_error(st.session_state.get("manual_outcome"), manual_signature(), "Validate & Build")
    if shown is not None:
        automaton = shown
        kind = "DFA (complete and deterministic)" if automaton.machine_type == DFA else "NFA"
        st.success(f"Valid {kind} with {len(automaton.states)} states.", icon="✅")
        render_automaton(automaton, [])
        if automaton.machine_type == NFA:
            st.caption("To convert it, open the NFA to DFA Converter tab and choose From Manual NFA.")
        else:
            st.caption("This DFA is already deterministic, so it needs no NFA-to-DFA conversion.")
