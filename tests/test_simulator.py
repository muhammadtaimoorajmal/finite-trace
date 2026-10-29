"""
Tests for the production simulator (core/simulator.py).

Expected verdicts come from independent sources: hand-specified examples,
plain Python predicates describing each language, and the separate test-only
runners nfa_accepts / dfa_accepts from earlier modules. check_trace() verifies
every recorded step against the automaton directly.
"""

import pytest

from core.automata import DFA, NFA, FiniteAutomaton
from core.converter import convert_nfa_to_dfa, regex_to_dfa
from core.language_builder import (
    CONTAINS,
    ENDS_WITH,
    EVEN_COUNT,
    EXACT_COUNT,
    NOT_CONTAINS,
    ODD_COUNT,
    STARTS_WITH,
    as_nfa,
    build_exact_string_dfa,
    build_language_dfa,
)
from core.manual_builder import parse_and_build
from core.simulator import (
    MAX_SIMULATION_LENGTH,
    SimulationError,
    SimulationInputError,
    accepts,
    simulate,
)
from core.thompson import regex_to_nfa
from test_converter import dfa_accepts
from test_thompson import all_strings, nfa_accepts


def make(machine_type, states, alphabet, initial, accepting, transitions) -> FiniteAutomaton:
    return FiniteAutomaton(machine_type, set(states), set(alphabet), initial, set(accepting), dict(transitions))


def reachable_by_epsilon(automaton, states):
    """Independent ε-closure (breadth-first, written separately from the converter's)."""
    seen, frontier = set(states), list(states)
    while frontier:
        nxt = []
        for state in frontier:
            for target in automaton.transitions.get((state, None), ()):
                if target not in seen:
                    seen.add(target)
                    nxt.append(target)
        frontier = nxt
    return seen


def check_trace(automaton, text, result):
    """Check every step of a trace against the automaton itself."""
    steps = result.steps
    assert len(steps) == len(text) + 1 == result.symbols_consumed + 1
    start = steps[0]
    assert (start.index, start.position, start.symbol) == (0, None, None)
    assert start.moved_to == {automaton.initial_state}
    assert start.active_after == reachable_by_epsilon(automaton, {automaton.initial_state})
    for step in steps:
        for source, symbol, target in step.epsilon_edges:
            assert symbol is None and target in automaton.transitions[(source, None)]
            assert source in step.active_after and target in step.active_after
        assert step.active_after <= automaton.states
        if automaton.machine_type == DFA:
            assert len(step.active_after) == 1
    for i, step in enumerate(steps[1:], start=1):
        assert (step.index, step.position, step.symbol) == (i, i, text[i - 1])
        assert step.active_before == steps[i - 1].active_after
        expected_moved = set()
        for source in step.active_before:
            expected_moved |= automaton.transitions.get((source, step.symbol), set())
        assert step.moved_to == expected_moved
        assert {t for _, _, t in step.symbol_edges} == expected_moved
        for source, symbol, target in step.symbol_edges:
            assert symbol == step.symbol and source in step.active_before
            assert target in automaton.transitions[(source, symbol)]
        assert step.active_after == reachable_by_epsilon(automaton, step.moved_to)
    assert result.final_states == steps[-1].active_after
    assert result.accepted == bool(result.final_states & automaton.accepting_states)


def run(automaton, text):
    result = simulate(automaton, text)
    check_trace(automaton, text, result)
    return result


EVEN_ZEROS = make(DFA, ["q0", "q1"], "01", "q0", ["q0"],
                  {("q0", "0"): {"q1"}, ("q0", "1"): {"q0"}, ("q1", "0"): {"q0"}, ("q1", "1"): {"q1"}})
EPSILON_NFA = make(NFA, ["q0", "q1", "q2", "q3"], "ab", "q0", ["q3"],
                   {("q0", None): {"q1", "q2"}, ("q1", "a"): {"q3"}, ("q2", "b"): {"q3"}})


# --- A: DFA simulation ------------------------------------------------------------

