"""
Robustness, safety and consistency checks across the application (Module 09).

Covers input limits, malformed input in every form, cross-session isolation,
output escaping, DOT download content, table column types, the automatic
diagram layout, and agreement between the README's stated limits and the code.
"""

import pathlib
import re

import pytest

import ui.visualizer as visualizer
from core.converter import MAX_DFA_STATES, regex_to_dfa
from core.language_builder import MAX_COUNT, MAX_EXACT_STRING_LENGTH, MAX_PATTERN_LENGTH
from core.manual_builder import (
    MAX_ALPHABET_SIZE,
    MAX_STATE_NAME_LENGTH,
    MAX_STATES,
    MAX_TRANSITION_ROWS,
    parse_and_build,
)
from core.regex_parser import MAX_EXPRESSION_LENGTH
from core.simulator import MAX_SIMULATION_LENGTH
from core.thompson import MAX_NFA_STATES, regex_to_nfa
from test_animation_app import press
from test_app import builder_dfa, convert_in_app, generate_in_app, parse_in_app, run_app
from test_app_modes import EPSILON_NFA, EVEN_ZEROS, generate_rule, set_manual
from test_simulator_app import simulate_regex, simulate_saved
from test_visualizer import assert_diagram_matches
from ui.animation import input_tape_html
from ui.visualizer import AUTO_LEFT_TO_RIGHT_MAX_STATES, automaton_to_dot, layout_direction

ROOT = pathlib.Path(__file__).resolve().parent.parent


# --- documentation agrees with the code ----------------------------------------------

@pytest.mark.parametrize(
    "value",
    [MAX_EXPRESSION_LENGTH, MAX_NFA_STATES, MAX_DFA_STATES, MAX_STATES, MAX_TRANSITION_ROWS,
     MAX_EXACT_STRING_LENGTH, MAX_SIMULATION_LENGTH, MAX_PATTERN_LENGTH, MAX_ALPHABET_SIZE,
     MAX_STATE_NAME_LENGTH, MAX_COUNT, visualizer.MAX_DIAGRAM_STATES, visualizer.MAX_DIAGRAM_EDGES,
     AUTO_LEFT_TO_RIGHT_MAX_STATES],
)
def test_readme_states_each_limit(value):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(rf"\b{value:,}\b", readme), f"README does not mention the limit {value:,}"


