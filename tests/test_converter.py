"""
Tests for NFA-to-DFA conversion (core/converter.py).

Language equivalence is checked by running the original NFA (with the
independent test helper from test_thompson.py) and the converted DFA (with
dfa_accepts below) on the same strings and comparing the answers.
"""

import pytest

from core.automata import DFA, NFA, FiniteAutomaton
from core.converter import (
    MAX_DFA_STATES,
    ConversionError,
    convert_nfa_to_dfa,
    epsilon_closure,
    format_subset,
    move,
    regex_to_dfa,
)
from core.regex_parser import RegexSyntaxError
from core.thompson import regex_to_nfa
from test_thompson import all_strings, nfa_accepts


# --- independent test-only DFA runner -------------------------------------

def dfa_accepts(dfa: FiniteAutomaton, text: str) -> bool:
    state = dfa.initial_state
    for symbol in text:
        destinations = dfa.transitions.get((state, symbol))
        if destinations is None:
            return False  # symbol outside the alphabet
        assert len(destinations) == 1
        (state,) = destinations
    return state in dfa.accepting_states


def assert_equivalent(nfa: FiniteAutomaton, dfa: FiniteAutomaton, max_length: int = 6):
    alphabet = set(nfa.alphabet) or {"a"}  # also probe a stray symbol for empty alphabets
    for text in all_strings(alphabet, max_length):
        assert nfa_accepts(nfa, text) == dfa_accepts(dfa, text), f"mismatch on {text!r}"


def make_nfa(states, alphabet, initial, accepting, transitions) -> FiniteAutomaton:
    return FiniteAutomaton(NFA, set(states), set(alphabet), initial, set(accepting), dict(transitions))


def transition_table(dfa: FiniteAutomaton) -> dict:
    return {(s, x): next(iter(d)) for (s, x), d in dfa.transitions.items()}


def example_nfa() -> FiniteAutomaton:
    """q0 -ε-> q1, q0 -ε-> q2, q1 -a-> q3, q2 -b-> q3; accepts exactly 'a' and 'b'."""
    return make_nfa(
        ["q0", "q1", "q2", "q3"], "ab", "q0", ["q3"],
        {("q0", None): {"q1", "q2"}, ("q1", "a"): {"q3"}, ("q2", "b"): {"q3"}},
    )


# --- A: ε-closure ---------------------------------------------------------

CHAIN = make_nfa(
    ["q0", "q1", "q2", "q3", "q4"], "a", "q0", ["q4"],
    {("q0", None): {"q1"}, ("q1", None): {"q2"}, ("q2", None): {"q3"}, ("q3", "a"): {"q4"}},
)


@pytest.mark.parametrize(
    "nfa, start, expected",
    [
        (make_nfa(["q0"], "a", "q0", [], {}), {"q0"}, {"q0"}),
        (make_nfa(["q0", "q1"], "a", "q0", [], {("q0", None): {"q1"}}), {"q0"}, {"q0", "q1"}),
        (CHAIN, {"q0"}, {"q0", "q1", "q2", "q3"}),
        (CHAIN, {"q2"}, {"q2", "q3"}),
        (example_nfa(), {"q0"}, {"q0", "q1", "q2"}),
        (make_nfa(["q0", "q1"], "a", "q0", [], {("q0", None): {"q0", "q1"}}), {"q0"}, {"q0", "q1"}),
        (make_nfa(["q0", "q1", "q2"], "a", "q0", [],
                  {("q0", None): {"q1"}, ("q1", None): {"q2"}, ("q2", None): {"q0"}}), {"q1"}, {"q0", "q1", "q2"}),
        (CHAIN, {"q0", "q4"}, {"q0", "q1", "q2", "q3", "q4"}),
        (CHAIN, set(), set()),
        (make_nfa(["q0", "q1"], "a", "q0", [], {("q0", "a"): {"q1"}}), {"q0"}, {"q0"}),
    ],
    ids=["single", "one-edge", "chain", "chain-middle", "branching", "self-loop",
         "cycle", "multiple-start", "empty", "symbol-only"],
)
def test_epsilon_closure(nfa, start, expected):
    before = {key: set(value) for key, value in nfa.transitions.items()}
    result = epsilon_closure(nfa, start)
    assert result == frozenset(expected)
    assert isinstance(result, frozenset)
    assert nfa.transitions == before  # the NFA is not modified