def test_dfa_state_sequence():
    result = run(EVEN_ZEROS, "1010")
    sequence = [next(iter(s.active_after)) for s in result.steps]
    assert sequence == ["q0", "q0", "q1", "q1", "q0"]
    assert [s.symbol_edges for s in result.steps[1:]] == [
        (("q0", "1", "q0"),), (("q0", "0", "q1"),), (("q1", "1", "q1"),), (("q1", "0", "q0"),),
    ]
    assert result.accepted
    assert result.explanation == "Accepted: the entire input was consumed and the final state q0 is accepting."
    assert result.steps[2].explanation == "Read '0': moved from q0 to q1."


@pytest.mark.parametrize("text, accepted", [("1", True), ("0", False), ("00", True), ("000", False), ("1101", False)])
def test_dfa_single_and_multiple_characters(text, accepted):
    assert run(EVEN_ZEROS, text).accepted is accepted


def test_dfa_rejection_explanation():
    result = run(EVEN_ZEROS, "0")
    assert result.explanation == "Rejected: the entire input was consumed, but the final state q1 is not accepting."


def test_dfa_dead_state_and_self_loops():
    dfa = regex_to_dfa("ab")  # has a dead state
    result = run(dfa, "ba")
    assert not result.accepted
    assert len({next(iter(s.active_after)) for s in result.steps[1:]}) == 1  # stuck in the dead state


def test_one_state_dfa_and_multiple_accepting_states():
    one = make(DFA, ["s"], "a", "s", ["s"], {("s", "a"): {"s"}})
    assert run(one, "aaa").accepted
    multi = make(DFA, ["x", "y", "z"], "a", "x", ["y", "z"], {("x", "a"): {"y"}, ("y", "a"): {"z"}, ("z", "a"): {"x"}})
    assert [run(multi, "a" * n).accepted for n in range(4)] == [False, True, True, False]


# --- B: empty string ------------------------------------------------------------

def test_empty_string_cases():
    assert run(EVEN_ZEROS, "").accepted
    assert not run(make(DFA, ["p", "q"], "a", "p", ["q"], {("p", "a"): {"q"}, ("q", "a"): {"q"}}), "").accepted
    assert run(make(NFA, ["a", "b", "c"], "x", "a", ["c"], {("a", None): {"b"}, ("b", None): {"c"}}), "").accepted
    assert not run(EPSILON_NFA, "").accepted
    assert run(regex_to_nfa("ε"), "").accepted
    assert run(regex_to_nfa("a*"), "").accepted
    assert not run(regex_to_nfa("a+"), "").accepted
    assert run(build_exact_string_dfa("", {"a", "b"}), "").accepted


def test_empty_string_trace_has_only_initial_configuration():
    result = run(regex_to_nfa("a*"), "")
    assert len(result.steps) == 1 and result.symbols_consumed == 0
    assert result.initial_states == result.final_states


# --- C: NFA ------------------------------------------------------------------------

BRANCHING = make(NFA, ["q0", "q1", "q2"], "ab", "q0", ["q2"], {("q0", "a"): {"q1", "q2"}, ("q1", "b"): {"q1"}})


def test_multiple_destinations_and_one_accepting_branch():
    result = run(BRANCHING, "a")
    assert result.final_states == {"q1", "q2"}
    assert result.accepted
    assert result.steps[1].symbol_edges == (("q0", "a", "q1"), ("q0", "a", "q2"))
    assert result.explanation == (
        "Accepted: after processing the entire input, the active-state set contains accepting state q2."
    )


def test_all_branches_rejecting_after_earlier_acceptance():
    # q2 was active (accepting) after 'a', but only q1 survives 'b'.
    result = run(BRANCHING, "ab")
    assert result.final_states == {"q1"}
    assert not result.accepted


def test_empty_active_set_continues_to_end_of_input():
    nfa = make(NFA, ["q0", "q1"], "ab", "q0", ["q1"], {("q0", "a"): {"q1"}})
    result = run(nfa, "abab")
    assert [s.active_after for s in result.steps] == [{"q0"}, {"q1"}, set(), set(), set()]
    assert not result.accepted
    assert "no transition path remains" in result.explanation
    assert result.steps[2].explanation == "Read 'b': no state in {q1} has a transition on 'b'; no states remain."
    assert result.steps[3].explanation == "Read 'a': no states are active, so none remain."


