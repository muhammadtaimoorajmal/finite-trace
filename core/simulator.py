"""
String simulation for any FiniteAutomaton (DFA, NFA or ε-NFA).

The engine tracks the *set* of active states, which covers both machine types:

    start:        active = ε-closure({initial state})
    each symbol:  active = ε-closure(move(active, symbol))
    accept:       active ∩ accepting states ≠ ∅   (after the whole input)

For a complete DFA there are no ε-moves and exactly one move per symbol, so
the active set always holds exactly one state (the DFA's current state).
For an NFA the set holds every state some path could be in, so all paths are
followed at once without enumerating them. If the set becomes empty, no path
survives; the remaining symbols are still recorded (with no active states)
so the trace always covers the whole input.

Test strings are read literally, one character at a time. Every character
must be in the alphabet: "" is the empty string, and a typed "ε" is just an
unsupported character. Positions in messages and traces count from 1.
"""

from dataclasses import dataclass
from typing import Optional

from core.automata import DFA, AutomatonValidationError, FiniteAutomaton, state_sort_key
from core.converter import epsilon_closure, format_subset, move

MAX_SIMULATION_LENGTH = 1000

# A transition actually followed: (source, symbol, destination); symbol None is ε.
Edge = tuple[str, Optional[str], str]


class SimulationError(ValueError):
    """Raised when the automaton cannot be simulated (it is invalid)."""


class SimulationInputError(SimulationError):
    """Raised when the test string is invalid (unknown symbol or too long)."""


@dataclass(frozen=True)
class SimulationStep:
    """
    One configuration of the run. Step 0 is the start (no symbol consumed);
    step i consumes the i-th character of the input.
    """

    index: int
    position: Optional[int]           # 1-based input position; None for step 0
    symbol: Optional[str]             # consumed character; None for step 0
    active_before: frozenset[str]     # empty for step 0
    symbol_edges: tuple[Edge, ...]    # transitions on `symbol` that were followed
    moved_to: frozenset[str]          # move(active_before, symbol); {initial} for step 0
    epsilon_edges: tuple[Edge, ...]   # ε-transitions used to complete the closure
    active_after: frozenset[str]      # ε-closure(moved_to): the active states now
    explanation: str


@dataclass(frozen=True)
class SimulationResult:
    machine_type: str
    input_string: str
    alphabet: frozenset[str]
    initial_state: str
    accepting_states: frozenset[str]
    steps: tuple[SimulationStep, ...]
    final_states: frozenset[str]
    accepted: bool
    explanation: str

    @property
    def initial_states(self) -> frozenset[str]:
        """Active states before any input is read (step 0)."""
        return self.steps[0].active_after

    @property
    def symbols_consumed(self) -> int:
        return len(self.steps) - 1

    @property
    def accepting_final_states(self) -> frozenset[str]:
        return self.final_states & self.accepting_states


def _sorted(states) -> list[str]:
    return sorted(states, key=state_sort_key)


def _format_alphabet(alphabet) -> str:
    return "{" + ", ".join(sorted(alphabet)) + "}" if alphabet else "{} (empty)"


def _check_automaton(automaton: FiniteAutomaton) -> None:
    # A DFA must be complete so that every symbol has exactly one move; nothing is repaired.
    try:
        automaton.validate(require_complete=True)
    except AutomatonValidationError as error:
        raise SimulationError(f"Cannot simulate an invalid automaton: {error}") from error


def check_test_string(automaton: FiniteAutomaton, text: str) -> None:
    """Raise SimulationInputError unless every character of `text` is in the alphabet."""
    if not isinstance(text, str):
        raise SimulationInputError("The test string must be text.")
    if len(text) > MAX_SIMULATION_LENGTH:
        raise SimulationInputError(
            f"The test string is {len(text)} characters long; the maximum is {MAX_SIMULATION_LENGTH}."
        )
    for position, character in enumerate(text, start=1):
        if character in automaton.alphabet:
            continue
        shown = repr(character) if character.isspace() else f"'{character}'"
        message = (
            f"Invalid test string: symbol {shown} at position {position} is not in the alphabet "
            f"{_format_alphabet(automaton.alphabet)}."
        )
        if character in ("ε", "λ"):
            message += " To test the empty string, leave the test string empty."
        raise SimulationInputError(message)