def test_epsilon_closure_of_long_chain_has_no_recursion_limit():
    count = 5000
    states = [f"q{i}" for i in range(count)]
    transitions = {(states[i], None): {states[i + 1]} for i in range(count - 1)}
    nfa = make_nfa(states, "", "q0", [], transitions)
    assert epsilon_closure(nfa, {"q0"}) == frozenset(states)


# --- B: move --------------------------------------------------------------

MOVE_NFA = make_nfa(
    ["q0", "q1", "q2", "q3", "q4"], "ab", "q0", ["q4"],
    {
        ("q0", "a"): {"q2"},
        ("q1", "a"): {"q3", "q4"},
        ("q1", "b"): {"q0"},
        ("q0", None): {"q1"},
    },
)


@pytest.mark.parametrize(
    "start, symbol, expected",
    [
        ({"q0"}, "a", {"q2"}),
        ({"q1"}, "a", {"q3", "q4"}),
        ({"q0", "q1"}, "a", {"q2", "q3", "q4"}),
        ({"q2"}, "a", set()),
        (set(), "a", set()),
        ({"q0", "q1"}, "b", {"q0"}),
        ({"q0"}, "b", set()),  # q0 reaches q1 only by ε, which move must not follow
    ],
)
def test_move(start, symbol, expected):
    assert move(MOVE_NFA, start, symbol) == frozenset(expected)


def test_move_rejects_epsilon():
    with pytest.raises(ConversionError, match="epsilon_closure"):
        move(MOVE_NFA, {"q0"}, None)


# --- the worked example ---------------------------------------------------

def test_worked_example_conversion():
    result = convert_nfa_to_dfa(example_nfa())
    dfa = result.dfa
    assert result.state_mapping == {
        "D0": frozenset({"q0", "q1", "q2"}),
        "D1": frozenset({"q3"}),
        "D2": frozenset(),
    }
    assert transition_table(dfa) == {
        ("D0", "a"): "D1", ("D0", "b"): "D1",
        ("D1", "a"): "D2", ("D1", "b"): "D2",
        ("D2", "a"): "D2", ("D2", "b"): "D2",
    }
    assert dfa.initial_state == "D0"
    assert dfa.accepting_states == {"D1"}
    assert result.dead_state == "D2"
    for text in ["a", "b"]:
        assert dfa_accepts(dfa, text)
    for text in ["", "aa", "bb", "ab", "ba"]:
        assert not dfa_accepts(dfa, text)


def test_worked_example_trace():
    steps = convert_nfa_to_dfa(example_nfa()).steps
    rows = [
        (s.source_dfa_state, s.input_symbol, format_subset(s.move_result),
         format_subset(s.epsilon_closure_result), s.destination_dfa_state, s.is_new_state)
        for s in steps
    ]
    assert rows == [
        ("D0", "a", "{q3}", "{q3}", "D1", True),
        ("D0", "b", "{q3}", "{q3}", "D1", False),
        ("D1", "a", "∅", "∅", "D2", True),
        ("D1", "b", "∅", "∅", "D2", False),
        ("D2", "a", "∅", "∅", "D2", False),
        ("D2", "b", "∅", "∅", "D2", False),
    ]
    assert [s.number for s in steps] == [1, 2, 3, 4, 5, 6]


# --- C/D/E: regex conversions are valid DFAs equivalent to their NFAs -----

REGEXES = [
    "a", "b", "ab", "a|b", "a*", "a+", "a?", "ε",
    "(a|b)*abb", "(0|1)*01", "(ab)+", "a(b|c)*", "(a|ε)b", "((a|b)c)*", "(a|b)*(ab|ba)", "(a?b+)*",
    r"\|", r"\*", r"a\|b", r"a\.b", r"a\\b",
]


@pytest.mark.parametrize("expression", REGEXES)
def test_regex_conversion_is_valid_and_equivalent(expression):
    nfa = regex_to_nfa(expression)
    result = convert_nfa_to_dfa(nfa)
    dfa = result.dfa
    assert dfa.machine_type == DFA
    dfa.validate(require_complete=True)
    assert dfa.alphabet == nfa.alphabet
    assert all(symbol is not None for (_, symbol) in dfa.transitions)
    assert all(len(d) == 1 for d in dfa.transitions.values())
    assert_equivalent(nfa, dfa, max_length=6 if len(nfa.alphabet) <= 2 else 4)