def test_several_accepting_states_reported():
    nfa = make(NFA, ["s", "t", "u"], "a", "s", ["t", "u"], {("s", "a"): {"t", "u"}})
    result = run(nfa, "a")
    assert result.accepting_final_states == {"t", "u"}
    assert "accepting states t, u" in result.explanation


# --- D: ε-NFAs ---------------------------------------------------------------------

def test_initial_epsilon_closure_and_symbol_step():
    result = run(EPSILON_NFA, "a")
    assert result.initial_states == {"q0", "q1", "q2"}
    assert result.steps[0].epsilon_edges == (("q0", None, "q1"), ("q0", None, "q2"))
    assert result.steps[1].moved_to == {"q3"} and result.final_states == {"q3"}
    assert result.accepted


def test_epsilon_cycles_self_loops_and_chains_terminate():
    nfa = make(
        NFA, ["q0", "q1", "q2", "q3", "q4"], "a", "q0", ["q4"],
        {("q0", None): {"q0", "q1"}, ("q1", None): {"q2"}, ("q2", None): {"q0"},
         ("q2", "a"): {"q3"}, ("q3", None): {"q3", "q4"}, ("q4", None): {"q3"}},
    )
    result = run(nfa, "a")
    assert result.initial_states == {"q0", "q1", "q2"}
    assert result.final_states == {"q3", "q4"}
    assert result.accepted
    assert len(result.steps[0].epsilon_edges) == len(set(result.steps[0].epsilon_edges))  # no repeats


def test_epsilon_after_symbol_reaches_multiple_accepting_states():
    nfa = make(NFA, ["s", "m", "f1", "f2"], "a", "s", ["f1", "f2"],
               {("s", "a"): {"m"}, ("m", None): {"f1", "f2"}})
    result = run(nfa, "a")
    assert result.steps[1].moved_to == {"m"}
    assert result.final_states == {"m", "f1", "f2"}
    assert result.accepting_final_states == {"f1", "f2"}


# --- regular expressions (NFA and DFA) ------------------------------------------

REGEX_CASES = [
    ("a|b", ["a", "b"], ["", "ab", "ba"]),
    ("a*", ["", "a", "aa", "aaaa"], ["b", "ab"]),
    ("a+", ["a", "aa", "aaa"], ["", "b"]),
    ("a?", ["", "a"], ["aa", "b"]),
    ("(ab)+", ["ab", "abab", "ababab"], ["", "a", "aba"]),
    ("(a|b)*abb", ["abb", "aabb", "babb", "ababb"], ["", "ab", "abba", "bab"]),
    ("(0|1)*01", ["01", "101", "1101", "0001"], ["", "00", "10", "011"]),
    ("(a|ε)b", ["b", "ab"], ["", "a", "abb"]),
    ("ε", [""], []),
    (r"a\|b", ["a|b"], ["a", "ab", "b"]),
]


@pytest.mark.parametrize("expression, accepted, rejected", REGEX_CASES)
@pytest.mark.parametrize("machine", ["NFA", "DFA"])
def test_regex_examples(machine, expression, accepted, rejected):
    automaton = regex_to_nfa(expression) if machine == "NFA" else regex_to_dfa(expression)
    for text in accepted:
        assert run(automaton, text).accepted, text
    for text in rejected:
        if set(text) <= automaton.alphabet:
            assert not run(automaton, text).accepted, text
        else:
            # e.g. 'b' for a* (alphabet {a}): outside the alphabet, so invalid rather than rejected.
            with pytest.raises(SimulationInputError, match="not in the alphabet"):
                simulate(automaton, text)


@pytest.mark.parametrize("text", ["a", "b"])
def test_epsilon_regex_rejects_symbols_as_invalid_input(text):
    # The alphabet of ε is empty, so any character is outside it.
    with pytest.raises(SimulationInputError, match="not in the alphabet {} \\(empty\\)"):
        simulate(regex_to_nfa("ε"), text)


# --- language rules, exact strings and manual automata -----------------------

