"""
Tests for Thompson's construction (core/thompson.py).

Language correctness is checked with nfa_accepts(), a small test-only NFA
runner written independently of the construction code, and for exhaustive
checks against Python's re module as an outside oracle.
"""

import itertools
import re

import pytest

from core.automata import NFA, FiniteAutomaton
from core.regex_parser import (
    CONCAT,
    LITERAL,
    STAR,
    UNION,
    ParsedRegex,
    RegexSyntaxError,
    Token,
    parse_regex,
)
from core.thompson import (
    MAX_NFA_STATES,
    ConstructionError,
    NFAFragment,
    construct_nfa,
    regex_to_nfa,
)


# --- independent test-only acceptance helper ------------------------------

def epsilon_closure(nfa: FiniteAutomaton, states: set) -> set:
    closure = set(states)
    pending = list(states)
    while pending:
        state = pending.pop()
        for target in nfa.transitions.get((state, None), set()):
            if target not in closure:
                closure.add(target)
                pending.append(target)
    return closure


def nfa_accepts(nfa: FiniteAutomaton, text: str) -> bool:
    current = epsilon_closure(nfa, {nfa.initial_state})
    for symbol in text:
        moved = set()
        for state in current:
            moved |= nfa.transitions.get((state, symbol), set())
        current = epsilon_closure(nfa, moved)
    return bool(current & nfa.accepting_states)


def assert_language(expression, accepted, rejected):
    nfa = regex_to_nfa(expression)
    for text in accepted:
        assert nfa_accepts(nfa, text), f"{expression!r} should accept {text!r}"
    for text in rejected:
        assert not nfa_accepts(nfa, text), f"{expression!r} should reject {text!r}"


def all_strings(alphabet, max_length):
    for length in range(max_length + 1):
        for letters in itertools.product(sorted(alphabet), repeat=length):
            yield "".join(letters)


def assert_well_formed(nfa: FiniteAutomaton):
    nfa.validate()
    assert nfa.machine_type == NFA
    assert len(nfa.accepting_states) == 1
    assert all(re.fullmatch(r"q\d+", state) for state in nfa.states)
    # States are numbered q0..q(n-1) with no gaps or duplicates.
    assert sorted(int(s[1:]) for s in nfa.states) == list(range(len(nfa.states)))
    for source, symbol, destination in nfa.transition_list():
        assert source in nfa.states and destination in nfa.states
        assert symbol is None or symbol in nfa.alphabet


# --- A: basic construction ------------------------------------------------

@pytest.mark.parametrize("symbol", ["a", "b", "0", "1", "Z", "_"])
def test_single_literal(symbol):
    nfa = regex_to_nfa(symbol)
    assert_well_formed(nfa)
    assert nfa.states == {"q0", "q1"}
    assert nfa.initial_state == "q0"
    assert nfa.accepting_states == {"q1"}
    assert nfa.alphabet == {symbol}
    assert nfa.transitions == {("q0", symbol): {"q1"}}


def test_concatenation_structure_preserves_order():
    nfa = regex_to_nfa("ab")
    assert nfa.transition_list() == [("q0", "a", "q1"), ("q1", None, "q2"), ("q2", "b", "q3")]
    assert nfa.initial_state == "q0" and nfa.accepting_states == {"q3"}
    assert_language("ab", ["ab"], ["", "a", "b", "ba", "abb"])


def test_three_symbol_concatenation():
    nfa = regex_to_nfa("abc")
    assert_well_formed(nfa)
    assert len(nfa.states) == 6
    assert_language("abc", ["abc"], ["", "ab", "bc", "cba", "abcc"])


# --- B: union -------------------------------------------------------------

def test_union_structure():
    nfa = regex_to_nfa("a|b")
    assert_well_formed(nfa)
    assert nfa.initial_state == "q4" and nfa.accepting_states == {"q5"}
    assert nfa.get_destinations("q4", None) == {"q0", "q2"}
    assert nfa.get_destinations("q1", None) == {"q5"}
    assert nfa.get_destinations("q3", None) == {"q5"}


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a|b", ["a", "b"], ["", "ab", "ba", "aa", "bb"]),
        ("0|1", ["0", "1"], ["", "01", "2"]),
        ("ab|cd", ["ab", "cd"], ["", "a", "ac", "abcd", "ad", "cb"]),
        ("(a|b)|c", ["a", "b", "c"], ["", "ab", "bc"]),
        ("a|(b|c)", ["a", "b", "c"], ["", "ab", "ca"]),
    ],
)
def test_union_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- C: Kleene star -------------------------------------------------------