@pytest.mark.parametrize("expression, symbol", [(r"\|", "|"), (r"\*", "*"), (r"a\|b", "|"), (r"a\.b", "."), (r"a\\b", "\\")])
def test_escaped_symbols_stay_literal(expression, symbol):
    dfa = regex_to_dfa(expression)
    assert symbol in dfa.alphabet
    literal = expression.replace("\\", "") if expression != r"a\\b" else "a\\b"
    assert dfa_accepts(dfa, literal)


# --- required acceptance scenarios on both NFA and DFA -------------------

@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a|b", ["a", "b"], ["", "ab", "ba", "aa"]),
        ("a*", ["", "a", "aa", "aaaa"], ["b", "ab"]),
        ("a+", ["a", "aa", "aaa"], ["", "b"]),
        ("(ab)+", ["ab", "abab", "ababab"], ["", "a", "aba"]),
        ("(a|b)*abb", ["abb", "aabb", "babb", "ababb"], ["", "ab", "abba", "bab"]),
        ("(0|1)*01", ["01", "101", "1101", "0001"], ["", "00", "10", "011"]),
        ("(a|ε)b", ["b", "ab"], ["", "a", "abb"]),
        ("ε", [""], ["a", "b"]),
        (r"a\|b", ["a|b"], ["a", "b", "ab"]),
    ],
)
def test_nfa_and_dfa_agree_on_required_examples(expression, accepted, rejected):
    nfa = regex_to_nfa(expression)
    dfa = convert_nfa_to_dfa(nfa).dfa
    for text in accepted:
        assert nfa_accepts(nfa, text) and dfa_accepts(dfa, text), text
    for text in rejected:
        assert not nfa_accepts(nfa, text) and not dfa_accepts(dfa, text), text


def test_classic_example_state_count():
    # (a|b)*abb gives the well-known five-state DFA from subset construction.
    result = convert_nfa_to_dfa(regex_to_nfa("(a|b)*abb"))
    assert len(result.dfa.states) == 5
    assert result.dead_state is None
    assert result.dfa.accepting_states == {"D4"}


# --- F: ε-heavy and hand-built NFAs ---------------------------------------

def test_epsilon_reachable_accepting_state_makes_start_accepting():
    nfa = make_nfa(["q0", "q1", "q2"], "a", "q0", ["q2"], {("q0", None): {"q1"}, ("q1", None): {"q2"}})
    result = convert_nfa_to_dfa(nfa)
    assert result.state_mapping["D0"] == frozenset({"q0", "q1", "q2"})
    assert result.dfa.accepting_states == {"D0"}
    assert_equivalent(nfa, result.dfa)


def test_epsilon_cycles_and_self_loops():
    nfa = make_nfa(
        ["q0", "q1", "q2", "q3"], "ab", "q0", ["q3"],
        {
            ("q0", None): {"q0", "q1"},
            ("q1", None): {"q0"},
            ("q1", "a"): {"q2"},
            ("q2", None): {"q2", "q1"},
            ("q2", "b"): {"q3"},
            ("q3", None): {"q1"},
        },
    )
    result = convert_nfa_to_dfa(nfa)
    assert result.state_mapping["D0"] == frozenset({"q0", "q1"})
    assert_equivalent(nfa, result.dfa)


def test_multiple_accepting_states_any_member_counts():
    nfa = make_nfa(
        ["q0", "q1", "q3", "q5", "q7"], "ab", "q0", ["q3", "q5"],
        {("q0", "a"): {"q1", "q3", "q7"}, ("q0", "b"): {"q7"}, ("q7", "b"): {"q5"}},
    )
    result = convert_nfa_to_dfa(nfa)
    mapping = {subset: name for name, subset in result.state_mapping.items()}
    mixed = mapping[frozenset({"q1", "q3", "q7"})]
    assert mixed in result.dfa.accepting_states  # contains q3, even though q1 and q7 are not accepting
    assert mapping[frozenset({"q7"})] not in result.dfa.accepting_states
    assert_equivalent(nfa, result.dfa)


