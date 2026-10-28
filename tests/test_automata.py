"""Tests for the shared FiniteAutomaton data model and its validation."""

import pytest

from core.automata import (
    DFA,
    EPSILON,
    NFA,
    AutomatonValidationError,
    FiniteAutomaton,
    display_symbol,
)


def make_dfa() -> FiniteAutomaton:
    """DFA over {a, b} accepting strings that end in 'a'."""
    return FiniteAutomaton(
        machine_type=DFA,
        states={"q0", "q1"},
        alphabet={"a", "b"},
        initial_state="q0",
        accepting_states={"q1"},
        transitions={
            ("q0", "a"): {"q1"},
            ("q0", "b"): {"q0"},
            ("q1", "a"): {"q1"},
            ("q1", "b"): {"q0"},
        },
    )


def make_nfa() -> FiniteAutomaton:
    """NFA over {a, b} accepting strings that contain 'ab'."""
    return FiniteAutomaton(
        machine_type=NFA,
        states={"q0", "q1", "q2"},
        alphabet={"a", "b"},
        initial_state="q0",
        accepting_states={"q2"},
        transitions={
            ("q0", "a"): {"q0", "q1"},
            ("q0", "b"): {"q0"},
            ("q1", "b"): {"q2"},
            ("q2", "a"): {"q2"},
            ("q2", "b"): {"q2"},
        },
    )


# --- valid machines -------------------------------------------------------

def test_valid_dfa_passes_validation():
    dfa = make_dfa()
    dfa.validate()
    assert dfa.is_dfa and not dfa.is_nfa
    assert dfa.states == {"q0", "q1"}
    assert dfa.alphabet == {"a", "b"}
    assert dfa.accepting_states == {"q1"}
    assert dfa.get_destinations("q0", "a") == {"q1"}


def test_valid_nfa_with_multiple_destinations():
    nfa = make_nfa()
    nfa.validate()
    assert nfa.is_nfa
    assert nfa.get_destinations("q0", "a") == {"q0", "q1"}
    # Missing transitions are allowed in an NFA and mean "no destinations".
    assert nfa.get_destinations("q1", "a") == set()


def test_valid_epsilon_nfa():
    nfa = FiniteAutomaton(
        machine_type=NFA,
        states={"q0", "q1", "q2"},
        alphabet={"a"},
        initial_state="q0",
        accepting_states={"q2"},
        transitions={("q0", EPSILON): {"q1", "q2"}, ("q1", "a"): {"q2"}},
    )
    nfa.validate()
    assert nfa.get_destinations("q0", None) == {"q1", "q2"}


def test_epsilon_is_none_not_letter_e():
    nfa = make_nfa()
    nfa.add_transition("q1", None, "q2")
    nfa.validate()
    # The literal character "e" is a normal symbol and is not in this alphabet.
    nfa.add_transition("q1", "e", "q2")
    with pytest.raises(AutomatonValidationError, match="not in the alphabet"):
        nfa.validate()
    assert display_symbol(None) == "ε"
    assert display_symbol("e") == "e"


def test_add_transition_builds_destination_sets():
    nfa = FiniteAutomaton(NFA, {"q0", "q1"}, {"a"}, "q0", {"q1"})
    nfa.add_transition("q0", "a", "q0")
    nfa.add_transition("q0", "a", "q1")
    assert nfa.transitions == {("q0", "a"): {"q0", "q1"}}
    assert nfa.is_valid()


# --- invalid machines -----------------------------------------------------

def test_invalid_machine_type():
    dfa = make_dfa()
    dfa.machine_type = "PDA"
    with pytest.raises(AutomatonValidationError, match="Invalid machine type"):
        dfa.validate()


def test_empty_state_name_rejected():
    nfa = make_nfa()
    nfa.states.add("  ")
    with pytest.raises(AutomatonValidationError, match="Invalid state identifier"):
        nfa.validate()


def test_multi_character_alphabet_symbol_rejected():
    nfa = make_nfa()
    nfa.alphabet.add("ab")
    with pytest.raises(AutomatonValidationError, match="Invalid alphabet symbol"):
        nfa.validate()


def test_invalid_initial_state():
    dfa = make_dfa()
    dfa.initial_state = "q9"
    with pytest.raises(AutomatonValidationError, match="Initial state 'q9'"):
        dfa.validate()


def test_invalid_accepting_state():
    dfa = make_dfa()
    dfa.accepting_states = {"q1", "q7"}
    with pytest.raises(AutomatonValidationError, match="Accepting state 'q7'"):
        dfa.validate()


def test_invalid_transition_source():
    nfa = make_nfa()
    nfa.transitions[("q5", "a")] = {"q0"}
    with pytest.raises(AutomatonValidationError, match="unknown state 'q5'"):
        nfa.validate()


def test_invalid_transition_destination():
    nfa = make_nfa()
    nfa.transitions[("q1", "a")] = {"q3"}
    with pytest.raises(AutomatonValidationError, match="unknown state 'q3'"):
        nfa.validate()


def test_dfa_with_two_destinations_rejected():
    dfa = make_dfa()
    dfa.transitions[("q0", "a")] = {"q0", "q1"}
    with pytest.raises(AutomatonValidationError, match="2 destinations"):
        dfa.validate()


def test_dfa_with_epsilon_transition_rejected():
    dfa = make_dfa()
    dfa.transitions[("q0", None)] = {"q1"}
    with pytest.raises(AutomatonValidationError, match="epsilon"):
        dfa.validate()


def test_incomplete_dfa_detected():
    dfa = make_dfa()
    del dfa.transitions[("q1", "b")]
    with pytest.raises(AutomatonValidationError, match="missing transition for state 'q1' on symbol 'b'"):
        dfa.validate()
    # The same partial DFA is acceptable when completeness is not required.
    dfa.validate(require_complete=False)
    assert not dfa.is_valid()
    assert dfa.is_valid(require_complete=False)