def test_star_structure():
    nfa = regex_to_nfa("a*")
    assert nfa.initial_state == "q2" and nfa.accepting_states == {"q3"}
    assert nfa.get_destinations("q2", None) == {"q0", "q3"}   # enter or skip
    assert nfa.get_destinations("q1", None) == {"q0", "q3"}   # loop or leave


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a*", ["", "a", "aa", "aaaa"], ["b", "ab", "ba"]),
        ("(ab)*", ["", "ab", "abab", "ababab"], ["a", "abb", "aba", "ba"]),
        ("(a|b)*", ["", "a", "b", "abba", "bbbb"], ["c", "abc"]),
        ("((a|b)c)*", ["", "ac", "bc", "acbc", "bcbcac"], ["a", "c", "ab", "acb", "cc"]),
    ],
)
def test_star_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- D: Kleene plus -------------------------------------------------------

def test_plus_has_no_skip_transition():
    nfa = regex_to_nfa("a+")
    assert nfa.get_destinations("q2", None) == {"q0"}
    assert nfa.get_destinations("q1", None) == {"q0", "q3"}


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a+", ["a", "aa", "aaa"], ["", "b", "ab"]),
        ("(ab)+", ["ab", "abab", "ababab"], ["", "a", "aba", "abb"]),
        ("(a|b)+", ["a", "b", "ab", "bba"], ["", "c"]),
    ],
)
def test_plus_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- E: optional ----------------------------------------------------------

def test_optional_has_no_loop():
    nfa = regex_to_nfa("a?")
    assert nfa.get_destinations("q2", None) == {"q0", "q3"}
    assert nfa.get_destinations("q1", None) == {"q3"}


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a?", ["", "a"], ["aa", "b"]),
        ("(ab)?", ["", "ab"], ["abab", "a", "b"]),
        ("a?b", ["b", "ab"], ["", "a", "aab", "abb"]),
    ],
)
def test_optional_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- F: epsilon -----------------------------------------------------------

@pytest.mark.parametrize("expression", ["ε", "λ"])
def test_epsilon_fragment(expression):
    nfa = regex_to_nfa(expression)
    assert_well_formed(nfa)
    assert nfa.alphabet == set()
    assert nfa.transitions == {("q0", None): {"q1"}}
    assert_language(expression, [""], ["a", "b"])


def test_epsilon_uses_none_not_character():
    for expression in ["a|ε", "(a|ε)b", "εa"]:
        nfa = regex_to_nfa(expression)
        assert all(symbol != "ε" and symbol != "λ" for (_, symbol) in nfa.transitions)
        assert "ε" not in nfa.alphabet


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a|ε", ["", "a"], ["aa", "b"]),
        ("(a|ε)b", ["b", "ab"], ["", "a", "abb"]),
        ("εa", ["a"], ["", "aa"]),
        ("e|ε", ["", "e"], ["ee"]),
    ],
)
def test_epsilon_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


def test_letter_e_is_a_real_symbol():
    nfa = regex_to_nfa("e")
    assert nfa.alphabet == {"e"}
    assert nfa.transitions == {("q0", "e"): {"q1"}}


# --- G: escaped literals --------------------------------------------------

@pytest.mark.parametrize("expression, symbol", [(r"\|", "|"), (r"\*", "*"), (r"\.", "."), (r"\\", "\\")])
def test_escaped_single_literal(expression, symbol):
    nfa = regex_to_nfa(expression)
    assert nfa.transitions == {("q0", symbol): {"q1"}}
    assert nfa.alphabet == {symbol}
    assert_language(expression, [symbol], ["", symbol * 2])


@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        (r"a\|b", ["a|b"], ["a", "b", "ab"]),
        (r"a\.b", ["a.b"], ["ab", "a"]),
        (r"a\\b", ["a\\b"], ["ab"]),
        (r"\*", ["*"], ["", "**"]),
    ],
)
def test_escaped_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- H: operator precedence -----------------------------------------------

