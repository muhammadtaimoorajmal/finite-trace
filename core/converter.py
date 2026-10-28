"""
NFA-to-DFA conversion by subset construction.

A DFA state stands for the *set* of NFA states the NFA could be in at once.
Two operations drive the construction:

    ε-closure(S)   every state reachable from S using only ε-transitions
    move(S, x)     every state reachable from S by reading one symbol x

Starting from D0 = ε-closure({q0}), each DFA state's transition on x is

    ε-closure(move(S, x))

Each new subset discovered this way becomes the next DFA state (D1, D2, ...).
Subsets are explored breadth-first, with symbols in sorted order, until no
unexplored subsets remain, so only reachable subsets ever become states.

A subset is accepting if it contains at least one accepting NFA state. The
empty subset ∅ is the dead state: it is non-accepting and loops to itself.
The resulting DFA is complete and equivalent to the NFA, but not minimized.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from core.automata import (
    DFA,
    AutomatonValidationError,
    FiniteAutomaton,
    state_sort_key,
)
from core.thompson import regex_to_nfa

# Subset construction can need exponentially many states in the worst case;
# stop with an error rather than freezing the app or returning a partial DFA.
MAX_DFA_STATES = 512


class ConversionError(ValueError):
    """Raised when an NFA cannot be converted (invalid input or resource limit)."""


@dataclass(frozen=True)
class ConversionStep:
    """One DFA transition calculation: ε-closure(move(subset, symbol))."""

    number: int
    source_dfa_state: str
    source_nfa_subset: frozenset[str]
    input_symbol: str
    move_result: frozenset[str]
    epsilon_closure_result: frozenset[str]
    destination_dfa_state: str
    is_new_state: bool


@dataclass(frozen=True)
class ConversionResult:
    dfa: FiniteAutomaton
    state_mapping: dict[str, frozenset[str]]   # DFA state name -> NFA subset, in discovery order
    steps: tuple[ConversionStep, ...]
    nfa_initial_state: str
    dead_state: Optional[str]                  # name of the ∅ state, or None if unreachable

    @property
    def initial_closure(self) -> frozenset[str]:
        return self.state_mapping[self.dfa.initial_state]


def format_subset(subset) -> str:
    """Display a set of NFA states as {q0, q1, q2} in numeric order, or ∅ when empty."""
    if not subset:
        return "∅"
    return "{" + ", ".join(sorted(subset, key=state_sort_key)) + "}"


def epsilon_closure(nfa: FiniteAutomaton, states) -> frozenset[str]:
    """Return all states reachable from `states` by zero or more ε-transitions."""
    closure = set(states)
    pending = list(states)
    # Each state is added to `pending` only when first seen, so ε-cycles terminate.
    while pending:
        state = pending.pop()
        for target in nfa.get_destinations(state, None):
            if target not in closure:
                closure.add(target)
                pending.append(target)
    return frozenset(closure)


def move(nfa: FiniteAutomaton, states, symbol: str) -> frozenset[str]:
    """Return the states reachable from `states` by reading exactly one `symbol` (no ε-moves)."""
    if symbol is None:
        raise ConversionError("move() reads an input symbol; use epsilon_closure() for ε-transitions.")
    destinations = set()
    for state in states:
        destinations |= nfa.get_destinations(state, symbol)
    return frozenset(destinations)


def _check_input(nfa: FiniteAutomaton) -> None:
    # A DFA is a special case of an NFA, so both are accepted. Completeness is
    # not required: missing transitions simply lead to the dead state.
    try:
        nfa.validate(require_complete=False)
    except AutomatonValidationError as error:
        raise ConversionError(f"Cannot convert an invalid automaton: {error}") from error


def convert_nfa_to_dfa(nfa: FiniteAutomaton, max_states: int = MAX_DFA_STATES) -> ConversionResult:
    """Convert an NFA (with or without ε-transitions) into an equivalent complete DFA."""
    _check_input(nfa)
    symbols = sorted(nfa.alphabet)

    start_subset = epsilon_closure(nfa, {nfa.initial_state})
    names: dict[frozenset[str], str] = {start_subset: "D0"}
    queue = deque([start_subset])
    transitions: dict[tuple[str, str], set[str]] = {}
    steps: list[ConversionStep] = []

    while queue:
        subset = queue.popleft()
        source = names[subset]
        for symbol in symbols:
            moved = move(nfa, subset, symbol)
            closure = epsilon_closure(nfa, moved)
            is_new = closure not in names
            if is_new:
                if len(names) >= max_states:
                    raise ConversionError(
                        f"The DFA would need more than {max_states} states. Subset construction can "
                        "produce many states for large NFAs; try a smaller expression."
                    )
                names[closure] = f"D{len(names)}"
                queue.append(closure)
            destination = names[closure]
            transitions[(source, symbol)] = {destination}
            steps.append(
                ConversionStep(
                    number=len(steps) + 1,
                    source_dfa_state=source,
                    source_nfa_subset=subset,
                    input_symbol=symbol,
                    move_result=moved,
                    epsilon_closure_result=closure,
                    destination_dfa_state=destination,
                    is_new_state=is_new,
                )
            )

    state_mapping = {name: subset for subset, name in names.items()}
    accepting = {name for name, subset in state_mapping.items() if subset & nfa.accepting_states}
    dfa = FiniteAutomaton(
        machine_type=DFA,
        states=set(state_mapping),
        alphabet=set(nfa.alphabet),
        initial_state="D0",
        accepting_states=accepting,
        transitions=transitions,
    )
    try:
        dfa.validate(require_complete=True)
    except AutomatonValidationError as error:
        raise ConversionError(f"The converted DFA is invalid: {error}") from error

    return ConversionResult(
        dfa=dfa,
        state_mapping=state_mapping,
        steps=tuple(steps),
        nfa_initial_state=nfa.initial_state,
        dead_state=names.get(frozenset()),
    )


def regex_to_dfa(expression: str) -> FiniteAutomaton:
    """Parse a regular expression, build its ε-NFA, and convert it to a DFA."""
    return convert_nfa_to_dfa(regex_to_nfa(expression)).dfa
