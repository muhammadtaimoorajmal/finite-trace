"""Tests for manual DFA/NFA definitions (core/manual_builder.py) and their conversion."""

import pytest

from core.automata import DFA, NFA
from core.converter import ConversionError, convert_nfa_to_dfa
from core.manual_builder import (
    MAX_STATES,
    MAX_TRANSITION_ROWS,
    ManualInputError,
    build_manual_automaton,
    parse_alphabet,
    parse_and_build,
    parse_manual_definition,
    parse_states,
)
from test_converter import assert_equivalent, dfa_accepts
from test_thompson import all_strings, nfa_accepts

EVEN_ZEROS = "q0,0,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1"
EPSILON_NFA = "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3"


def build(machine_type, alphabet, states, initial, accepting, transitions):
    return parse_and_build(machine_type, alphabet, states, initial, accepting, transitions)


# --- valid DFAs -----------------------------------------------------------------

def test_even_zeros_dfa():
    dfa = build(DFA, "0,1", "q0,q1", "q0", "q0", EVEN_ZEROS)
    assert dfa.machine_type == DFA
    assert dfa.transitions == {("q0", "0"): {"q1"}, ("q0", "1"): {"q0"}, ("q1", "0"): {"q0"}, ("q1", "1"): {"q1"}}
    for text in all_strings({"0", "1"}, 6):
        assert dfa_accepts(dfa, text) == (text.count("0") % 2 == 0)


def test_whitespace_is_trimmed():
    dfa = build(DFA, " 0 , 1 ", " q0 , q1 ", " q0 ", " q0 ", "  q0 , 0 , q1\n\nq0,1,q0\n # comment\nq1,0,q0\nq1,1,q1  ")
    assert dfa.states == {"q0", "q1"} and dfa.alphabet == {"0", "1"}


@pytest.mark.parametrize(
    "alphabet, states, initial, accepting, transitions, accepted, rejected",
    [
        ("a", "s", "s", "s", "s,a,s", ["", "aaa"], []),                                    # one state, self-loop
        ("a,b", "A,B", "A", "A,B", "A,a,B\nA,b,A\nB,a,B\nB,b,A", ["", "a", "ab"], []),       # several accepting
        ("a,b", "A,B", "A", "", "A,a,B\nA,b,A\nB,a,B\nB,b,A", [], ["", "a", "ab"]),          # no accepting states
        ("", "q0", "q0", "q0", "", [""], []),                                               # empty alphabet
    ],
)
def test_other_valid_dfas(alphabet, states, initial, accepting, transitions, accepted, rejected):
    dfa = build(DFA, alphabet, states, initial, accepting, transitions)
    dfa.validate(require_complete=True)
    for text in accepted:
        assert dfa_accepts(dfa, text)
    for text in rejected:
        assert not dfa_accepts(dfa, text)


def test_duplicate_identical_rows_are_merged():
    dfa = build(DFA, "a", "q0", "q0", "q0", "q0,a,q0\nq0,a,q0")
    assert dfa.transitions == {("q0", "a"): {"q0"}}


# --- invalid DFAs ---------------------------------------------------------------

@pytest.mark.parametrize(
    "fields, message",
    [
        ((DFA, "0,1", "q0", "q0", "q0", "q0,0,q1\nq0,1,q0"), "line 1: unknown state 'q1'"),
        ((DFA, "0,1", "q0,q1", "q5", "q0", EVEN_ZEROS), "Initial state 'q5'"),
        ((DFA, "0,1", "q0,q1", "q0", "q9", EVEN_ZEROS), "Accepting state 'q9'"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,0,q1\nq0,1,q7"), "line 2: unknown state 'q7'"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,2,q1"), "line 1: symbol '2' is not in the alphabet"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,0,q1\nq0,1,q0\nq1,0,q0"),
         "Incomplete DFA: missing transition for state 'q1' on symbol '1'"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,0,q1\nq0,0,q0\nq0,1,q0\nq1,0,q0\nq1,1,q1"),
         "line 2: a DFA allows one destination .* already goes to 'q1' on line 1"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,ε,q1"), "line 1: a DFA cannot have ε-transitions"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,0"), "line 1: expected 'source,symbol,destination'"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,0,q1,q0"), "found 4 field"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", ",0,q1"), "must not be empty"),
        ((DFA, "0,1", "q0,q1", "q0", "q0", "q0,01,q1"), "must be a single character"),
        (("PDA", "0,1", "q0", "q0", "q0", ""), "Machine type must be DFA or NFA"),
        ((DFA, "0,1", "", "q0", "", ""), "enter at least one state"),
        ((DFA, "0,1", "q0", "", "", ""), "Initial state: enter"),
        ((DFA, "0,,1", "q0", "q0", "", ""), "empty item"),
        ((DFA, "ab", "q0", "q0", "", ""), "not a single character"),
        ((DFA, "a,a", "q0", "q0", "", ""), "listed more than once"),
        ((DFA, "a,ε", "q0", "q0", "", ""), "reserved for epsilon"),
        ((DFA, "a", "q0,q 1", "q0", "", ""), "not a valid state name"),
        ((DFA, "a", "q0,q0", "q0", "", ""), "listed more than once"),
    ],
)
def test_invalid_definitions(fields, message):
    with pytest.raises(ManualInputError, match=message):
        build(*fields)


def test_incomplete_dfa_lists_every_missing_pair():
    with pytest.raises(ManualInputError) as info:
        build(DFA, "a,b", "q0,q1", "q0", "", "q0,a,q1")
    message = str(info.value)
    for pair in ["state 'q0' on symbol 'b'", "state 'q1' on symbol 'a'", "state 'q1' on symbol 'b'"]:
        assert pair in message