B = {"0", "1"}
RULE_CASES = [
    (STARTS_WITH, {"pattern": "10"}, ["10", "101", "1000"], ["", "1", "010"]),
    (ENDS_WITH, {"pattern": "01"}, ["01", "101", "1101"], ["", "10", "011"]),
    (CONTAINS, {"pattern": "00"}, ["00", "100", "11001"], ["", "01", "10101"]),
    (NOT_CONTAINS, {"pattern": "00"}, ["", "0", "01", "10101"], ["00", "100", "001"]),
    (EVEN_COUNT, {"symbol": "0"}, ["", "1", "00", "1010"], ["0", "01", "000"]),
    (ODD_COUNT, {"symbol": "1"}, ["1", "01", "111"], ["", "0", "11"]),
    (EXACT_COUNT, {"symbol": "0", "count": 3}, ["000", "10001", "00101"], ["", "00", "0000"]),
]


@pytest.mark.parametrize("rule, params, accepted, rejected", RULE_CASES)
def test_language_rules_as_dfa_and_nfa(rule, params, accepted, rejected):
    dfa = build_language_dfa(rule, B, **params)
    for automaton in (dfa, as_nfa(dfa)):
        assert [run(automaton, t).accepted for t in accepted] == [True] * len(accepted)
        assert [run(automaton, t).accepted for t in rejected] == [False] * len(rejected)


def test_exact_strings():
    dfa = build_exact_string_dfa("aabb", {"a", "b"})
    for automaton in (dfa, as_nfa(dfa)):
        assert run(automaton, "aabb").accepted
        assert not any(run(automaton, t).accepted for t in ["", "a", "aa", "aab", "aabba", "babb"])
    assert run(build_exact_string_dfa("x", {"x"}), "x").accepted
    literal = build_exact_string_dfa("a|b", {"a", "b", "|"})
    assert run(literal, "a|b").accepted and not run(literal, "a").accepted
    punctuation = build_exact_string_dfa("*.\\", {"*", ".", "\\"})
    assert run(punctuation, "*.\\").accepted


def test_manual_even_zero_dfa():
    dfa = parse_and_build("DFA", "0,1", "q0,q1", "q0", "q0", "q0,0,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1")
    assert [run(dfa, t).accepted for t in ["", "0", "00", "1010", "000"]] == [True, False, True, True, False]


def test_manual_epsilon_nfa():
    nfa = parse_and_build("NFA", "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3")
    assert [run(nfa, t).accepted for t in ["a", "b", "", "ab"]] == [True, True, False, False]


def test_complex_manual_nfa_with_custom_names():
    nfa = parse_and_build(
        "NFA", "x,y", "Start,Loop,Hit,Other,Orphan", "Start", "Hit,Other",
        "Start,x,Loop\nStart,x,Hit\nLoop,ε,Start\nStart,ε,Loop\nLoop,y,Other\nOrphan,x,Hit",
    )
    for text in all_strings({"x", "y"}, 5):
        assert run(nfa, text).accepted == nfa_accepts(nfa, text), text
    no_accepting = parse_and_build("NFA", "x", "A,B", "A", "", "A,x,B\nB,ε,A")
    assert not any(run(no_accepting, t).accepted for t in all_strings({"x"}, 4))


# --- independent language checks and NFA/DFA equivalence --------------------------

