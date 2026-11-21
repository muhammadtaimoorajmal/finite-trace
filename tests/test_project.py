"""Tests for Project 29: (b + bbb + bb)* cc + ad + bbd."""
import itertools
import re

import pytest
from streamlit.testing.v1 import AppTest

from automata.convert import nfa_to_dfa, partial
from automata.nfa import build_nfa
from automata.regex import PROJECT_RE, NotProjectRegex, RegexError, validate
from automata.simulate import accepts, check_word, run, trace

NFA = build_nfa()
DFA, ROWS = nfa_to_dfa(NFA)
ORACLE = re.compile(r"b*cc|ad|bbd")  # the same language in Python's regex syntax


# ---------- input validation
@pytest.mark.parametrize("text", [PROJECT_RE, "(b+bbb+bb)*cc+ad+bbd", " ( b + bbb + bb ) * c c + a d + b b d "])
def test_project_regex_is_accepted_with_any_spacing(text):
    validate(text)


@pytest.mark.parametrize("text", ["(a + b)*abb", "(bb + b + bbb)*cc + ad + bbd", "b*cc + ad + bbd", "a"])
def test_other_valid_regexes_are_declined(text):
    with pytest.raises(NotProjectRegex, match="built only for Project 29"):
        validate(text)


@pytest.mark.parametrize("text, message", [
    ("", "Please enter a regular expression"),
    ("(a+b", "Missing closing parenthesis for '\\(' at position 1"),
    ("a++b", "Two operators in a row \\('\\+\\+'\\) at position 3"),
    ("a+b)", "Unmatched closing parenthesis at position 4"),
    ("*ab", "'\\*' at position 1 has nothing to repeat"),
    ("a+", "has no right-hand side"),
    ("+a", "'\\+' at position 1 has no left-hand side"),
    ("a()b", "Empty parentheses"),
    ("a#b", "Invalid symbol '#' at position 2"),
])
def test_malformed_regexes_give_clear_errors(text, message):
    with pytest.raises(RegexError, match=message):
        validate(text)


# ---------- NFA and DFA
def test_nfa_has_one_branch_per_term():
    assert NFA.states == [f"q{i}" for i in range(9)] and NFA.start == "q0"
    assert NFA.finals == {"q3", "q5", "q8"}
    assert NFA.next("q0", "b") == {"q1", "q6"}  # nondeterministic: loop branch or bbd branch
    assert NFA.next("q1", "b") == {"q1"}        # the (b + bbb + bb)* loop


def test_subset_construction():
    assert DFA.states == ["{q0}", "{q4}", "{q1,q6}", "{q2}", "φ", "{q5}", "{q1,q7}", "{q3}", "{q1}", "{q8}"]
    assert DFA.finals == {"{q3}", "{q5}", "{q8}"}
    assert DFA.next("{q1,q6}", "b") == {"{q1,q7}"}
    assert all(DFA.next("φ", x) == {"φ"} for x in "abcd")  # dead state
    assert all(len(DFA.next(s, x)) == 1 for s in DFA.states for x in "abcd")  # complete DFA
    assert len(ROWS) == len(DFA.states)
    assert "δ({q1,q6}, b) = δ(q1,b) ∪ δ(q6,b) = {q1} ∪ {q7} = {q1,q7}" in ROWS[2]["work"]
    assert partial(DFA, ROWS, 0).states == ["{q0}"]
    assert partial(DFA, ROWS, 1).states == ["{q0}", "{q4}", "{q1,q6}", "{q2}", "φ"]


@pytest.mark.parametrize("machine", [NFA, DFA], ids=["NFA", "DFA"])
def test_machine_matches_language_on_every_short_string(machine):
    for n in range(8):
        for word in map("".join, itertools.product("abcd", repeat=n)):
            assert accepts(machine, word) == bool(ORACLE.fullmatch(word)), word


def test_loop_belongs_only_to_cc():
    for word in ["bad", "bbbd", "bbad"]:
        assert not accepts(NFA, word) and not accepts(DFA, word)


# ---------- simulation trace
def test_trace_lines():
    assert trace(DFA, "ad", run(DFA, "ad")) == [
        "Start: {q0}", "{q0} --a--> {q4}", "{q4} --d--> {q5}", "{q5} is Final State → String Accepted"]
    nfa_lines = trace(NFA, "bbd", run(NFA, "bbd"))
    assert nfa_lines[1] == "q0 --b--> q1\nq0 --b--> q6"
    assert "q1 --d--> φ (this branch dies)" in nfa_lines[3]
    assert nfa_lines[-1] == "q8 is Final State → String Accepted"
    assert trace(NFA, "bad", run(NFA, "bad"))[-1] == "All branches died → String Rejected"
    assert check_word(DFA, "abx") and check_word(DFA, "bbd") is None


# ---------- interface
def app(text=None):
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    if text is not None:
        at.text_input[0].set_value(text).run()
    return at


def test_app_shows_all_tabs_for_project_regex():
    at = app()
    assert not at.exception and at.success and len(at.tabs) == 4


def test_app_declines_other_regex_and_shows_syntax_errors():
    at = app("(a + b)*abb")
    assert "built only for Project 29" in at.warning[0].value and not at.tabs
    at = app("(a+b")
    assert "Invalid Regular Expression: Missing closing parenthesis" in at.error[0].value


def test_app_animation_steps():
    at = app()
    next(b for b in at.button if b.key == "conversionn").click().run()
    assert any("Row 1 of 10" in m.value for m in at.markdown)
    next(b for b in at.button if b.key == "NFA:bbdn").click().run()
    assert any("Step 1 of 3" in c.value for c in at.caption)
