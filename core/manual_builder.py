"""
Manual DFA/NFA definitions: parse user-entered text into a FiniteAutomaton.

Input format (all lists are comma-separated; spaces around items are ignored):

    Alphabet          a,b            single non-whitespace characters, not ',' 'ε' or 'λ'
    States            q0,q1,q2       letters, digits and _ . - ' (no spaces or commas)
    Initial state     q0
    Accepting states  q2             may be empty
    Transitions       one per line:  source,symbol,destination
                      use ε or λ as the symbol for an epsilon transition (NFA only);
                      blank lines and lines starting with # are ignored.

Repeated source,symbol pairs with different destinations make an NFA
nondeterministic and are rejected for a DFA. Identical rows are merged (a
transition is a set membership, so listing it twice changes nothing).
A manual DFA must be complete: every state needs one transition per symbol.

parse_manual_definition() turns the text into structured data with
line-numbered errors; build_manual_automaton() turns structured data into a
validated FiniteAutomaton and does not depend on Streamlit or text parsing.
"""

import re
from dataclasses import dataclass
from typing import Optional

from core.automata import DFA, MACHINE_TYPES, AutomatonValidationError, FiniteAutomaton

MAX_STATES = 150
MAX_ALPHABET_SIZE = 20
MAX_TRANSITION_ROWS = 2000
MAX_STATE_NAME_LENGTH = 40

EPSILON_INPUTS = {"ε", "λ"}
STATE_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.'\-]+")

Transition = tuple[str, Optional[str], str]


class ManualInputError(ValueError):
    """Raised for malformed or invalid manual automaton definitions."""


@dataclass(frozen=True)
class ManualDefinition:
    machine_type: str
    states: tuple[str, ...]          # in the order the user listed them
    alphabet: frozenset[str]
    initial_state: str
    accepting_states: frozenset[str]
    transitions: tuple[Transition, ...]


def _split_list(text: str, label: str) -> list[str]:
    """Split a comma-separated list. Empty text is an empty list; empty items are errors."""
    if not text.strip():
        return []
    items = [item.strip() for item in text.split(",")]
    if any(item == "" for item in items):
        raise ManualInputError(f"{label}: empty item in '{text.strip()}'. Separate items with single commas.")
    return items


def parse_alphabet(text: str) -> set[str]:
    """Parse a comma-separated alphabet such as 'a,b' or '0, 1'."""
    symbols = _split_list(text, "Alphabet")
    seen = set()
    for symbol in symbols:
        if len(symbol) != 1:
            raise ManualInputError(
                f"Alphabet: '{symbol}' is not a single character. Separate symbols with commas, e.g. a,b."
            )
        if symbol in EPSILON_INPUTS:
            raise ManualInputError(f"Alphabet: '{symbol}' is reserved for epsilon and cannot be an input symbol.")
        if symbol in seen:
            raise ManualInputError(f"Alphabet: '{symbol}' is listed more than once.")
        seen.add(symbol)
    if len(seen) > MAX_ALPHABET_SIZE:
        raise ManualInputError(f"Alphabet: {len(seen)} symbols given; the maximum is {MAX_ALPHABET_SIZE}.")
    return seen


def _check_state_name(name: str, label: str) -> None:
    if len(name) > MAX_STATE_NAME_LENGTH:
        raise ManualInputError(f"{label}: state name '{name[:20]}…' is longer than {MAX_STATE_NAME_LENGTH} characters.")
    if not STATE_NAME_PATTERN.fullmatch(name):
        raise ManualInputError(
            f"{label}: '{name}' is not a valid state name. Use letters, digits, _ . - or ' (no spaces)."
        )


def parse_states(text: str, label: str = "States") -> list[str]:
    """Parse a comma-separated list of state names, keeping the user's order."""
    names = _split_list(text, label)
    seen = set()
    for name in names:
        _check_state_name(name, label)
        if name in seen:
            raise ManualInputError(f"{label}: '{name}' is listed more than once.")
        seen.add(name)
    if len(names) > MAX_STATES:
        raise ManualInputError(f"{label}: {len(names)} states given; the maximum is {MAX_STATES}.")
    return names


def parse_transition_rows(text: str) -> list[tuple[int, str, Optional[str], str]]:
    """Parse 'source,symbol,destination' lines into (line number, source, symbol, destination)."""
    rows = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 3:
            raise ManualInputError(
                f"Transitions line {line_number}: expected 'source,symbol,destination' but found "
                f"{len(fields)} field(s) in '{line}'."
            )
        source, symbol, destination = fields
        if not source or not destination:
            raise ManualInputError(f"Transitions line {line_number}: the source and destination must not be empty.")
        if len(symbol) != 1:
            raise ManualInputError(
                f"Transitions line {line_number}: symbol '{symbol}' must be a single character (or ε for epsilon)."
            )
        rows.append((line_number, source, None if symbol in EPSILON_INPUTS else symbol, destination))
        if len(rows) > MAX_TRANSITION_ROWS:
            raise ManualInputError(f"Transitions: more than {MAX_TRANSITION_ROWS} rows; the maximum is {MAX_TRANSITION_ROWS}.")
    return rows


