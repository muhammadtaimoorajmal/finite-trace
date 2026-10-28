"""
Structured language rules and exact strings -> complete DFAs.

Each rule is built by a general algorithm from the user's parameters
(alphabet, pattern, symbol, count); nothing is looked up from a list of
known answers.

    starts_with     states count how much of the prefix has matched; a mismatch goes to a dead state
    ends_with       pattern-matching states (see below); accepting only while the input ends with the pattern
    contains        the same states, but the full-match state is absorbing
    not_contains    complement of contains   (swap accepting states of a complete DFA)
    not_ends_with   complement of ends_with
    even_count      two parity states toggled by the chosen symbol
    odd_count       the same two states with acceptance swapped
    exact_count     states 0..k count occurrences, plus an overflow state for more than k
    exact string    a chain of states for the characters, then a dead state

Pattern-matching states: state i means "the last i characters read are the
first i characters of the pattern, and i is as large as possible". After
reading x in state i, the new state is the length of the longest prefix of
the pattern that is a suffix of pattern[:i] + x. This is the idea behind the
Knuth-Morris-Pratt string-matching automaton and handles overlapping
patterns such as 'aba' in 'ababa'.

Every result is a complete DFA with states q0, q1, ... A state that cannot be
reached (for example a dead state no symbol leads to) is left out.
"""

from dataclasses import dataclass, field

from core.automata import DFA, NFA, AutomatonValidationError, FiniteAutomaton
from core.manual_builder import MAX_ALPHABET_SIZE

STARTS_WITH = "starts_with"
ENDS_WITH = "ends_with"
CONTAINS = "contains"
NOT_CONTAINS = "not_contains"
NOT_ENDS_WITH = "not_ends_with"
EVEN_COUNT = "even_count"
ODD_COUNT = "odd_count"
EXACT_COUNT = "exact_count"

# Rule id -> (label for the interface, which parameter it needs).
RULES = {
    STARTS_WITH: ("Starts with", "pattern"),
    ENDS_WITH: ("Ends with", "pattern"),
    CONTAINS: ("Contains substring", "pattern"),
    NOT_CONTAINS: ("Does not contain substring", "pattern"),
    NOT_ENDS_WITH: ("Does not end with", "pattern"),
    EVEN_COUNT: ("Even number of a symbol", "symbol"),
    ODD_COUNT: ("Odd number of a symbol", "symbol"),
    EXACT_COUNT: ("Exactly k occurrences of a symbol", "count"),
}

MAX_PATTERN_LENGTH = 50
MAX_EXACT_STRING_LENGTH = 100
MAX_COUNT = 100


class LanguageRuleError(ValueError):
    """Raised for unsupported rules or invalid rule parameters."""


@dataclass(frozen=True)
class LanguageAutomaton:
    """A generated automaton plus a plain-English description and the meaning of each state."""

    automaton: FiniteAutomaton
    description: str
    state_notes: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parameter checks
# ---------------------------------------------------------------------------

def _check_alphabet(alphabet) -> list[str]:
    if len(alphabet) > MAX_ALPHABET_SIZE:
        raise LanguageRuleError(f"The alphabet has {len(alphabet)} symbols; the maximum is {MAX_ALPHABET_SIZE}.")
    for symbol in alphabet:
        if not isinstance(symbol, str) or len(symbol) != 1 or symbol.isspace() or symbol in ",ελ":
            raise LanguageRuleError(f"Invalid alphabet symbol {symbol!r}: use single non-space characters.")
    return sorted(alphabet)


def _check_text(text: str, alphabet, what: str, max_length: int, allow_empty: bool) -> None:
    if not isinstance(text, str):
        raise LanguageRuleError(f"The {what} must be text.")
    if not text and not allow_empty:
        raise LanguageRuleError(f"Enter a {what}; this rule needs at least one symbol.")
    if len(text) > max_length:
        raise LanguageRuleError(f"The {what} is {len(text)} characters long; the maximum is {max_length}.")
    for position, character in enumerate(text, start=1):
        if character not in alphabet:
            raise LanguageRuleError(
                f"The {what} contains '{character}' at position {position}, which is not in the alphabet."
            )


def _check_symbol(symbol, alphabet) -> None:
    if not symbol:
        raise LanguageRuleError("Choose the symbol to count.")
    if not isinstance(symbol, str) or len(symbol) != 1:
        raise LanguageRuleError(f"The counted symbol must be a single character, not {symbol!r}.")
    if symbol not in alphabet:
        raise LanguageRuleError(f"The counted symbol '{symbol}' is not in the alphabet.")


