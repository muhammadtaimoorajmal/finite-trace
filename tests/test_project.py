"""Tests for Project 29: (b + bbb + bb)* cc + ad + bbd."""
import itertools
import re

import pytest
from streamlit.testing.v1 import AppTest

from automata import build_all
from automata.regex import PROJECT_RE, NotProjectRegex, RegexError, to_postfix, validate
from automata.simulate import accepts, check_word, run, trace

R = build_all()
NFA, DFA, MIN = R["nfa"], R["dfa"], R["min_dfa"]
ORACLE = re.compile(r"b*cc|ad|bbd")  # the same language written in Python's regex syntax


# ---------- input validation
@pytest.mark.parametrize("text", [PROJECT_RE, "(b+bbb+bb)*cc+ad+bbd", "  ( b + bbb + bb ) * c c + a d + b b d "])
def test_project_regex_is_accepted_with_any_spacing(text):
    validate(text)  # must not raise


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
    ("a(+b)", "no left-hand side"),
    ("(a+)b", "no right-hand side"),
    ("a()b", "Empty parentheses"),
    ("a#b", "Invalid symbol '#' at position 2"),
])
def test_malformed_regexes_give_clear_errors(text, message):
    with pytest.raises(RegexError, match=message):
        validate(text)


def test_postfix():
    assert "".join(to_postfix(PROJECT_RE)) == "bbb.b.+bb.+*c.c.ad.+bb.d.+"


# ---------- the three machines
def test_thompson_nfa_size():
    assert len(NFA.states) == 36 and NFA.start == "q0" and len(NFA.finals) == 1
    assert sum(len(v) for v in NFA.delta.values()) == 41
    assert sum(len(v) for (_, symbol), v in NFA.delta.items() if symbol == "ε") == 28
    assert R["nfa_steps"][-1]["Sub-expression"] == "(b + bbb + bb)*cc + ad + bbd"


def test_subset_construction():
    assert len(DFA.states) == 10 and DFA.finals == {"D5", "D7", "D9"}
    assert R["subsets"]["D4"] == frozenset()  # dead state
    for name, subset in R["subsets"].items():  # final DFA state <=> subset contains the NFA final state
        assert (name in DFA.finals) == bool(subset & NFA.finals)
    for state in DFA.states:  # complete and deterministic
        assert all(len(DFA.next(state, a)) == 1 for a in DFA.alphabet)


def test_table_filling_merges_the_three_final_states():
    assert len(MIN.states) == 8
    assert [g for g in R["groups"] if len(g) > 1] == [["D5", "D7", "D9"]]


@pytest.mark.parametrize("machine", [NFA, DFA, MIN], ids=["e-NFA", "DFA", "minDFA"])
def test_machine_matches_language_on_every_short_string(machine):
    for n in range(8):
        for word in map("".join, itertools.product("abcd", repeat=n)):
            assert accepts(machine, word) == bool(ORACLE.fullmatch(word)), word


# ---------- simulation
def test_trace_lines():
    lines = trace(DFA, "ad", run(DFA, "ad"))
    assert lines == ["Start: D0", "D0 --a--> D1", "D1 --d--> D5", "D5 is Final State → String Accepted"]
    assert trace(MIN, "bd", run(MIN, "bd"))[-1].endswith("String Rejected")
    assert not accepts(NFA, "")


def test_symbols_outside_alphabet_are_reported():
    assert check_word(DFA, "abx") and "'x'" in check_word(DFA, "abx")
    assert check_word(DFA, "bbd") is None


# ---------- interface
def build(text):
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    at.text_input[0].set_value(text)
    at.button[0].click().run()
    return at


def test_app_builds_all_tabs_for_project_regex():
    at = build(PROJECT_RE)
    assert not at.exception and at.success and len(at.tabs) == 4
    assert [m.value for m in at.metric][1:] == ["36", "10", "8"]


def test_app_declines_other_regex_and_shows_syntax_errors():
    at = build("(a + b)*abb")
    assert "built only for Project 29" in at.warning[0].value and not at.tabs
    at = build("(a+b")
    assert "Invalid Regular Expression: Missing closing parenthesis" in at.error[0].value


def test_app_simulator_reports_bad_strings_and_steps_the_animation():
    at = build(PROJECT_RE)
    at.text_area[0].set_value("bbd\nabx").run()
    assert any("'x'" in e.value for e in at.error)
    next_button = next(b for b in at.button if b.label == "Next ▶")
    next_button.click().run()
    assert any("Step 1 of 3" in c.value for c in at.caption)