# --- valid NFAs ---------------------------------------------------------------------

def test_epsilon_nfa():
    nfa = build(NFA, "a,b", "q0,q1,q2,q3", "q0", "q3", EPSILON_NFA)
    assert nfa.machine_type == NFA
    assert nfa.transitions[("q0", None)] == {"q1", "q2"}
    assert_language = [(t, nfa_accepts(nfa, t)) for t in ["a", "b", "", "ab", "aa"]]
    assert assert_language == [("a", True), ("b", True), ("", False), ("ab", False), ("aa", False)]


def test_lambda_is_epsilon_and_e_is_a_symbol():
    nfa = build(NFA, "a,e", "q0,q1,q2", "q0", "q2", "q0,λ,q1\nq1,e,q2")
    assert nfa.transitions == {("q0", None): {"q1"}, ("q1", "e"): {"q2"}}


def test_nondeterministic_nfa_with_missing_transitions():
    nfa = build(NFA, "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,a,q1\nq0,a,q2\nq1,b,q3\nq2,b,q3")
    assert nfa.transitions[("q0", "a")] == {"q1", "q2"}
    assert nfa_accepts(nfa, "ab") and not nfa_accepts(nfa, "a")


def test_nfa_with_epsilon_cycle_and_multiple_or_no_accepting_states():
    cyclic = build(NFA, "a", "x,y,z", "x", "y,z", "x,ε,y\ny,ε,x\ny,a,z\nz,ε,z")
    cyclic.validate()
    assert nfa_accepts(cyclic, "") and nfa_accepts(cyclic, "a")
    empty = build(NFA, "a", "x,y", "x", "", "x,a,y")
    assert not any(nfa_accepts(empty, t) for t in all_strings({"a"}, 3))


# --- manual NFA conversion ----------------------------------------------------------

def test_manual_epsilon_nfa_converts_to_a_or_b():
    nfa = build(NFA, "a,b", "q0,q1,q2,q3", "q0", "q3", EPSILON_NFA)
    result = convert_nfa_to_dfa(nfa)
    dfa = result.dfa
    dfa.validate(require_complete=True)
    assert dfa.alphabet == {"a", "b"}
    assert result.state_mapping["D0"] == frozenset({"q0", "q1", "q2"})
    accepted = [t for t in all_strings({"a", "b"}, 4) if dfa_accepts(dfa, t)]
    assert accepted == ["a", "b"]
    assert_equivalent(nfa, dfa)


def test_custom_named_nfa_converts_generally():
    # Arbitrary state names and a hand-made structure: strings whose second-to-last symbol is 'a',
    # plus an ε-shortcut from Start straight to Final on 'c'.
    nfa = build(
        NFA, "a,b,c", "Start,Mid,Final,Spare", "Start", "Final",
        "Start,a,Start\nStart,b,Start\nStart,c,Start\nStart,a,Mid\nMid,a,Final\nMid,b,Final\n"
        "Mid,c,Final\nStart,ε,Spare\nSpare,c,Final",
    )
    result = convert_nfa_to_dfa(nfa)
    assert all(name.startswith("D") for name in result.dfa.states)
    assert result.state_mapping["D0"] == frozenset({"Start", "Spare"})
    assert_equivalent(nfa, result.dfa, max_length=5)


def test_manual_nfa_conversion_respects_state_limit():
    nfa = build(NFA, "a,b", "s,t,u", "s", "u", "s,a,s\ns,b,s\ns,a,t\nt,a,u\nt,b,u")
    with pytest.raises(ConversionError, match="more than 2 states"):
        convert_nfa_to_dfa(nfa, max_states=2)


# --- limits and structured API ----------------------------------------------------

def test_state_limit():
    names = ",".join(f"s{i}" for i in range(MAX_STATES + 1))
    with pytest.raises(ManualInputError, match=f"maximum is {MAX_STATES}"):
        parse_states(names)


def test_transition_row_limit():
    rows = "\n".join("q0,a,q0" for _ in range(MAX_TRANSITION_ROWS + 1))
    with pytest.raises(ManualInputError, match=f"maximum is {MAX_TRANSITION_ROWS}"):
        build(NFA, "a", "q0", "q0", "", rows)


def test_alphabet_limit_and_long_state_names():
    with pytest.raises(ManualInputError, match="maximum is 20"):
        parse_alphabet(",".join("abcdefghijklmnopqrstu"))
    with pytest.raises(ManualInputError, match="longer than 40"):
        parse_states("q" * 41)


def test_build_manual_automaton_structured_api():
    nfa = build_manual_automaton(NFA, {"p", "r"}, {"x"}, "p", {"r"}, [("p", "x", "r"), ("p", None, "r")])
    assert nfa.transitions == {("p", "x"): {"r"}, ("p", None): {"r"}}
    with pytest.raises(ManualInputError, match="Incomplete DFA"):
        build_manual_automaton(DFA, {"p"}, {"x"}, "p", set(), [])
    with pytest.raises(ManualInputError, match="unknown state 'z'"):
        build_manual_automaton(NFA, {"p"}, {"x"}, "p", set(), [("p", "x", "z")])


def test_parse_manual_definition_keeps_order():
    definition = parse_manual_definition(NFA, "b,a", "z,y,x", "z", "x", "z,a,y")
    assert definition.states == ("z", "y", "x")
    assert definition.alphabet == frozenset({"a", "b"})