def _check_count(count) -> None:
    if isinstance(count, bool) or not isinstance(count, int):
        raise LanguageRuleError(f"The count must be a whole number, not {count!r}.")
    if not 0 <= count <= MAX_COUNT:
        raise LanguageRuleError(f"The count must be between 0 and {MAX_COUNT}; got {count}.")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_dfa(state_count, delta, accepting, alphabet, notes) -> tuple[FiniteAutomaton, dict[str, str]]:
    """
    Turn numbered states (0 is initial) and delta[(i, x)] = j into a FiniteAutomaton
    named q0, q1, ... Unreachable states are dropped; reachable ones keep their order.
    """
    symbols = sorted(alphabet)
    reachable = {0}
    pending = [0]
    while pending:
        state = pending.pop()
        for symbol in symbols:
            target = delta[(state, symbol)]
            if target not in reachable:
                reachable.add(target)
                pending.append(target)

    kept = [i for i in range(state_count) if i in reachable]
    name = {old: f"q{new}" for new, old in enumerate(kept)}
    automaton = FiniteAutomaton(
        machine_type=DFA,
        states=set(name.values()),
        alphabet=set(alphabet),
        initial_state="q0",
        accepting_states={name[i] for i in accepting if i in reachable},
        transitions={(name[i], x): {name[delta[(i, x)]]} for i in kept for x in symbols},
    )
    try:
        automaton.validate(require_complete=True)
    except AutomatonValidationError as error:  # would indicate a bug in a constructor
        raise LanguageRuleError(f"Generated DFA is invalid: {error}") from error
    return automaton, {name[i]: notes[i] for i in kept}


def _longest_prefix_suffix(pattern: str, text: str) -> int:
    """Length of the longest prefix of `pattern` that is also a suffix of `text`."""
    for length in range(min(len(pattern), len(text)), 0, -1):
        if text.endswith(pattern[:length]):
            return length
    return 0


def _pattern_states(pattern: str, symbols, absorbing: bool) -> dict:
    """delta for the pattern-matching states 0..m. If absorbing, state m loops to itself."""
    m = len(pattern)
    delta = {}
    for i in range(m + 1):
        for x in symbols:
            if i == m and absorbing:
                delta[(i, x)] = m
            else:
                delta[(i, x)] = _longest_prefix_suffix(pattern, pattern[:i] + x)
    return delta


def _matched_notes(pattern: str) -> list[str]:
    return ["nothing matched yet"] + [f"matched '{pattern[:i]}'" for i in range(1, len(pattern) + 1)]


def _quote(text: str) -> str:
    return f"'{text}'" if text else "ε (the empty string)"


# ---------------------------------------------------------------------------
# Rule constructors (return state count, delta, accepting set, notes)
# ---------------------------------------------------------------------------

def _starts_with(pattern, symbols):
    m = len(pattern)
    dead = m + 1
    delta = {}
    for i in range(m):
        for x in symbols:
            delta[(i, x)] = i + 1 if x == pattern[i] else dead
    for x in symbols:
        delta[(m, x)] = m        # prefix complete: accept anything after it
        delta[(dead, x)] = dead
    notes = _matched_notes(pattern)
    notes[m] = f"prefix '{pattern}' complete"
    return m + 2, delta, {m}, notes + ["dead: prefix did not match"]


def _ends_with(pattern, symbols):
    m = len(pattern)
    notes = _matched_notes(pattern)
    notes[m] = f"input ends with '{pattern}'"
    return m + 1, _pattern_states(pattern, symbols, absorbing=False), {m}, notes


def _contains(pattern, symbols):
    m = len(pattern)
    notes = _matched_notes(pattern)
    notes[m] = f"'{pattern}' found (stays accepting)"
    return m + 1, _pattern_states(pattern, symbols, absorbing=True), {m}, notes


def _complement(state_count, delta, accepting, notes):
    # Valid because the DFA is complete: every string ends in exactly one state.
    return state_count, delta, set(range(state_count)) - set(accepting), notes


def _parity(symbol, symbols, accept_odd: bool):
    delta = {}
    for x in symbols:
        delta[(0, x)] = 1 if x == symbol else 0
        delta[(1, x)] = 0 if x == symbol else 1
    notes = [f"even number of '{symbol}' so far", f"odd number of '{symbol}' so far"]
    return 2, delta, {1} if accept_odd else {0}, notes


