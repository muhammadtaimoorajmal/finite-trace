"""
Thompson's construction: regular expression -> ε-NFA.

The parser (core/regex_parser.py) produces the expression in postfix order.
This module reads that postfix sequence left to right with a stack of NFA
*fragments*. A fragment is a partial NFA with one entry state (start) and one
exit state (end). Every rule below creates or joins fragments; ε-transitions
(stored with the symbol None) glue them together without consuming input.

    literal x    start --x--> end                            2 new states
    ε            start --ε--> end                            2 new states
    A.B          A.end --ε--> B.start                        no new states
    A|B          s --ε--> A.start, s --ε--> B.start,
                 A.end --ε--> e, B.end --ε--> e              2 new states
    A*           s --ε--> A.start, s --ε--> e,
                 A.end --ε--> A.start, A.end --ε--> e        2 new states
    A+           like A* but without s --ε--> e              2 new states
    A?           like A* but without the A.end --ε--> A.start loop

When the postfix sequence is consumed, exactly one fragment remains: its start
is the NFA's initial state and its end is the single accepting state.

States are named q0, q1, q2, ... in creation order, so the same expression
always produces the same automaton.
"""

from dataclasses import dataclass, field
from typing import Optional

from core.automata import NFA, AutomatonValidationError, FiniteAutomaton, display_symbol
from core.regex_parser import (
    CONCAT,
    EPSILON,
    LITERAL,
    OPERATOR_ARITY,
    OPTIONAL,
    PLUS,
    STAR,
    UNION,
    ParsedRegex,
    Token,
    parse_regex,
)

# Safety limit on generated states. With the parser's 512-character limit a
# valid expression yields at most about 1,024 states, so this only guards
# against unexpected input passed to construct_nfa() directly.
MAX_NFA_STATES = 1500

OPERATION_NAMES = {
    LITERAL: "Literal",
    EPSILON: "Epsilon",
    CONCAT: "Concatenation",
    UNION: "Union",
    STAR: "Kleene star",
    PLUS: "Kleene plus",
    OPTIONAL: "Optional",
}


class ConstructionError(ValueError):
    """Raised when a postfix sequence cannot be turned into an NFA."""


@dataclass(frozen=True)
class NFAFragment:
    """A partial NFA with a single entry state and a single exit state."""

    start: str
    end: str


@dataclass(frozen=True)
class ConstructionStep:
    """One postfix token processed during construction, for the educational trace."""

    number: int
    token: str                  # display form of the postfix token
    operation: str
    explanation: str
    fragment: NFAFragment       # the fragment pushed by this step
    new_transitions: tuple[tuple[str, Optional[str], str], ...]
    stack_depth: int            # fragments on the stack after this step


@dataclass(frozen=True)
class ConstructionResult:
    automaton: FiniteAutomaton
    steps: tuple[ConstructionStep, ...]


class _Builder:
    """
    Holds everything for one construction: the state counter, states and
    transitions. A new builder is created per call, so separate constructions
    never share state (important because Streamlit reruns the script).
    """

    def __init__(self, max_states: int):
        self.max_states = max_states
        self.states: list[str] = []
        self.transitions: dict[tuple[str, Optional[str]], set[str]] = {}
        self.step_transitions: list[tuple[str, Optional[str], str]] = []

    def new_state(self) -> str:
        if len(self.states) >= self.max_states:
            raise ConstructionError(
                f"The NFA would need more than {self.max_states} states. Try a shorter expression."
            )
        state = f"q{len(self.states)}"
        self.states.append(state)
        return state

    def connect(self, source: str, symbol: Optional[str], destination: str) -> None:
        self.transitions.setdefault((source, symbol), set()).add(destination)
        self.step_transitions.append((source, symbol, destination))

    # --- one method per Thompson rule ------------------------------------

    def symbol_fragment(self, symbol: Optional[str]) -> NFAFragment:
        start, end = self.new_state(), self.new_state()
        self.connect(start, symbol, end)
        return NFAFragment(start, end)

    def concatenate(self, first: NFAFragment, second: NFAFragment) -> NFAFragment:
        self.connect(first.end, None, second.start)
        return NFAFragment(first.start, second.end)

    def union(self, first: NFAFragment, second: NFAFragment) -> NFAFragment:
        start, end = self.new_state(), self.new_state()
        self.connect(start, None, first.start)
        self.connect(start, None, second.start)
        self.connect(first.end, None, end)
        self.connect(second.end, None, end)
        return NFAFragment(start, end)

    def repeat(self, inner: NFAFragment, allow_skip: bool, allow_loop: bool) -> NFAFragment:
        """Star (skip + loop), plus (loop only) and optional (skip only)."""
        start, end = self.new_state(), self.new_state()
        self.connect(start, None, inner.start)
        if allow_skip:
            self.connect(start, None, end)  # zero occurrences
        if allow_loop:
            self.connect(inner.end, None, inner.start)  # one more occurrence
        self.connect(inner.end, None, end)
        return NFAFragment(start, end)


