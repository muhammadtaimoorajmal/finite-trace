"""
Tests for structured language rules and exact strings (core/language_builder.py).

Every generated DFA is checked against an independent Python predicate on
all strings up to a fixed length, using a test-only DFA runner.
"""

import pytest

from core.automata import DFA, NFA
from core.language_builder import (
    CONTAINS,
    ENDS_WITH,
    EVEN_COUNT,
    EXACT_COUNT,
    MAX_COUNT,
    MAX_PATTERN_LENGTH,
    NOT_CONTAINS,
    NOT_ENDS_WITH,
    ODD_COUNT,
    STARTS_WITH,
    LanguageRuleError,
    as_nfa,
    build_exact_string,
    build_exact_string_dfa,
    build_language,
    build_language_dfa,
)
from test_converter import dfa_accepts
from test_thompson import all_strings, nfa_accepts


def assert_matches(dfa, alphabet, predicate, max_length=7):
    assert dfa.machine_type == DFA
    dfa.validate(require_complete=True)
    for text in all_strings(alphabet, max_length):
        assert dfa_accepts(dfa, text) == predicate(text), f"disagreement on {text!r}"


def assert_examples(dfa, accepted, rejected):
    for text in accepted:
        assert dfa_accepts(dfa, text), f"should accept {text!r}"
    for text in rejected:
        assert not dfa_accepts(dfa, text), f"should reject {text!r}"


# --- A: starts with ---------------------------------------------------------

@pytest.mark.parametrize("alphabet, pattern", [("ab", "a"), ("ab", "ab"), ("01", "01"), ("01", "101"), ("abc", "cab")])
def test_starts_with(alphabet, pattern):
    dfa = build_language_dfa(STARTS_WITH, set(alphabet), pattern=pattern)
    assert_matches(dfa, set(alphabet), lambda t: t.startswith(pattern))


def test_starts_with_examples_and_structure():
    dfa = build_language_dfa(STARTS_WITH, {"a", "b"}, pattern="ab")
    assert_examples(dfa, ["ab", "aba", "abb", "abab"], ["", "a", "ba", "bb"])
    assert len(dfa.states) == 4  # q0, q1, accepting q2, dead q3
    assert dfa.accepting_states == {"q2"}


def test_starts_with_drops_unreachable_dead_state():
    # Over {a}, the prefix 'aa' can never mismatch, so no dead state is needed.
    dfa = build_language_dfa(STARTS_WITH, {"a"}, pattern="aa")
    assert dfa.states == {"q0", "q1", "q2"}
    assert_matches(dfa, {"a"}, lambda t: t.startswith("aa"))


# --- B: ends with -------------------------------------------------------------

@pytest.mark.parametrize(
    "alphabet, pattern",
    [("01", "01"), ("ab", "abb"), ("ab", "aaa"), ("ab", "abab"), ("01", "10101"), ("abc", "aca")],
)
def test_ends_with(alphabet, pattern):
    dfa = build_language_dfa(ENDS_WITH, set(alphabet), pattern=pattern)
    assert_matches(dfa, set(alphabet), lambda t: t.endswith(pattern), max_length=7 if len(alphabet) == 2 else 5)


def test_ends_with_examples_and_overlaps():
    dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01")
    assert_examples(dfa, ["01", "101", "1101", "0001"], ["", "0", "10", "011"])
    overlapping = build_language_dfa(ENDS_WITH, {"a", "b"}, pattern="abab")
    assert_examples(overlapping, ["abab", "ababab", "aababab"], ["aba", "ababa", "abba"])
    repeated = build_language_dfa(ENDS_WITH, {"a", "b"}, pattern="aaa")
    assert_examples(repeated, ["aaa", "aaaa", "baaaaa"], ["aa", "aaab", "aabaa"])
    long_pattern = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="10101")
    assert_examples(long_pattern, ["1010101", "0010101"], ["101010", "1011"])


