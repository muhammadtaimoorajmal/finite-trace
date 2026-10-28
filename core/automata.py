"""
Shared finite automaton data model for FiniteTrace.

A finite automaton is the 5-tuple (Q, Σ, δ, q0, F):

    Q   - a finite set of states                      -> FiniteAutomaton.states
    Σ   - the input alphabet                          -> FiniteAutomaton.alphabet
    δ   - the transition function                     -> FiniteAutomaton.transitions
    q0  - the initial (start) state                   -> FiniteAutomaton.initial_state
    F   - the set of accepting (final) states         -> FiniteAutomaton.accepting_states

The same class is used for both DFAs and NFAs. Transitions are always stored as

    (source_state, symbol) -> set of destination states

so a DFA simply has exactly one destination in each set, while an NFA may
have zero, one, or several. Epsilon (empty-string) transitions use the Python
value ``None`` as their symbol; the character "ε" is only used for display.
"""

from dataclasses import dataclass, field
from typing import Optional

# Supported machine types.
DFA = "DFA"
NFA = "NFA"
MACHINE_TYPES = (DFA, NFA)

# Internal epsilon symbol, and how it is shown to users.
EPSILON = None
EPSILON_DISPLAY = "ε"

# A transition key: (source state, input symbol or None for epsilon).
TransitionKey = tuple[str, Optional[str]]


class AutomatonValidationError(ValueError):
    """Raised when an automaton definition is structurally invalid."""


def display_symbol(symbol: Optional[str]) -> str:
    """Return a printable form of a transition symbol (None becomes 'ε')."""
    if symbol is EPSILON:
        return EPSILON_DISPLAY
    return symbol


@dataclass
class FiniteAutomaton:
    """A DFA or NFA described by states, alphabet, transitions, start and accepting states."""

    machine_type: str
    states: set[str]
    alphabet: set[str]
    initial_state: str
    accepting_states: set[str]
    transitions: dict[TransitionKey, set[str]] = field(default_factory=dict)

    @property
    def is_dfa(self) -> bool:
        return self.machine_type == DFA

    @property
    def is_nfa(self) -> bool:
        return self.machine_type == NFA

    def get_destinations(self, state: str, symbol: Optional[str]) -> set[str]:
        """Return the destination states for (state, symbol), or an empty set if none."""
        return set(self.transitions.get((state, symbol), set()))

    def add_transition(self, source: str, symbol: Optional[str], destination: str) -> None:
        """Add one transition source --symbol--> destination (no validation is performed here)."""
        key = (source, symbol)
        if key not in self.transitions:
            self.transitions[key] = set()
        self.transitions[key].add(destination)

    def validate(self, require_complete: bool = True) -> None:
        """
        Check that this automaton is well formed.

        Raises AutomatonValidationError with a specific message on the first
        problem found. For a DFA, ``require_complete`` controls whether every
        (state, symbol) pair must have a transition defined.
        """
        _check_machine_type(self)
        _check_states(self)
        _check_alphabet(self)
        _check_initial_and_accepting(self)
        _check_transitions(self)
        if self.is_dfa:
            _check_dfa_rules(self, require_complete)

    def is_valid(self, require_complete: bool = True) -> bool:
        """Return True if validate() succeeds, False otherwise."""
        try:
            self.validate(require_complete)
        except AutomatonValidationError:
            return False
        return True


# ---------------------------------------------------------------------------
# Validation helpers. Each one checks a single rule and raises on failure.
# ---------------------------------------------------------------------------

def _check_machine_type(automaton: FiniteAutomaton) -> None:
    if automaton.machine_type not in MACHINE_TYPES:
        raise AutomatonValidationError(
            f"Invalid machine type {automaton.machine_type!r}; expected one of {MACHINE_TYPES}."
        )


def _check_states(automaton: FiniteAutomaton) -> None:
    if not automaton.states:
        raise AutomatonValidationError("The automaton must have at least one state.")
    for state in automaton.states:
        if not isinstance(state, str) or not state.strip():
            raise AutomatonValidationError(
                f"Invalid state identifier {state!r}; states must be nonempty strings."
            )


def _check_alphabet(automaton: FiniteAutomaton) -> None:
    for symbol in automaton.alphabet:
        if symbol is EPSILON:
            raise AutomatonValidationError(
                "Epsilon (None) must not be part of the alphabet; it is only allowed as an NFA transition symbol."
            )
        if not isinstance(symbol, str) or len(symbol) != 1 or symbol.isspace():
            raise AutomatonValidationError(
                f"Invalid alphabet symbol {symbol!r}; each symbol must be a single non-whitespace character."
            )


def _check_initial_and_accepting(automaton: FiniteAutomaton) -> None:
    if automaton.initial_state not in automaton.states:
        raise AutomatonValidationError(
            f"Initial state {automaton.initial_state!r} is not in the set of states."
        )
    for state in automaton.accepting_states:
        if state not in automaton.states:
            raise AutomatonValidationError(
                f"Accepting state {state!r} is not in the set of states."
            )


def _check_transitions(automaton: FiniteAutomaton) -> None:
    for (source, symbol), destinations in automaton.transitions.items():
        label = f"δ({source!r}, {display_symbol(symbol)!r})"
        if source not in automaton.states:
            raise AutomatonValidationError(
                f"Transition {label} starts from unknown state {source!r}."
            )
        if symbol is not EPSILON and symbol not in automaton.alphabet:
            raise AutomatonValidationError(
                f"Transition {label} uses symbol {symbol!r}, which is not in the alphabet."
            )
        if not isinstance(destinations, set):
            raise AutomatonValidationError(
                f"Transition {label} destinations must be a set of states."
            )
        for destination in destinations:
            if destination not in automaton.states:
                raise AutomatonValidationError(
                    f"Transition {label} leads to unknown state {destination!r}."
                )


def _check_dfa_rules(automaton: FiniteAutomaton, require_complete: bool) -> None:
    # A DFA has no epsilon moves and at most one destination per (state, symbol).
    for (source, symbol), destinations in automaton.transitions.items():
        if symbol is EPSILON:
            raise AutomatonValidationError(
                f"DFA must not contain epsilon transitions (found one from state {source!r})."
            )
        if len(destinations) > 1:
            raise AutomatonValidationError(
                f"DFA transition δ({source!r}, {symbol!r}) has {len(destinations)} destinations "
                f"{sorted(destinations)}; a DFA allows exactly one."
            )

    if not require_complete:
        return

    # A complete DFA defines exactly one move for every state and every symbol.
    for state in sorted(automaton.states):
        for symbol in sorted(automaton.alphabet):
            if len(automaton.transitions.get((state, symbol), set())) != 1:
                raise AutomatonValidationError(
                    f"Incomplete DFA: missing transition for state {state!r} on symbol {symbol!r}."
                )