def _span(fragment: NFAFragment) -> str:
    return f"{fragment.start}…{fragment.end}"


def _apply_token(builder: _Builder, token: Token, operands: list[NFAFragment]) -> tuple[NFAFragment, str]:
    """Build the fragment for one token from its operands; return it with an explanation."""
    if token.kind == LITERAL:
        fragment = builder.symbol_fragment(token.value)
        return fragment, f"New fragment {fragment.start} --{token.value}--> {fragment.end}."

    if token.kind == EPSILON:
        fragment = builder.symbol_fragment(None)
        return fragment, f"New fragment {fragment.start} --ε--> {fragment.end} (matches the empty string)."

    if token.kind == CONCAT:
        first, second = operands
        fragment = builder.concatenate(first, second)
        return fragment, (
            f"Join {_span(first)} then {_span(second)} with ε from {first.end} to {second.start}."
        )

    if token.kind == UNION:
        first, second = operands
        fragment = builder.union(first, second)
        return fragment, (
            f"New start {fragment.start} branches by ε to {first.start} and {second.start}; "
            f"{first.end} and {second.end} lead by ε to new end {fragment.end}."
        )

    (inner,) = operands
    if token.kind == STAR:
        fragment = builder.repeat(inner, allow_skip=True, allow_loop=True)
        detail = f"ε skip {fragment.start}→{fragment.end} allows zero repetitions; ε loop {inner.end}→{inner.start} allows more."
    elif token.kind == PLUS:
        fragment = builder.repeat(inner, allow_skip=False, allow_loop=True)
        detail = f"No skip, so {_span(inner)} must match at least once; ε loop {inner.end}→{inner.start} allows more."
    else:  # OPTIONAL
        fragment = builder.repeat(inner, allow_skip=True, allow_loop=False)
        detail = f"ε skip {fragment.start}→{fragment.end} allows zero occurrences; no loop, so at most one."
    return fragment, f"Wrap {_span(inner)} in new states {fragment.start}, {fragment.end}. {detail}"


def construct_nfa(parsed: ParsedRegex, max_states: int = MAX_NFA_STATES) -> ConstructionResult:
    """Run Thompson's construction on a parsed expression's postfix tokens."""
    builder = _Builder(max_states)
    stack: list[NFAFragment] = []
    steps: list[ConstructionStep] = []

    for number, token in enumerate(parsed.postfix, start=1):
        if token.kind not in OPERATION_NAMES:
            raise ConstructionError(
                f"Token {token.display!r} ({token.kind}) at postfix step {number} cannot appear in a postfix expression."
            )

        arity = OPERATOR_ARITY.get(token.kind, 0)
        if len(stack) < arity:
            raise ConstructionError(
                f"Operator {token.display!r} at postfix step {number} needs {arity} operand(s) "
                f"but only {len(stack)} available; the postfix sequence is malformed."
            )
        # Pop operands; for binary operators the second operand is on top.
        operands = stack[len(stack) - arity:]
        del stack[len(stack) - arity:]

        builder.step_transitions = []
        fragment, explanation = _apply_token(builder, token, operands)
        stack.append(fragment)
        steps.append(
            ConstructionStep(
                number=number,
                token=token.display,
                operation=OPERATION_NAMES[token.kind],
                explanation=explanation,
                fragment=fragment,
                new_transitions=tuple(builder.step_transitions),
                stack_depth=len(stack),
            )
        )

    if len(stack) != 1:
        raise ConstructionError(
            f"The postfix sequence left {len(stack)} fragments instead of exactly 1; "
            "it is missing operands or operators."
        )

    final = stack[0]
    automaton = FiniteAutomaton(
        machine_type=NFA,
        states=set(builder.states),
        alphabet=set(parsed.alphabet),
        initial_state=final.start,
        accepting_states={final.end},
        transitions=builder.transitions,
    )
    try:
        automaton.validate()
    except AutomatonValidationError as error:
        raise ConstructionError(f"The constructed NFA is invalid: {error}") from error

    return ConstructionResult(automaton=automaton, steps=tuple(steps))


def regex_to_nfa(expression: str) -> FiniteAutomaton:
    """Parse a regular expression and return its Thompson ε-NFA."""
    return construct_nfa(parse_regex(expression)).automaton


def format_transition(source: str, symbol: Optional[str], destination: str) -> str:
    return f"{source} --{display_symbol(symbol)}--> {destination}"