def test_ends_with_accepting_state_is_not_absorbing():
    dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01")
    accepting = next(iter(dfa.accepting_states))
    assert dfa.transitions[(accepting, "1")] != {accepting}


# --- C: contains ------------------------------------------------------------

@pytest.mark.parametrize(
    "alphabet, pattern", [("01", "00"), ("ab", "aba"), ("ab", "aaa"), ("01", "101"), ("ab", "abab"), ("abc", "abc")]
)
def test_contains(alphabet, pattern):
    dfa = build_language_dfa(CONTAINS, set(alphabet), pattern=pattern)
    assert_matches(dfa, set(alphabet), lambda t: pattern in t, max_length=7 if len(alphabet) == 2 else 5)


def test_contains_examples_and_fallback():
    dfa = build_language_dfa(CONTAINS, {"0", "1"}, pattern="00")
    assert_examples(dfa, ["00", "000", "100", "001", "11001"], ["", "0", "01", "10101"])
    # Partial-match fallback: after 'abab' fails to continue as 'ababa…', the overlap must be kept.
    overlap = build_language_dfa(CONTAINS, {"a", "b"}, pattern="aba")
    assert_examples(overlap, ["ababa", "aaba", "bbaba"], ["abba", "aabb"])
    tricky = build_language_dfa(CONTAINS, {"a", "b"}, pattern="abab")
    assert_examples(tricky, ["aababab", "abaabab"], ["abaab", "abba"])


def test_contains_accepting_state_is_absorbing():
    dfa = build_language_dfa(CONTAINS, {"0", "1"}, pattern="00")
    (accepting,) = dfa.accepting_states
    assert all(dfa.transitions[(accepting, x)] == {accepting} for x in "01")


# --- D/E: complements ---------------------------------------------------------

@pytest.mark.parametrize("alphabet, pattern", [("01", "00"), ("ab", "aba"), ("ab", "bb"), ("abc", "ca")])
def test_does_not_contain(alphabet, pattern):
    dfa = build_language_dfa(NOT_CONTAINS, set(alphabet), pattern=pattern)
    assert_matches(dfa, set(alphabet), lambda t: pattern not in t, max_length=7 if len(alphabet) == 2 else 5)


def test_does_not_contain_examples():
    dfa = build_language_dfa(NOT_CONTAINS, {"0", "1"}, pattern="00")
    assert_examples(dfa, ["", "0", "1", "01", "10101"], ["00", "100", "001", "000"])


@pytest.mark.parametrize("alphabet, pattern", [("01", "01"), ("ab", "abb"), ("ab", "aa"), ("abc", "cb")])
def test_does_not_end_with(alphabet, pattern):
    dfa = build_language_dfa(NOT_ENDS_WITH, set(alphabet), pattern=pattern)
    assert_matches(dfa, set(alphabet), lambda t: not t.endswith(pattern), max_length=7 if len(alphabet) == 2 else 5)


def test_does_not_end_with_examples():
    dfa = build_language_dfa(NOT_ENDS_WITH, {"0", "1"}, pattern="01")
    assert_examples(dfa, ["", "0", "1", "10", "011"], ["01", "101", "1101"])


def test_complement_has_same_transitions_and_swapped_acceptance():
    contains = build_language_dfa(CONTAINS, {"0", "1"}, pattern="00")
    complement = build_language_dfa(NOT_CONTAINS, {"0", "1"}, pattern="00")
    assert contains.transitions == complement.transitions
    assert complement.accepting_states == contains.states - contains.accepting_states


# --- F: parity --------------------------------------------------------------------

@pytest.mark.parametrize(
    "rule, alphabet, symbol",
    [(EVEN_COUNT, "01", "0"), (ODD_COUNT, "01", "0"), (EVEN_COUNT, "ab", "a"), (ODD_COUNT, "ab", "b"),
     (EVEN_COUNT, "abc", "c"), (ODD_COUNT, "01", "1")],
)
def test_parity(rule, alphabet, symbol):
    dfa = build_language_dfa(rule, set(alphabet), symbol=symbol)
    remainder = 0 if rule == EVEN_COUNT else 1
    assert_matches(dfa, set(alphabet), lambda t: t.count(symbol) % 2 == remainder, max_length=7 if len(alphabet) == 2 else 5)
    assert len(dfa.states) == 2