def test_no_dynamic_code_execution_in_application_code():
    sources = [ROOT / "app.py", *(ROOT / "core").glob("*.py"), *(ROOT / "ui").glob("*.py")]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(eval|exec)\(|subprocess|os\.system", text), path.name


# --- malformed input never crashes the app or shows a result -----------------------

@pytest.mark.parametrize("expression", ["", "a||b", "(ab", "ab)", "*a", "a**", "a+?", "[ab]", "a{2}", "a\\", "a" * 513])
def test_invalid_regex_shows_error_everywhere(expression):
    app = builder_dfa(run_app(), expression)
    assert not app.exception and app.error and not app.success
    app = convert_in_app(app, expression)
    assert not app.exception and not any("Converted" in s.value for s in app.success)
    app = simulate_regex(app, expression, "NFA", "a")
    assert not app.exception and len(app.error) >= 1
    assert not any(s.value.startswith("**Accepted**") for s in app.success)
    assert not any("Traceback" in e.value for e in app.error)


@pytest.mark.parametrize(
    "alphabet, rule, kwargs",
    [("0,,1", "Ends with", {"pattern": "01"}), ("0,1", "Ends with", {"pattern": ""}),
     ("0,1", "Contains substring", {"pattern": "0x"}), ("0,1", "Even number of a symbol", {"symbol": "z"}),
     ("ab", "Starts with", {"pattern": "a"})],
)
def test_invalid_language_rules_show_error(alphabet, rule, kwargs):
    app = generate_rule(run_app(), alphabet, rule, **kwargs)
    assert not app.exception and app.error and not app.success


@pytest.mark.parametrize(
    "changes",
    [{"manual_states": ""}, {"manual_initial": "q9"}, {"manual_transitions": "q0,0"},
     {"manual_transitions": "q0,0,q1\nq0,0,q0\nq0,1,q0\nq1,0,q0\nq1,1,q1"}, {"manual_alphabet": "0,ε"},
     {"manual_transitions": "q0,ε,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1"}, {"manual_states": "q0,q 1"}],
)
def test_invalid_manual_definitions_show_error(changes):
    app = set_manual(run_app(), dict(EVEN_ZEROS, **changes))
    assert not app.exception and app.error and not app.success


def test_simulation_input_errors():
    app = simulate_regex(run_app(), "a*", "DFA", "ε")
    assert "leave the test string empty" in app.error[0].value
    app = simulate_regex(app, "a*", "DFA", "a" * (MAX_SIMULATION_LENGTH + 1))
    assert f"maximum is {MAX_SIMULATION_LENGTH}" in app.error[0].value
    app = simulate_regex(app, "(a|b)*a" + "(a|b)" * 9, "DFA", "a")
    assert f"more than {MAX_DFA_STATES} states" in app.error[0].value


# --- sessions are isolated --------------------------------------------------------

def test_two_sessions_do_not_share_results_or_playback():
    first = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    second = simulate_regex(run_app(), "ab", "NFA", "ab")
    first = press(first, "next")
    first = press(first, "next")
    second.run()
    assert first.session_state["sim_regex_outcome_playback"].current_step == 2
    assert second.session_state["sim_regex_outcome_playback"].current_step == 0
    assert second.text_input(key="sim_regex").value == "ab"
    assert "builder_outcome" not in second.session_state


# --- saved-automaton dropdown follows options appearing and disappearing ---------------

def test_simulator_dropdown_follows_available_automata():
    app = set_manual(run_app(), EVEN_ZEROS)
    assert app.selectbox(key="sim_builder_choice").value.startswith("Manual Automaton")
    app.text_input(key="manual_accepting").input("q1").run()  # manual result becomes stale
    app = generate_rule(app, "0,1", "Ends with", pattern="01")
    box = app.selectbox(key="sim_builder_choice")
    assert box.options == [o for o in box.options if o.startswith("Language Rule")]
    assert box.value == box.options[0]
    app.text_input(key="sim_builder_text").input("01")
    app.button(key="sim_builder_button").click()
    app.run()
    assert any(s.value.startswith("**Accepted**") for s in app.success)


# --- every table column holds a single type (pyarrow rejects mixed columns) ------------

def _assert_single_type_columns(app):
    for frame in app.dataframe:
        for column in frame.value.columns:
            kinds = {type(value).__name__ for value in frame.value[column] if value is not None}
            assert len(kinds) <= 1, f"column {column!r} mixes {kinds}"


def test_dataframe_columns_have_consistent_types():
    app = parse_in_app(run_app(), "(a|b)*abb")
    _assert_single_type_columns(app)
    app = generate_in_app(app, "(a|b)*abb")
    _assert_single_type_columns(app)
    app = builder_dfa(app, "ab")
    app = convert_in_app(app, "(0|1)*01")
    app = generate_rule(app, "0,1", "Ends with", pattern="01")
    app = set_manual(app, EPSILON_NFA)
    app = simulate_regex(app, "(a|b)*abb", "DFA", "aabb")
    app = simulate_saved(app, "sim_builder", "Manual Automaton", "a")
    _assert_single_type_columns(app)


# --- output escaping ---------------------------------------------------------------

def test_input_tape_escapes_every_ascii_punctuation_character():
    punctuation = "!\"#$%&'()*+-./:;<=>?@[\\]^_`{|}~"
    html = input_tape_html(punctuation, 3)
    for dangerous in "<>\"'":
        assert f">{dangerous}<" not in html  # never inserted raw between tags
    assert html.count("<span") == len(punctuation)


def test_dot_output_survives_hostile_looking_symbols_and_names():
    symbols = ['"', "\\", "<", ">", "{", "}", "[", "]", ";", "=", "#", "|"]
    states = ["q0", "a-b", "x'y", "S.1", "end_"]
    rows = "\n".join(f"{states[i % 5]},{s},{states[(i + 1) % 5]}" for i, s in enumerate(symbols))
    nfa = parse_and_build("NFA", ",".join(symbols), ",".join(states), "q0", "end_", rows)
    assert_diagram_matches(nfa)
    # A label like  "] ; evil -> x [  can never create extra nodes: every node is an internal id.
    dot = automaton_to_dot(nfa)
    declared = [n for n in re.findall(r"^\t(\w+) \[", dot, flags=re.M) if n not in ("node", "edge", "graph")]
    assert sorted(declared) == sorted(["start"] + [f"s{i}" for i in range(len(states))])


# --- DOT download is the complete automaton ------------------------------------------

def test_download_contains_complete_plain_dot(monkeypatch):
    captured = {}
    monkeypatch.setattr(visualizer.st, "session_state", {})  # called outside `streamlit run`
    monkeypatch.setattr(visualizer.st, "graphviz_chart", lambda *a, **k: None)
    monkeypatch.setattr(visualizer.st, "download_button", lambda label, data, **k: captured.update(data=data, **k))
    dfa = regex_to_dfa("(a|b)*abb")
    visualizer.render_automaton_diagram(dfa, key="t", highlight_states={"D1"}, highlight_edges={("D0", "a", "D1")})
    assert captured["data"] == automaton_to_dot(dfa)  # complete, unhighlighted automaton
    assert captured["file_name"] == "finite-trace-dfa.dot"
    big = regex_to_nfa("a*" * 40)  # above the diagram limit: no chart, but the full DOT
    visualizer.render_automaton_diagram(big, key="t2")
    assert captured["data"] == automaton_to_dot(big, direction="TB")
    assert captured["data"].count(" -> ") == len(big.transition_list()) + 1  # every edge plus the start arrow


# --- automatic diagram layout ------------------------------------------------------

def test_automatic_layout_depends_only_on_size():
    small, large = regex_to_nfa("(a|b)*abb"), regex_to_nfa("(a|b)*a(a|b)(a|b)(a|b)")
    assert len(small.states) <= AUTO_LEFT_TO_RIGHT_MAX_STATES < len(large.states)
    assert layout_direction(small) == "LR" and layout_direction(large) == "TB"
    assert layout_direction(large, "Left to right") == "LR"
    assert layout_direction(small, "Top to bottom") == "TB"


def test_app_uses_automatic_layout_by_default():
    app = generate_in_app(run_app(), "(a|b)*a(a|b)(a|b)(a|b)")  # 34 states
    assert app.radio(key="diagram_direction").value == "Automatic"
    assert "rankdir=TB" in app.get("graphviz_chart")[0].proto.spec
    app = generate_in_app(app, "ab")
    assert "rankdir=LR" in app.get("graphviz_chart")[0].proto.spec