LANGUAGES = [
    ("(a|b)*abb", lambda t: t.endswith("abb")),
    ("(0|1)*01", lambda t: t.endswith("01")),
    ("(ab)*", lambda t: t == "ab" * (len(t) // 2)),
    ("a(b|c)*", lambda t: t[:1] == "a" and set(t[1:]) <= {"b", "c"}),
    ("(a|b)*(ab|ba)", lambda t: t[-2:] in ("ab", "ba")),
    ("((a|ε)b)+", lambda t: len(t) > 0 and t.endswith("b") and "aa" not in t),
]


@pytest.mark.parametrize("expression, predicate", LANGUAGES)
def test_nfa_and_converted_dfa_agree_with_language(expression, predicate):
    nfa = regex_to_nfa(expression)
    dfa = convert_nfa_to_dfa(nfa).dfa
    for text in all_strings(nfa.alphabet, 6 if len(nfa.alphabet) <= 2 else 4):
        expected = predicate(text)
        assert simulate(nfa, text).accepted == expected, text
        assert simulate(dfa, text).accepted == expected, text
        assert dfa_accepts(dfa, text) == expected


def test_manual_nfa_and_converted_dfa_agree():
    nfa = parse_and_build("NFA", "a,b", "A,B,C", "A", "C", "A,a,A\nA,b,A\nA,a,B\nB,a,C\nB,b,C")
    dfa = convert_nfa_to_dfa(nfa).dfa
    for text in all_strings({"a", "b"}, 6):
        expected = len(text) >= 2 and text[-2] == "a"
        assert simulate(nfa, text).accepted == simulate(dfa, text).accepted == expected


def test_accepts_matches_simulate():
    nfa = regex_to_nfa("(a|b)*abb")
    for text in all_strings({"a", "b"}, 5):
        assert accepts(nfa, text) == simulate(nfa, text).accepted == nfa_accepts(nfa, text)


@pytest.mark.parametrize("expression", ["(a|b)*abb", "((a|b)c)*", "(a?b+)*", "a|ε"])
def test_traces_are_consistent_for_many_strings(expression):
    nfa = regex_to_nfa(expression)
    dfa = convert_nfa_to_dfa(nfa).dfa
    for text in all_strings(nfa.alphabet, 4):
        run(nfa, text)
        run(dfa, text)


def test_simulation_is_deterministic_and_does_not_modify_automaton():
    nfa = regex_to_nfa("(a|b)*abb")
    copy = regex_to_nfa("(a|b)*abb")
    first, second = simulate(nfa, "babb"), simulate(nfa, "babb")
    assert first == second
    assert nfa == copy


# --- errors ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, message",
    [
        ("abc", "symbol 'c' at position 3 is not in the alphabet {a, b}"),
        ("a b", r"symbol ' ' at position 2"),
        ("aB", "symbol 'B' at position 2"),
        ("ε", "leave the test string empty"),
        ("λ", "leave the test string empty"),
        ("a" * (MAX_SIMULATION_LENGTH + 1), f"maximum is {MAX_SIMULATION_LENGTH}"),
    ],
)
def test_invalid_test_strings(text, message):
    with pytest.raises(SimulationInputError, match=message):
        simulate(regex_to_nfa("(a|b)*"), text)


def test_input_at_length_limit_runs():
    result = simulate(regex_to_nfa("(a|b)*abb"), "ab" * (MAX_SIMULATION_LENGTH // 2 - 2) + "babb")
    assert result.accepted and result.symbols_consumed == MAX_SIMULATION_LENGTH


def test_long_input_on_largest_nfa_is_fast():
    # The largest regex NFA (1,024 states) on a maximum-length input; repeated
    # configurations are reused, so this should take well under a second.
    import time

    nfa = regex_to_nfa("a*" * 256)
    start = time.perf_counter()
    result = simulate(nfa, "a" * MAX_SIMULATION_LENGTH)
    assert result.accepted and time.perf_counter() - start < 5


def test_whitespace_is_not_stripped_and_case_matters():
    dfa = build_exact_string_dfa("aA", {"a", "A"})
    assert simulate(dfa, "aA").accepted
    assert not simulate(dfa, "Aa").accepted
    with pytest.raises(SimulationInputError):
        simulate(dfa, " aA")


@pytest.mark.parametrize(
    "automaton, message",
    [
        (make("PDA", ["q"], "a", "q", [], {}), "Invalid machine type"),
        (make(NFA, ["q"], "a", "q", [], {("q", "a"): {"z"}}), "unknown state 'z'"),
        (make(NFA, ["q"], "a", "z", [], {}), "Initial state 'z'"),
        (make(DFA, ["q"], "a", "q", [], {}), "Incomplete DFA"),
        (make(DFA, ["q", "r"], "a", "q", [], {("q", "a"): {"q", "r"}, ("r", "a"): {"r"}}), "2 destinations"),
        (make(DFA, ["q"], "a", "q", [], {("q", "a"): {"q"}, ("q", None): {"q"}}), "epsilon"),
    ],
)
def test_invalid_automata(automaton, message):
    with pytest.raises(SimulationError, match=message):
        simulate(automaton, "a")


def test_empty_alphabet():
    automaton = make(NFA, ["q"], "", "q", ["q"], {})
    assert simulate(automaton, "").accepted
    with pytest.raises(SimulationInputError):
        simulate(automaton, "a")


def test_input_error_is_a_simulation_error():
    assert issubclass(SimulationInputError, SimulationError)
    assert issubclass(SimulationError, ValueError)