def parse_manual_definition(
    machine_type: str,
    alphabet_text: str,
    states_text: str,
    initial_text: str,
    accepting_text: str,
    transitions_text: str,
) -> ManualDefinition:
    """Parse the text fields of the manual form, reporting problems with line numbers."""
    if machine_type not in MACHINE_TYPES:
        raise ManualInputError(f"Machine type must be DFA or NFA, not '{machine_type}'.")
    alphabet = parse_alphabet(alphabet_text)
    states = parse_states(states_text)
    if not states:
        raise ManualInputError("States: enter at least one state, e.g. q0,q1.")
    known = set(states)

    initial = initial_text.strip()
    if not initial:
        raise ManualInputError("Initial state: enter the name of the start state.")
    if initial not in known:
        raise ManualInputError(f"Initial state '{initial}' is not one of the listed states.")

    accepting = parse_states(accepting_text, "Accepting states")
    for state in accepting:
        if state not in known:
            raise ManualInputError(f"Accepting state '{state}' is not one of the listed states.")

    first_seen: dict[tuple[str, Optional[str]], tuple[str, int]] = {}
    transitions = []
    for line_number, source, symbol, destination in parse_transition_rows(transitions_text):
        where = f"Transitions line {line_number}"
        for state in (source, destination):
            if state not in known:
                raise ManualInputError(f"{where}: unknown state '{state}'. Add it to the States list first.")
        if symbol is None:
            if machine_type == DFA:
                raise ManualInputError(f"{where}: a DFA cannot have ε-transitions. Choose NFA to use ε.")
        elif symbol not in alphabet:
            raise ManualInputError(f"{where}: symbol '{symbol}' is not in the alphabet.")
        if machine_type == DFA:
            previous = first_seen.get((source, symbol))
            if previous is not None and previous[0] != destination:
                raise ManualInputError(
                    f"{where}: a DFA allows one destination per state and symbol, but ({source}, {symbol}) "
                    f"already goes to '{previous[0]}' on line {previous[1]}."
                )
            first_seen.setdefault((source, symbol), (destination, line_number))
        transitions.append((source, symbol, destination))

    return ManualDefinition(
        machine_type=machine_type,
        states=tuple(states),
        alphabet=frozenset(alphabet),
        initial_state=initial,
        accepting_states=frozenset(accepting),
        transitions=tuple(transitions),
    )


def _missing_dfa_pairs(states, alphabet, transitions) -> list[tuple[str, str]]:
    defined = {(source, symbol) for source, symbol, _ in transitions}
    return [(state, symbol) for state in states for symbol in sorted(alphabet) if (state, symbol) not in defined]


def build_manual_automaton(
    machine_type: str,
    states,
    alphabet,
    initial_state: str,
    accepting_states,
    transitions,
) -> FiniteAutomaton:
    """Build and validate a FiniteAutomaton from structured data. Manual DFAs must be complete."""
    if machine_type not in MACHINE_TYPES:
        raise ManualInputError(f"Machine type must be DFA or NFA, not '{machine_type}'.")
    if len(states) > MAX_STATES:
        raise ManualInputError(f"{len(states)} states given; the maximum is {MAX_STATES}.")
    if len(alphabet) > MAX_ALPHABET_SIZE:
        raise ManualInputError(f"{len(alphabet)} alphabet symbols given; the maximum is {MAX_ALPHABET_SIZE}.")
    if len(transitions) > MAX_TRANSITION_ROWS:
        raise ManualInputError(f"{len(transitions)} transitions given; the maximum is {MAX_TRANSITION_ROWS}.")

    automaton = FiniteAutomaton(
        machine_type=machine_type,
        states=set(states),
        alphabet=set(alphabet),
        initial_state=initial_state,
        accepting_states=set(accepting_states),
    )
    for source, symbol, destination in transitions:
        automaton.add_transition(source, symbol, destination)

    if machine_type == DFA:
        # List every missing pair at once so the user can fix them together.
        missing = _missing_dfa_pairs(list(states), alphabet, transitions)
        if missing:
            shown = "; ".join(f"state '{s}' on symbol '{x}'" for s, x in missing[:10])
            more = f" (and {len(missing) - 10} more)" if len(missing) > 10 else ""
            raise ManualInputError(f"Incomplete DFA: missing transition for {shown}{more}.")
    try:
        automaton.validate(require_complete=True)
    except AutomatonValidationError as error:
        raise ManualInputError(str(error)) from error
    return automaton


def build_from_definition(definition: ManualDefinition) -> FiniteAutomaton:
    return build_manual_automaton(
        definition.machine_type,
        definition.states,
        definition.alphabet,
        definition.initial_state,
        definition.accepting_states,
        definition.transitions,
    )


def parse_and_build(
    machine_type: str,
    alphabet_text: str,
    states_text: str,
    initial_text: str,
    accepting_text: str,
    transitions_text: str,
) -> FiniteAutomaton:
    """Convenience wrapper: parse the form text and build the automaton."""
    return build_from_definition(
        parse_manual_definition(machine_type, alphabet_text, states_text, initial_text, accepting_text, transitions_text)
    )