def test_nfa_without_epsilon_transitions():
    # Classic NFA for strings whose second-to-last symbol is 'a'.
    nfa = make_nfa(
        ["q0", "q1", "q2"], "ab", "q0", ["q2"],
        {("q0", "a"): {"q0", "q1"}, ("q0", "b"): {"q0"}, ("q1", "a"): {"q2"}, ("q1", "b"): {"q2"}},
    )
    result = convert_nfa_to_dfa(nfa)
    assert result.state_mapping["D0"] == frozenset({"q0"})
    assert len(result.dfa.states) == 4
    assert result.dead_state is None
    assert_equivalent(nfa, result.dfa)


def test_nfa_with_no_accepting_states_accepts_nothing():
    nfa = make_nfa(["q0", "q1"], "a", "q0", [], {("q0", "a"): {"q1"}})
    dfa = convert_nfa_to_dfa(nfa).dfa
    assert dfa.accepting_states == set()
    assert not any(dfa_accepts(dfa, text) for text in all_strings({"a"}, 4))


def test_empty_alphabet():
    for nfa in [regex_to_nfa("ε"), make_nfa(["q0", "q1"], "", "q0", ["q1"], {("q0", None): {"q1"}})]:
        result = convert_nfa_to_dfa(nfa)
        assert result.dfa.states == {"D0"}
        assert result.dfa.transitions == {}
        assert result.dfa.accepting_states == {"D0"}
        assert result.dead_state is None
        assert result.steps == ()
        assert result.initial_closure == frozenset(nfa.states)


def test_empty_alphabet_without_acceptance():
    nfa = make_nfa(["q0", "q1"], "", "q0", ["q1"], {})
    result = convert_nfa_to_dfa(nfa)
    assert result.dfa.states == {"D0"} and result.dfa.accepting_states == set()


def test_dfa_input_is_converted_to_an_equivalent_dfa():
    dfa_in = FiniteAutomaton(DFA, {"s", "t"}, {"a"}, "s", {"t"}, {("s", "a"): {"t"}})  # partial DFA
    result = convert_nfa_to_dfa(dfa_in)
    assert len(result.dfa.states) == 3 and result.dead_state == "D2"
    assert_equivalent(dfa_in, result.dfa)


# --- G: dead state ---------------------------------------------------------

def test_dead_state_properties():
    result = convert_nfa_to_dfa(regex_to_nfa("ab"))
    dead = result.dead_state
    assert dead is not None
    assert result.state_mapping[dead] == frozenset()
    assert dead not in result.dfa.accepting_states
    for symbol in result.dfa.alphabet:
        assert result.dfa.transitions[(dead, symbol)] == {dead}
    empty_states = [name for name, subset in result.state_mapping.items() if not subset]
    assert empty_states == [dead]


@pytest.mark.parametrize("expression", ["a*", "(a|b)*", "(0|1)*01", "ε"])
def test_no_dead_state_when_unreachable(expression):
    result = convert_nfa_to_dfa(regex_to_nfa(expression))
    assert result.dead_state is None
    assert frozenset() not in result.state_mapping.values()


# --- H: reachability and duplicate prevention ----------------------------

def test_unreachable_nfa_states_are_ignored():
    nfa = make_nfa(
        ["q0", "q1", "q8", "q9"], "a", "q0", ["q1", "q9"],
        {("q0", "a"): {"q1"}, ("q8", "a"): {"q9"}, ("q9", None): {"q8"}},
    )
    result = convert_nfa_to_dfa(nfa)
    used = set().union(*result.state_mapping.values())
    assert not used & {"q8", "q9"}
    assert len(result.dfa.states) == 3


def test_subsets_are_unique_and_names_sequential():
    result = convert_nfa_to_dfa(regex_to_nfa("(a|b)*(ab|ba)"))
    subsets = list(result.state_mapping.values())
    assert len(subsets) == len(set(subsets))
    assert list(result.state_mapping) == [f"D{i}" for i in range(len(subsets))]


def test_cycles_terminate():
    nfa = make_nfa(["q0", "q1"], "ab", "q0", ["q1"],
                   {("q0", "a"): {"q1"}, ("q1", "a"): {"q0"}, ("q0", "b"): {"q0", "q1"}, ("q1", "b"): {"q1"}})
    result = convert_nfa_to_dfa(nfa)
    assert len(result.dfa.states) <= 2 ** len(nfa.states)
    assert_equivalent(nfa, result.dfa)