def _exact_count(symbol, count, symbols):
    overflow = count + 1
    delta = {}
    for i in range(count + 2):
        for x in symbols:
            if x == symbol:
                delta[(i, x)] = min(i + 1, overflow)
            else:
                delta[(i, x)] = i
    notes = [f"{i} × '{symbol}' so far" for i in range(count + 1)] + [f"more than {count} × '{symbol}' (dead)"]
    return count + 2, delta, {count}, notes


def build_language(rule: str, alphabet, pattern: str = "", symbol=None, count=None) -> LanguageAutomaton:
    """Build the complete DFA for a structured language rule."""
    if rule not in RULES:
        raise LanguageRuleError(f"Unsupported language rule {rule!r}. Choose one of: {', '.join(RULES)}.")
    symbols = _check_alphabet(alphabet)
    sigma = "{" + ", ".join(symbols) + "}"
    needs = RULES[rule][1]
    if needs == "pattern":
        _check_text(pattern, alphabet, "pattern", MAX_PATTERN_LENGTH, allow_empty=False)
    elif needs in ("symbol", "count"):
        _check_symbol(symbol, alphabet)
        if needs == "count":
            _check_count(count)

    if rule == STARTS_WITH:
        parts, description = _starts_with(pattern, symbols), f"All strings over {sigma} that start with '{pattern}'."
    elif rule == ENDS_WITH:
        parts, description = _ends_with(pattern, symbols), f"All strings over {sigma} that end with '{pattern}'."
    elif rule == CONTAINS:
        parts, description = _contains(pattern, symbols), f"All strings over {sigma} that contain '{pattern}'."
    elif rule == NOT_CONTAINS:
        parts = _complement(*_contains(pattern, symbols))
        description = f"All strings over {sigma} that do not contain '{pattern}'."
    elif rule == NOT_ENDS_WITH:
        parts = _complement(*_ends_with(pattern, symbols))
        description = f"All strings over {sigma} that do not end with '{pattern}'."
    elif rule in (EVEN_COUNT, ODD_COUNT):
        odd = rule == ODD_COUNT
        parts = _parity(symbol, symbols, accept_odd=odd)
        description = f"All strings over {sigma} with an {'odd' if odd else 'even'} number of '{symbol}'."
    else:  # EXACT_COUNT
        parts = _exact_count(symbol, count, symbols)
        description = f"All strings over {sigma} with exactly {count} occurrence(s) of '{symbol}'."

    automaton, notes = _make_dfa(*parts[:3], alphabet, parts[3])
    return LanguageAutomaton(automaton, description, notes)


def build_language_dfa(rule: str, alphabet, pattern: str = "", symbol=None, count=None) -> FiniteAutomaton:
    """Shortcut returning only the DFA for a language rule."""
    return build_language(rule, alphabet, pattern, symbol, count).automaton


def build_exact_string(text: str, alphabet) -> LanguageAutomaton:
    """DFA accepting exactly `text` (taken literally, never as a regular expression)."""
    symbols = _check_alphabet(alphabet)
    _check_text(text, alphabet, "exact string", MAX_EXACT_STRING_LENGTH, allow_empty=True)
    n = len(text)
    dead = n + 1
    delta = {}
    for i in range(n + 2):
        for x in symbols:
            delta[(i, x)] = i + 1 if i < n and x == text[i] else dead
    notes = _matched_notes(text) if text else ["nothing read yet"]
    notes[n] = f"read exactly {_quote(text)}"
    notes.append("dead: input differs from the string")
    automaton, state_notes = _make_dfa(n + 2, delta, {n}, alphabet, notes)
    sigma = "{" + ", ".join(symbols) + "}"
    return LanguageAutomaton(automaton, f"Only the string {_quote(text)} over {sigma}.", state_notes)


def build_exact_string_dfa(text: str, alphabet) -> FiniteAutomaton:
    return build_exact_string(text, alphabet).automaton


def as_nfa(dfa: FiniteAutomaton) -> FiniteAutomaton:
    """
    The same machine labelled as an NFA. Every DFA is an NFA whose transitions
    each have exactly one destination and no ε-moves. All sets are copied, so
    changing one automaton never affects the other.
    """
    return FiniteAutomaton(
        machine_type=NFA,
        states=set(dfa.states),
        alphabet=set(dfa.alphabet),
        initial_state=dfa.initial_state,
        accepting_states=set(dfa.accepting_states),
        transitions={key: set(destinations) for key, destinations in dfa.transitions.items()},
    )
