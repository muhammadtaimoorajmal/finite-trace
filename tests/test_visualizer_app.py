"""AppTest workflows for state diagrams in the Builder, Converter and Simulator (Module 07)."""

from core.converter import regex_to_dfa
from core.simulator import simulate
from core.thompson import regex_to_nfa
from test_app import builder_dfa, convert_in_app, frame_with_column, generate_in_app, parse_in_app, run_app
from test_app_modes import EPSILON_NFA, EVEN_ZEROS, generate_rule, set_manual
from test_simulator_app import simulate_regex, verdicts
from test_visualizer import parse_dot
from ui.visualizer import automaton_to_dot


def charts(app):
    """The DOT source of every graphviz chart on the page."""
    return [chart.proto.spec for chart in app.get("graphviz_chart")]


def chart_alts(app):
    return [chart.proto.alt for chart in app.get("graphviz_chart")]


def downloads(app):
    return app.get("download_button")


def test_no_diagrams_before_anything_is_built():
    app = run_app()
    assert not app.exception
    assert charts(app) == []


def test_1_regex_nfa_diagram_with_table():
    app = generate_in_app(run_app(), "(a|b)*abb")
    assert not app.exception
    assert charts(app) == [automaton_to_dot(regex_to_nfa("(a|b)*abb"))]
    assert chart_alts(app)[0].startswith("NFA state diagram with 14 states, initial state q6")
    assert len(frame_with_column(app, "Source")) == 16  # transition listing still shown
    assert [d.label for d in downloads(app)] == ["Download DOT"]


def test_2_regex_dfa_diagram():
    app = builder_dfa(run_app(), "(a|b)*abb")
    assert charts(app) == [automaton_to_dot(regex_to_dfa("(a|b)*abb"))]
    assert "accepting states D4" in chart_alts(app)[0]


def test_3_language_rule_diagram():
    app = generate_rule(run_app(), "0,1", "Ends with", pattern="01")
    (dot,) = charts(app)
    nodes, edges = parse_dot(dot)
    assert sum(1 for n in nodes.values() if n.get("shape") == "doublecircle") == 1
    assert len([e for e in edges if e[0] != "start"]) == 6


def test_4_exact_string_diagram():
    app = run_app()
    app.text_input(key="exact_alphabet").input("a,b")
    app.text_input(key="exact_text").input("aabb")
    app.button(key="exact_generate").click()
    app.run()
    (dot,) = charts(app)
    nodes, edges = parse_dot(dot)
    assert len(nodes) == 7  # six states plus the start marker
    assert len(edges) == 13  # 12 transitions plus the start arrow


def test_5_manual_dfa_diagram():
    app = set_manual(run_app(), EVEN_ZEROS)
    (dot,) = charts(app)
    assert 'label=q0' in dot and "shape=doublecircle" in dot


def test_6_manual_nfa_diagram():
    app = set_manual(run_app(), EPSILON_NFA)
    (dot,) = charts(app)
    _, edges = parse_dot(dot)
    assert sorted(attrs["label"] for s, _, attrs in edges if s != "start") == ["a", "b", "ε", "ε"]


def test_7_regex_conversion_diagrams():
    app = convert_in_app(run_app(), "(0|1)*01")
    assert not app.exception
    nfa, dfa = regex_to_nfa("(0|1)*01"), regex_to_dfa("(0|1)*01")
    assert charts(app) == [automaton_to_dot(nfa), automaton_to_dot(dfa)]
    assert len(frame_with_column(app, "move(S, x)")) == 8  # conversion steps still shown
    assert {d.label for d in downloads(app)} == {"Download DOT"} and len(downloads(app)) == 2


def test_8_manual_conversion_diagrams():
    app = set_manual(run_app(), EPSILON_NFA)
    app.button(key="convert_manual_button").click()
    app.run()
    # Builder manual NFA, converter's source NFA and converted DFA.
    dots = charts(app)
    assert len(dots) == 3 and dots[0] == dots[1]
    dfa_nodes, _ = parse_dot(dots[2])
    assert sorted(attrs["label"] for n, attrs in dfa_nodes.items() if n != "start") == ["D0", "D1", "D2"]


def test_9_simulation_diagram_shows_step_0_highlighting():
    # Since Module 08 the simulator diagram is animated; it opens on step 0 of the real trace.
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    assert verdicts(app)[0]
    dfa = regex_to_dfa("(a|b)*abb")
    step0 = simulate(dfa, "aabb").steps[0]
    assert charts(app) == [automaton_to_dot(dfa, highlight_states=step0.active_after,
                                            highlight_edges=step0.symbol_edges + step0.epsilon_edges)]


def test_10_invalid_input_shows_no_diagram():
    app = generate_in_app(run_app(), "(a|b)*abb")
    assert charts(app)
    app = generate_in_app(app, "a||b")
    assert charts(app) == [] and app.error
    bad = dict(EVEN_ZEROS, manual_transitions="q0,0,q1")
    app = set_manual(app, bad)
    assert charts(app) == []


def test_11_changed_input_hides_diagram():
    app = generate_rule(run_app(), "0,1", "Contains substring", pattern="00")
    assert len(charts(app)) == 1
    app.text_input(key="lang_pattern").input("000").run()
    assert charts(app) == []


def test_12_large_automaton_shows_notice_and_table():
    app = generate_in_app(run_app(), "a*" * 40)
    assert not app.exception
    assert charts(app) == []
    assert any("more than the diagram limit" in w.value for w in app.warning)
    full = len(regex_to_nfa("a*" * 40).transition_list())  # 239: 40 symbol + 199 ε-transitions
    assert len(frame_with_column(app, "Source")) == full  # the full transition listing, not truncated
    assert len(downloads(app)) == 1  # complete DOT still downloadable


def test_layout_control_switches_direction():
    app = generate_in_app(run_app(), "ab")
    assert "rankdir=LR" in charts(app)[0]
    app.radio(key="diagram_direction").set_value("Top to bottom").run()
    assert "rankdir=TB" in charts(app)[0]


def test_13_existing_workflows_still_work():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert [s.value for s in app.success] == ["Valid expression"]
    assert charts(app) == []  # parsing alone produces no automaton
    app = builder_dfa(app, "(a|b)*abb")
    app = simulate_regex(app, "(a|b)*abb", "NFA", "abab")
    assert verdicts(app)[1]