def _edges(automaton: FiniteAutomaton, states, symbol: Optional[str], rank: dict) -> tuple[Edge, ...]:
    """Every transition on `symbol` leaving `states`, ordered by state (rank gives q2 before q10)."""
    return tuple(
        (source, symbol, target)
        for source in sorted(states, key=rank.__getitem__)
        for target in sorted(automaton.transitions.get((source, symbol), ()), key=rank.__getitem__)
    )


def _step_explanation(is_dfa: bool, symbol: str, before, moved, after) -> str:
    if is_dfa:
        return f"Read '{symbol}': moved from {next(iter(before))} to {next(iter(after))}."
    if not before:
        return f"Read '{symbol}': no states are active, so none remain."
    if not moved:
        return f"Read '{symbol}': no state in {format_subset(before)} has a transition on '{symbol}'; no states remain."
    if moved == after:
        return f"Read '{symbol}': from {format_subset(before)}, symbol transitions reached {format_subset(moved)}."
    return (
        f"Read '{symbol}': from {format_subset(before)}, symbol transitions reached {format_subset(moved)}; "
        f"ε-closure is {format_subset(after)}."
    )


def _final_explanation(is_dfa: bool, final_states, accepting) -> str:
    if is_dfa:
        (state,) = final_states
        if accepting:
            return f"Accepted: the entire input was consumed and the final state {state} is accepting."
        return f"Rejected: the entire input was consumed, but the final state {state} is not accepting."
    if accepting:
        names = ", ".join(_sorted(accepting))
        plural = "states" if len(accepting) > 1 else "state"
        return f"Accepted: after processing the entire input, the active-state set contains accepting {plural} {names}."
    if not final_states:
        return "Rejected: the active-state set became empty, so no transition path remains for the input."
    return (
        f"Rejected: no accepting state remains active after the entire input was consumed "
        f"(active states: {format_subset(final_states)})."
    )


def simulate(automaton: FiniteAutomaton, input_string: str) -> SimulationResult:
    """Run `input_string` on `automaton` and return the full trace and the verdict."""
    _check_automaton(automaton)
    check_test_string(automaton, input_string)
    is_dfa = automaton.machine_type == DFA
    rank = {state: index for index, state in enumerate(_sorted(automaton.states))}

    def closure_with_edges(states):
        # ε-closure (the converter's algorithm) plus every ε-transition inside it.
        closure = epsilon_closure(automaton, states)
        return closure, _edges(automaton, closure, None, rank)

    # A step depends only on (active set, symbol). Active sets repeat a lot, so each
    # distinct pair is computed once and reused; this keeps long inputs fast.
    known_steps: dict[tuple[frozenset[str], str], tuple] = {}

    def advance(before: frozenset[str], symbol: str) -> tuple:
        key = (before, symbol)
        if key not in known_steps:
            moved = move(automaton, before, symbol)
            after, epsilon_edges = closure_with_edges(moved)
            known_steps[key] = (
                _edges(automaton, before, symbol, rank),
                moved,
                epsilon_edges,
                after,
                _step_explanation(is_dfa, symbol, before, moved, after),
            )
        return known_steps[key]

    start = frozenset({automaton.initial_state})
    active, epsilon_edges = closure_with_edges(start)
    if is_dfa:
        start_text = f"Start in the initial state {automaton.initial_state}."
    else:
        start_text = f"Start: ε-closure({{{automaton.initial_state}}}) = {format_subset(active)}."
    steps = [SimulationStep(0, None, None, frozenset(), (), start, epsilon_edges, active, start_text)]

    for position, symbol in enumerate(input_string, start=1):
        before = active
        symbol_edges, moved, epsilon_edges, active, explanation = advance(before, symbol)
        steps.append(
            SimulationStep(position, position, symbol, before, symbol_edges, moved, epsilon_edges, active, explanation)
        )

    accepting = active & automaton.accepting_states
    return SimulationResult(
        machine_type=automaton.machine_type,
        input_string=input_string,
        alphabet=frozenset(automaton.alphabet),
        initial_state=automaton.initial_state,
        accepting_states=frozenset(automaton.accepting_states),
        steps=tuple(steps),
        final_states=active,
        accepted=bool(accepting),
        explanation=_final_explanation(is_dfa, active, accepting),
    )


def accepts(automaton: FiniteAutomaton, input_string: str) -> bool:
    """True if the automaton accepts the string (same engine as simulate())."""
    return simulate(automaton, input_string).accepted