@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("a|bc", ["a", "bc"], ["ac", "abc", "b", "c"]),
        ("ab*", ["a", "ab", "abbb"], ["", "abab", "b"]),
        ("(ab)*", ["", "ab", "abab"], ["abb", "a"]),
        ("a(b|c)*", ["a", "ab", "acbc"], ["", "b", "ba"]),
        ("(a|b)*abb", ["abb", "aabb", "babb", "ababb"], ["", "ab", "abba", "bab"]),
        ("(0|1)*01", ["01", "101", "1101", "0001"], ["", "00", "10", "011"]),
    ],
)
def test_precedence_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- I: nested expressions ------------------------------------------------

@pytest.mark.parametrize(
    "expression, accepted, rejected",
    [
        ("((a|b)c)*", ["", "ac", "bcac"], ["c", "abc"]),
        ("((ab)|(cd))*", ["", "ab", "cd", "abcdab"], ["a", "ac", "abc"]),
        ("(a|b)*(ab|ba)", ["ab", "ba", "aab", "bbba"], ["", "a", "aa", "abb"]),
        ("(a?b+)*", ["", "b", "ab", "abbab", "bbb"], ["a", "aab", "ba"]),
        ("((a|ε)b)+", ["b", "ab", "bab", "abab"], ["", "a", "aab", "ba"]),
    ],
)
def test_nested_language(expression, accepted, rejected):
    assert_language(expression, accepted, rejected)


# --- exhaustive small-string checks --------------------------------------

