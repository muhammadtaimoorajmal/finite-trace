"""Tests for Project 29: (b + bbb + bb)* cc + ad + bbd."""
import itertools
import re

import pytest
from streamlit.testing.v1 import AppTest

from automata.convert import nfa_to_dfa, partial
from automata.diagram import to_dot
from automata.nfa import build_nfa
from automata.regex import PROJECT_RE, NotProjectRegex, RegexError, validate
from automata.simulate import accepts, check_word, run, trace

NFA = build_nfa()
DFA, ROWS, SUBSETS = nfa_to_dfa(NFA)
ORACLE = re.compile(r"b*cc|ad|bbd")  # the same language in Python's regex syntax


# ---------- input validation
@pytest.mark.parametrize("text", [PROJECT_RE, "(b+bbb+bb)*cc+ad+bbd", " ( b + bbb + bb ) * c c + a d + b b d "])
def test_project_regex_is_accepted_with_any_spacing(text):
    validate(text)


@pytest.mark.parametrize("text", ["(a + b)*abb", "(bb + b + bbb)*cc + ad + bbd", "b*cc + ad + bbd", "a",
                                  "(b + bbb + bb)* cc + ad + bbd + ε", "Λ"])
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
    assert NFA.states == list("ABCDEFG") and NFA.start == "A" and NFA.finals == {"G"}
    assert NFA.next("A", "b") == {"B", "E"}  # nondeterministic: loop branch or bbd branch
    assert NFA.next("B", "b") == {"B"}       # the (b + bbb + bb)* loop
    assert NFA.next("D", "d") == NFA.next("C", "c") == NFA.next("F", "d") == {"G"}  # one final state


def test_subset_construction_gives_the_8_state_dfa():
    assert DFA.states == ["q0", "q1", "q2", "q3", "qT", "q4", "q5", "q6"]
    assert SUBSETS == {"q0": "{A}", "q1": "{D}", "q2": "{B,E}", "q3": "{C}", "qT": "φ",
                       "q4": "{G}", "q5": "{B,F}", "q6": "{B}"}
    assert DFA.finals == {"q4"}
    assert all(DFA.next("qT", x) == {"qT"} for x in "abcd")  # trap state
    assert all(len(DFA.next(s, x)) == 1 for s in DFA.states for x in "abcd")  # complete DFA
    assert len(ROWS) == len(DFA.states)
    assert "δ({B,E}, b) = δ(B,b) ∪ δ(E,b) = {B} ∪ {F} = {B,F}  → q5" in ROWS[2]["work"]
    assert partial(DFA, ROWS, 0).states == ["q0"]
    assert partial(DFA, ROWS, 1).states == ["q0", "q1", "q2", "q3", "qT"]


def test_dfa_is_the_same_machine_as_the_hand_drawn_one():
    # hand-drawn DFA from class notes: q0 b-> q1 b-> q2 b-> q3 (loop b), c-> q4 c-> q6, a-> q5 d-> q6, q2 d-> q6
    hand = {("q0", "a"): "q5", ("q0", "b"): "q1", ("q0", "c"): "q4", ("q1", "b"): "q2", ("q1", "c"): "q4",
            ("q2", "b"): "q3", ("q2", "c"): "q4", ("q2", "d"): "q6", ("q3", "b"): "q3", ("q3", "c"): "q4",
            ("q4", "c"): "q6", ("q5", "d"): "q6"}
    rename = {"q0": "q0", "q1": "q5", "q2": "q1", "q3": "q4", "q4": "q6", "q5": "q2", "q6": "q3"}
    for (src, x), dst in hand.items():
        ours_src = next(k for k, v in rename.items() if v == src)
        assert rename[next(iter(DFA.next(ours_src, x)))] == dst


@pytest.mark.parametrize("machine", [NFA, DFA], ids=["NFA", "DFA"])
def test_machine_matches_language_on_every_short_string(machine):
    for n in range(8):
        for word in map("".join, itertools.product("abcd", repeat=n)):
            assert accepts(machine, word) == bool(ORACLE.fullmatch(word)), word


def test_loop_belongs_only_to_cc():
    for word in ["bad", "bbbd", "bbad"]:
        assert not accepts(NFA, word) and not accepts(DFA, word)


def test_trap_state_can_be_hidden_in_the_diagram():
    assert '"qT"' in to_dot(DFA) and '"qT"' not in to_dot(DFA, hide={"qT"})
    # once reached, qT is drawn with only the move actually used (d), not "a, d"
    dot = to_dot(DFA, active={"qT"}, used={("q6", "d", "qT")}, hide={"qT"})
    assert '"q6" -> "qT" [label=" d "' in dot and '"q1" -> "qT"' not in dot
    # "ccadbbd": the move into qT (q4 -a-> qT) stays visible while the run loops in qT
    path = {("q0", "c", "q3"), ("q3", "c", "q4"), ("q4", "a", "qT"), ("qT", "d", "qT"), ("qT", "b", "qT")}
    dot = to_dot(DFA, active={"qT"}, used={("qT", "d", "qT")}, hide={"qT"}, path=path)
    assert '"q4" -> "qT" [label=" a "' in dot and '"qT" -> "qT" [label=" b, d "' in dot
    assert not accepts(DFA, "ccadbbd") and not accepts(NFA, "ccadbbd")


# ---------- simulation trace
def test_trace_lines():
    assert trace(DFA, "ad", run(DFA, "ad")) == [
        "Start: q0", "q0 --a--> q1", "q1 --d--> q4", "q4 is Final State → String Accepted"]
    assert trace(DFA, "bd", run(DFA, "bd"))[-1] == "qT is not a Final State → String Rejected"
    nfa_lines = trace(NFA, "bbd", run(NFA, "bbd"))
    assert nfa_lines[1] == "A --b--> B\nA --b--> E"
    assert nfa_lines[3] == "B --d--> φ (this branch dies)\nF --d--> G"
    assert nfa_lines[-1] == "G is Final State → String Accepted"
    assert trace(NFA, "bad", run(NFA, "bad"))[-1] == "All branches died → String Rejected"
    assert "String Rejected" in check_word(DFA, "abx") and check_word(DFA, "bbd") is None


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
    at = app(r"a\b")  # the backslash is escaped, so it is shown and not swallowed by formatting
    assert r"Invalid symbol '\\'" in at.error[0].value


def test_app_animation_steps():
    at = app()
    next(b for b in at.button if b.key == "conversionn").click().run()
    assert any("Row 1 of 8" in m.value for m in at.markdown)
    next(b for b in at.button if b.key == "NFA:bbdn").click().run()
    assert any("Step 1 of 3" in c.value for c in at.caption)


def test_app_runs_the_typed_string_on_both_machines():
    at = app()
    at.text_input[1].set_value("bbbd")
    next(b for b in at.button if b.label == "Run ▶").click().run()
    assert any("DFA reading “bbbd”" in m.value for m in at.markdown)
    for _ in range(4):
        next(b for b in at.button if b.key == "DFA:bbbdn").click().run()
    assert any("qT is not a Final State → String Rejected" in e.value for e in at.error)
    at.text_input[1].set_value("ε")
    next(b for b in at.button if b.label == "Run ▶").click().run()
    assert any("DFA reading “ε”" in m.value for m in at.markdown)
    at.text_input[1].set_value("abx")
    next(b for b in at.button if b.label == "Run ▶").click().run()
    assert any("'x'" in e.value for e in at.error) and not at.exception