# --- trace correctness -----------------------------------------------------

@pytest.mark.parametrize("expression", ["(a|b)*abb", "ab", "(a?b+)*", "a|ε"])
def test_trace_is_consistent_with_algorithm(expression):
    nfa = regex_to_nfa(expression)
    result = convert_nfa_to_dfa(nfa)
    assert result.initial_closure == epsilon_closure(nfa, {nfa.initial_state})
    discovered = {"D0"}
    for step in result.steps:
        assert step.source_dfa_state in discovered
        assert result.state_mapping[step.source_dfa_state] == step.source_nfa_subset
        assert step.input_symbol in nfa.alphabet
        assert step.move_result == move(nfa, step.source_nfa_subset, step.input_symbol)
        assert step.epsilon_closure_result == epsilon_closure(nfa, step.move_result)
        assert result.state_mapping[step.destination_dfa_state] == step.epsilon_closure_result
        assert step.is_new_state == (step.destination_dfa_state not in discovered)
        discovered.add(step.destination_dfa_state)
        assert result.dfa.transitions[(step.source_dfa_state, step.input_symbol)] == {step.destination_dfa_state}
    # One step per DFA state and symbol, covering every transition.
    assert len(result.steps) == len(result.dfa.states) * len(nfa.alphabet)
    assert discovered == result.dfa.states
    # States are processed in discovery order, symbols in sorted order.
    order = [(int(s.source_dfa_state[1:]), s.input_symbol) for s in result.steps]
    assert order == sorted(order)


# --- I: determinism ------------------------------------------------------

def test_conversion_is_deterministic():
    first = convert_nfa_to_dfa(regex_to_nfa("(a|b)*(ab|ba)"))
    convert_nfa_to_dfa(regex_to_nfa("(0|1)*01"))  # an unrelated conversion in between
    second = convert_nfa_to_dfa(regex_to_nfa("(a|b)*(ab|ba)"))
    assert first.state_mapping == second.state_mapping
    assert first.dfa == second.dfa
    assert first.steps == second.steps


def test_conversion_does_not_modify_nfa():
    nfa = regex_to_nfa("(a|b)*abb")
    before = regex_to_nfa("(a|b)*abb")
    convert_nfa_to_dfa(nfa)
    assert nfa == before


# --- J: invalid inputs ---------------------------------------------------

@pytest.mark.parametrize(
    "nfa, message",
    [
        (FiniteAutomaton("PDA", {"q0"}, {"a"}, "q0", set()), "Invalid machine type"),
        (make_nfa(["q0"], "a", "q9", [], {}), "Initial state 'q9'"),
        (make_nfa(["q0"], "a", "q0", [], {("q0", "a"): {"q7"}}), "unknown state 'q7'"),
        (make_nfa(["q0"], "a", "q0", [], {("q0", "b"): {"q0"}}), "not in the alphabet"),
        (make_nfa(["q0"], "a", "q0", ["q5"], {}), "Accepting state 'q5'"),
        (make_nfa(["q0"], "a", "q0", [], {("q0", "a"): ["q0"]}), "must be a set"),
    ],
)
def test_invalid_automata_are_rejected(nfa, message):
    with pytest.raises(ConversionError, match=message):
        convert_nfa_to_dfa(nfa)


def test_state_limit():
    # "The 6th symbol from the end is 'a'" needs at least 2**6 DFA states. Subset
    # construction gives 65: the start subset is never re-entered, and the DFA is not minimized.
    nfa = regex_to_nfa("(a|b)*a(a|b)(a|b)(a|b)(a|b)(a|b)")
    with pytest.raises(ConversionError, match="more than 20 states"):
        convert_nfa_to_dfa(nfa, max_states=20)
    dfa = convert_nfa_to_dfa(nfa).dfa
    assert len(dfa.states) == 65 <= MAX_DFA_STATES
    assert_equivalent(nfa, dfa, max_length=8)


def test_regex_to_dfa_propagates_syntax_errors():
    with pytest.raises(RegexSyntaxError):
        regex_to_dfa("a||b")


def test_conversion_error_is_value_error():
    assert issubclass(ConversionError, ValueError)