@pytest.mark.parametrize(
    "expression, predicate",
    [
        ("a*", lambda s: set(s) <= {"a"}),
        ("a+", lambda s: len(s) >= 1 and set(s) <= {"a"}),
        ("a?", lambda s: s in ("", "a")),
        ("a|b", lambda s: s in ("a", "b")),
        ("ab", lambda s: s == "ab"),
        ("(ab)*", lambda s: s == "ab" * (len(s) // 2)),
        ("(ab)+", lambda s: len(s) >= 2 and s == "ab" * (len(s) // 2)),
        ("(a|b)*abb", lambda s: s.endswith("abb")),
        ("(0|1)*01", lambda s: s.endswith("01")),
    ],
)
def test_exhaustive_against_predicate(expression, predicate):
    nfa = regex_to_nfa(expression)
    alphabet = nfa.alphabet | ({"b"} if nfa.alphabet == {"a"} else set())
    for text in all_strings(alphabet, 5):
        assert nfa_accepts(nfa, text) == predicate(text), f"{expression!r} on {text!r}"


@pytest.mark.parametrize(
    "expression",
    [
        "(a|b)*(ab|ba)", "(a?b+)*", "((a|ε)b)+", "a(b|c)*", "((ab)|(cd))*",
        "(a|b)?(b|c)+a*", "((a*b?)*c)+", "a|b|c|ε", "(ab|a)(bc|c)", "((a|b)(a|b))*",
    ],
)
def test_exhaustive_against_python_re(expression):
    # Python's re agrees with formal regexes on this escape-free subset; ε maps to "".
    oracle = re.compile(expression.replace("ε", ""))
    nfa = regex_to_nfa(expression)
    for text in all_strings(nfa.alphabet, 5):
        assert nfa_accepts(nfa, text) == bool(oracle.fullmatch(text)), f"{expression!r} on {text!r}"


# --- expected Thompson state counts --------------------------------------

@pytest.mark.parametrize(
    "expression, states",
    [("a", 2), ("ε", 2), ("ab", 4), ("a|b", 6), ("a*", 4), ("a+", 4), ("a?", 4), ("(a|b)*abb", 14)],
)
def test_state_counts(expression, states):
    assert len(regex_to_nfa(expression).states) == states


# --- J: uniqueness, determinism, isolation -------------------------------

@pytest.mark.parametrize("expression", ["(a|b)*abb", "((ab)|(cd))*", "(a?b+)*", r"a\|b|ε"])
def test_generated_nfa_is_well_formed(expression):
    assert_well_formed(regex_to_nfa(expression))


def test_construction_is_deterministic():
    first = regex_to_nfa("(a|b)*abb")
    second = regex_to_nfa("(a|b)*abb")
    assert first == second
    assert first.transition_list() == second.transition_list()


def test_constructions_do_not_share_state():
    big = regex_to_nfa("(a|b)*abb")
    small = regex_to_nfa("a")
    assert small.states == {"q0", "q1"}
    assert small.transitions == {("q0", "a"): {"q1"}}
    big.transitions[("q0", "a")].add("q5")  # mutating one result must not affect another
    assert regex_to_nfa("(a|b)*abb").transitions[("q0", "a")] == {"q1"}


# --- construction trace --------------------------------------------------

def test_trace_records_each_postfix_token():
    result = construct_nfa(parse_regex("ab|c"))
    assert [(s.token, s.operation) for s in result.steps] == [
        ("a", "Literal"), ("b", "Literal"), (".", "Concatenation"), ("c", "Literal"), ("|", "Union"),
    ]
    assert [s.stack_depth for s in result.steps] == [1, 2, 1, 2, 1]
    assert result.steps[2].fragment == NFAFragment("q0", "q3")
    assert result.steps[2].new_transitions == (("q1", None, "q2"),)
    assert result.steps[-1].fragment.start == result.automaton.initial_state
    assert {result.steps[-1].fragment.end} == result.automaton.accepting_states


def test_trace_transitions_add_up_to_automaton():
    result = construct_nfa(parse_regex("((a|b)c)*d?"))
    traced = sorted(t for step in result.steps for t in step.new_transitions)
    assert traced == sorted(result.automaton.transition_list())


# --- K: error handling ----------------------------------------------------

def make_parsed(postfix, alphabet=("a", "b")):
    return ParsedRegex(original="(manual)", infix=(), postfix=tuple(postfix), alphabet=frozenset(alphabet))


def test_invalid_regex_raises_syntax_error():
    with pytest.raises(RegexSyntaxError):
        regex_to_nfa("a||b")


def test_missing_operand_is_reported():
    with pytest.raises(ConstructionError, match="needs 2 operand"):
        construct_nfa(make_parsed([Token(LITERAL, "a"), Token(UNION, "|")]))


def test_unary_operator_without_operand():
    with pytest.raises(ConstructionError, match="needs 1 operand"):
        construct_nfa(make_parsed([Token(STAR, "*")]))


def test_leftover_fragments_are_reported():
    with pytest.raises(ConstructionError, match="left 2 fragments"):
        construct_nfa(make_parsed([Token(LITERAL, "a"), Token(LITERAL, "b")]))


def test_empty_postfix_is_reported():
    with pytest.raises(ConstructionError, match="left 0 fragments"):
        construct_nfa(make_parsed([]))


def test_parenthesis_token_is_rejected():
    with pytest.raises(ConstructionError, match="cannot appear in a postfix"):
        construct_nfa(make_parsed([Token("LEFT_PAREN", "(")]))


def test_unknown_token_kind_is_rejected():
    with pytest.raises(ConstructionError, match="cannot appear in a postfix"):
        construct_nfa(make_parsed([Token(LITERAL, "a"), Token("WILDCARD", "~")]))


def test_alphabet_mismatch_is_reported():
    postfix = [Token(LITERAL, "a"), Token(LITERAL, "c"), Token(CONCAT, ".")]
    with pytest.raises(ConstructionError, match="not in the alphabet"):
        construct_nfa(make_parsed(postfix, alphabet=("a",)))


def test_state_limit_is_enforced():
    with pytest.raises(ConstructionError, match="more than 10 states"):
        construct_nfa(parse_regex("(a|b)*abb"), max_states=10)


def test_largest_valid_input_fits_default_limit():
    # 256 starred literals is about as many states as a 512-character expression can need.
    nfa = regex_to_nfa("a*" * 256)
    assert len(nfa.states) == 1024 <= MAX_NFA_STATES
    assert nfa_accepts(nfa, "a" * 10)


def test_complex_expression():
    expression = "((a|b)*c(d|e|ε)+f?)|(0|1)*01"
    nfa = regex_to_nfa(expression)
    assert_well_formed(nfa)
    assert_language(expression, ["c", "abcdf", "bbcedd", "01", "1101"], ["", "cdfd", "ab", "0", "cff"])