def test_parity_examples():
    even = build_language_dfa(EVEN_COUNT, {"0", "1"}, symbol="0")
    assert_examples(even, ["", "1", "00", "1010"], ["0", "01", "000"])
    odd = build_language_dfa(ODD_COUNT, {"0", "1"}, symbol="0")
    assert_examples(odd, ["0", "01", "000"], ["", "1", "00"])
    # Other symbols do not change parity.
    assert even.transitions[("q0", "1")] == {"q0"} and even.transitions[("q1", "1")] == {"q1"}


# --- G: exactly k ---------------------------------------------------------------------

@pytest.mark.parametrize("alphabet, symbol, count", [("01", "0", 0), ("ab", "a", 1), ("01", "0", 3), ("01", "1", 4), ("abc", "b", 2)])
def test_exact_count(alphabet, symbol, count):
    dfa = build_language_dfa(EXACT_COUNT, set(alphabet), symbol=symbol, count=count)
    assert_matches(dfa, set(alphabet), lambda t: t.count(symbol) == count, max_length=7 if len(alphabet) == 2 else 5)
    assert len(dfa.states) == count + 2  # counts 0..k plus the overflow state


def test_exact_count_examples_and_overflow():
    dfa = build_language_dfa(EXACT_COUNT, {"0", "1"}, symbol="0", count=3)
    assert_examples(dfa, ["000", "10001", "00101"], ["", "00", "0000", "111"])
    overflow = "q4"
    assert overflow not in dfa.accepting_states
    assert all(dfa.transitions[(overflow, x)] == {overflow} for x in "01")


def test_exact_count_zero():
    dfa = build_language_dfa(EXACT_COUNT, {"0", "1"}, symbol="0", count=0)
    assert_examples(dfa, ["", "1", "111"], ["0", "10"])


def test_exact_count_maximum():
    dfa = build_language_dfa(EXACT_COUNT, {"a", "b"}, symbol="a", count=MAX_COUNT)
    assert len(dfa.states) == MAX_COUNT + 2
    assert dfa_accepts(dfa, "a" * MAX_COUNT + "b") and not dfa_accepts(dfa, "a" * (MAX_COUNT + 1))


# --- H: exact strings ---------------------------------------------------------------

@pytest.mark.parametrize("alphabet, text", [("a", "a"), ("ab", "ab"), ("ab", "aabb"), ("01", "0101"), ("a|b", "a|b"), ("*.", "*.*")])
def test_exact_string(alphabet, text):
    dfa = build_exact_string_dfa(text, set(alphabet))
    assert_matches(dfa, set(alphabet), lambda t: t == text, max_length=6)


def test_exact_string_examples_and_structure():
    result = build_exact_string("aabb", {"a", "b"})
    dfa = result.automaton
    assert_examples(dfa, ["aabb"], ["", "a", "aa", "aab", "aabba", "babb", "baab"])
    assert dfa.states == {f"q{i}" for i in range(6)}
    assert dfa.accepting_states == {"q4"}
    assert result.state_notes["q5"].startswith("dead")
    assert [dfa.transitions[(f"q{i}", c)] for i, c in enumerate("aabb")] == [{"q1"}, {"q2"}, {"q3"}, {"q4"}]


def test_exact_string_is_literal_not_regex():
    dfa = build_exact_string_dfa("a|b", {"a", "b", "|"})
    assert_examples(dfa, ["a|b"], ["a", "b", "ab"])


def test_empty_exact_string():
    dfa = build_exact_string_dfa("", {"a", "b"})
    assert_matches(dfa, {"a", "b"}, lambda t: t == "")
    assert len(dfa.states) == 2  # accepting start state plus dead state
    empty_alphabet = build_exact_string_dfa("", set())
    assert empty_alphabet.states == {"q0"} and empty_alphabet.transitions == {}
    assert empty_alphabet.accepting_states == {"q0"}


