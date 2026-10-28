"""Reusable Streamlit display for any FiniteAutomaton: summary, states and a transition table."""

from typing import Optional

import streamlit as st

from core.automata import DFA, EPSILON_DISPLAY, FiniteAutomaton, state_sort_key


def format_alphabet(automaton: FiniteAutomaton) -> str:
    if not automaton.alphabet:
        return "{} (empty: no input symbols)"
    return "{" + ", ".join(sorted(automaton.alphabet)) + "}"


def format_states(states) -> str:
    return ", ".join(sorted(states, key=state_sort_key))


def state_label(automaton: FiniteAutomaton, state: str) -> str:
    """Prefix a state with → if initial and ★ if accepting, as in textbook tables."""
    prefix = ("→" if state == automaton.initial_state else "") + ("★" if state in automaton.accepting_states else "")
    return f"{prefix} {state}".strip()


def transition_grid_rows(automaton: FiniteAutomaton, notes: Optional[dict] = None) -> list[dict]:
    """
    One row per state, one column per symbol (plus ε for NFAs that use it).
    DFA cells hold the single next state; NFA cells hold a set, or ∅ when there is no move.
    """
    symbols: list = sorted(automaton.alphabet)
    if any(symbol is None for (_, symbol) in automaton.transitions):
        symbols.append(None)
    rows = []
    for state in automaton.sorted_states():
        row = {"State": state_label(automaton, state)}
        for symbol in symbols:
            destinations = automaton.get_destinations(state, symbol)
            column = EPSILON_DISPLAY if symbol is None else symbol
            if automaton.machine_type == DFA and len(destinations) == 1:
                row[column] = next(iter(destinations))
            elif destinations:
                row[column] = "{" + format_states(destinations) + "}"
            else:
                row[column] = "∅"
        if notes:
            row["Meaning"] = notes.get(state, "")
        rows.append(row)
    return rows


def render_automaton(automaton: FiniteAutomaton, details: list[tuple[str, str]], notes: Optional[dict] = None) -> None:
    """Show metrics, the given detail fields, the state set and the transition table."""
    transitions = automaton.transition_list()
    epsilon_count = sum(1 for _, symbol, _ in transitions if symbol is None)
    with st.container(border=True):
        columns = st.columns(4)
        columns[0].metric("Machine type", automaton.machine_type)
        columns[1].metric("States", len(automaton.states))
        columns[2].metric("Transitions", len(transitions))
        columns[3].metric("ε-transitions", epsilon_count)

        fields = details + [
            ("Alphabet Σ", format_alphabet(automaton)),
            ("Initial state", automaton.initial_state),
            ("Accepting states", format_states(automaton.accepting_states) or "none (accepts no strings)"),
        ]
        left, right = st.columns(2)
        for index, (label, value) in enumerate(fields):
            with left if index % 2 == 0 else right:
                st.markdown(f"**{label}**")
                st.code(value, language=None, wrap_lines=True)
        st.markdown("**States**")
        st.code("{" + format_states(automaton.states) + "}", language=None, wrap_lines=True)

    st.markdown("#### Transition table")
    if automaton.alphabet or epsilon_count:
        st.caption(
            "→ marks the initial state and ★ accepting states. "
            + ("Each cell is the single next state." if automaton.machine_type == DFA
               else "Each cell is the set of next states; ∅ means no transition.")
        )
        st.dataframe(transition_grid_rows(automaton, notes), hide_index=True, width="stretch")
    else:
        st.info("The alphabet is empty and there are no ε-transitions, so there is nothing to tabulate.", icon="ℹ️")