# --- I: DFA / NFA output --------------------------------------------------------------

def test_nfa_representation_is_equivalent_and_independent():
    dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="011")
    nfa = as_nfa(dfa)
    assert nfa.machine_type == NFA and dfa.machine_type == DFA
    nfa.validate()
    assert nfa.transitions == dfa.transitions and nfa.accepting_states == dfa.accepting_states
    for text in all_strings({"0", "1"}, 6):
        assert nfa_accepts(nfa, text) == dfa_accepts(dfa, text)
    nfa.transitions[("q0", "0")].add("q2")
    nfa.accepting_states.add("q0")
    assert dfa.transitions[("q0", "0")] == {"q1"}  # the DFA is unaffected
    assert "q0" not in dfa.accepting_states


def test_generation_is_deterministic():
    first = build_language(CONTAINS, {"a", "b", "c"}, pattern="abca")
    second = build_language(CONTAINS, {"a", "b", "c"}, pattern="abca")
    assert first == second


# --- empty alphabet -----------------------------------------------------------------

def test_counting_rules_need_symbol_in_alphabet():
    with pytest.raises(LanguageRuleError, match="not in the alphabet"):
        build_language_dfa(EVEN_COUNT, set(), symbol="a")


# --- J: invalid parameters ----------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"rule": "palindrome", "alphabet": {"a"}}, "Unsupported language rule"),
        ({"rule": ENDS_WITH, "alphabet": {"a", "b"}, "pattern": ""}, "Enter a pattern"),
        ({"rule": STARTS_WITH, "alphabet": {"0", "1"}, "pattern": "012"}, "'2' at position 3"),
        ({"rule": EVEN_COUNT, "alphabet": {"0", "1"}, "symbol": "a"}, "not in the alphabet"),
        ({"rule": ODD_COUNT, "alphabet": {"0", "1"}, "symbol": ""}, "Choose the symbol"),
        ({"rule": EXACT_COUNT, "alphabet": {"0", "1"}, "symbol": "0", "count": -1}, "between 0 and"),
        ({"rule": EXACT_COUNT, "alphabet": {"0", "1"}, "symbol": "0", "count": 2.5}, "whole number"),
        ({"rule": EXACT_COUNT, "alphabet": {"0", "1"}, "symbol": "0", "count": "3"}, "whole number"),
        ({"rule": EXACT_COUNT, "alphabet": {"0", "1"}, "symbol": "0", "count": MAX_COUNT + 1}, "between 0 and"),
        ({"rule": EXACT_COUNT, "alphabet": {"0", "1"}, "symbol": "00", "count": 1}, "single character"),
        ({"rule": CONTAINS, "alphabet": {"ab"}, "pattern": "ab"}, "Invalid alphabet symbol"),
        ({"rule": CONTAINS, "alphabet": {" "}, "pattern": " "}, "Invalid alphabet symbol"),
        ({"rule": CONTAINS, "alphabet": {","}, "pattern": ","}, "Invalid alphabet symbol"),
        ({"rule": CONTAINS, "alphabet": {"a"}, "pattern": "a" * (MAX_PATTERN_LENGTH + 1)}, "maximum is"),
        ({"rule": CONTAINS, "alphabet": set("abcdefghijklmnopqrstu"), "pattern": "a"}, "maximum is 20"),
    ],
)
def test_invalid_parameters(kwargs, message):
    with pytest.raises(LanguageRuleError, match=message):
        build_language(**kwargs)


def test_exact_string_rejects_symbols_outside_alphabet():
    with pytest.raises(LanguageRuleError, match="'c' at position 3"):
        build_exact_string_dfa("abc", {"a", "b"})
    with pytest.raises(LanguageRuleError, match="maximum is 100"):
        build_exact_string_dfa("a" * 101, {"a"})
