"""
AppTest workflows for the interactive playback panel in the String Simulator (Module 08).

AppTest does not run browser timers, so automatic timed playback is covered by
the fake-clock tests in test_animation.py and was checked in a real browser;
here the buttons, frames and state handling are exercised.
"""

import re

from core.converter import regex_to_dfa
from core.simulator import simulate
from test_app import builder_dfa, convert_in_app, generate_in_app, parse_in_app, run_app
from test_app_modes import EPSILON_NFA, set_manual
from test_simulator_app import simulate_regex, verdicts
from test_visualizer import parse_dot
from ui.animation import frame_highlights
from ui.visualizer import automaton_to_dot

PANEL = "sim_regex_outcome_playback"


def frame(app):
    """(step, total, status) from the 'Step i of n · status' line, or None."""
    for block in app.markdown:
        if (match := re.fullmatch(r"\*\*Step (\d+) of (\d+)\*\* · (\w+)", block.value)):
            return int(match[1]), int(match[2]), match[3]
    return None


def press(app, name, panel=PANEL):
    app.button(key=f"{panel}_{name}").click()
    return app.run()


def highlighted_states(app):
    (chart,) = [c for c in app.get("graphviz_chart") if "penwidth=3" in c.proto.spec or "fbbf24" in c.proto.spec][-1:] or [None]
    nodes, _ = parse_dot(chart.proto.spec)
    return {a["label"] for n, a in nodes.items() if a.get("penwidth") == "3"}


def controls(app, panel=PANEL):
    return {b.label: b.disabled for b in app.button if b.key and b.key.startswith(panel + "_")}


def test_a_b_controls_and_initial_frame():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    assert not app.exception
    assert frame(app) == (0, 4, "Ready")
    assert controls(app) == {"↺ Reset": True, "⏮ Previous": True, "▶ Play": False, "⏸ Pause": True,
                             "⏭ Next": False, "⟳ Replay": False}
    assert app.select_slider(key=f"{PANEL}_speed").value == "Normal (1 s)"
    assert highlighted_states(app) == {"D0"}
    assert app.progress[0].value == 0


def test_c_d_e_next_previous_reset():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    dfa = regex_to_dfa("(a|b)*abb")
    trace = simulate(dfa, "aabb")
    app = press(app, "next")
    assert frame(app) == (1, 4, "Paused") and highlighted_states(app) == {"D1"}
    app = press(app, "next")
    app = press(app, "next")
    assert frame(app)[0] == 3
    states, edges = frame_highlights(trace, 3)
    assert [c.proto.spec for c in app.get("graphviz_chart")] == [
        automaton_to_dot(dfa, highlight_states=states, highlight_edges=edges)]
    assert any(c.value == "Read 'b': moved from D1 to D3." for c in app.caption)
    app = press(app, "previous")
    assert frame(app)[0] == 2 and highlighted_states(app) == {"D1"}
    app = press(app, "reset")
    assert frame(app) == (0, 4, "Ready") and highlighted_states(app) == {"D0"}


def test_f_play_and_pause_change_state():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app = press(app, "play")
    assert frame(app) == (0, 4, "Playing")
    assert controls(app)["⏸ Pause"] is False and controls(app)["▶ Play"] is True
    app = press(app, "pause")
    assert frame(app) == (0, 4, "Ready")
    app = press(app, "next")
    app = press(app, "play")
    app = press(app, "pause")
    assert frame(app) == (1, 4, "Paused")


def test_g_final_frame_shows_matching_verdict():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "abab")
    for _ in range(4):
        app = press(app, "next")
    assert frame(app) == (4, 4, "Completed")
    assert controls(app)["⏭ Next"] and controls(app)["▶ Play"]
    finals = [w.value for w in app.warning if "Final configuration" in w.value]
    assert finals and finals[0].startswith("**Final configuration: Rejected.**")
    assert verdicts(app)[1]  # the main verdict agrees
    assert app.progress[0].value == 100  # AppTest reports progress as a percentage


def test_replay_returns_to_start_and_plays():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    for _ in range(4):
        app = press(app, "next")
    app = press(app, "replay")
    assert frame(app) == (0, 4, "Playing")


def test_h_empty_string_has_one_frame():
    app = simulate_regex(run_app(), "a*", "NFA", "")
    assert frame(app) == (0, 0, "Completed")
    assert controls(app)["⏭ Next"] and controls(app)["▶ Play"] and controls(app)["⟳ Replay"]
    assert any("Final configuration: Accepted" in s.value for s in app.success)
    app = simulate_regex(app, "a+", "NFA", "")
    assert any("Final configuration: Rejected" in w.value for w in app.warning)


def test_i_nfa_highlights_every_active_state():
    app = set_manual(run_app(), EPSILON_NFA)
    box = app.selectbox(key="sim_builder_choice")
    assert box.value.startswith("Manual Automaton")
    app.text_input(key="sim_builder_text").input("a")
    app.button(key="sim_builder_button").click()
    app.run()
    panel = "sim_builder_outcome_playback"
    assert frame(app) == (0, 1, "Ready")
    charts = [c.proto.spec for c in app.get("graphviz_chart")]
    nodes, edges = parse_dot(charts[-1])
    labels = {n: a["label"] for n, a in nodes.items() if n != "start"}
    assert {labels[n] for n, a in nodes.items() if a.get("penwidth") == "3"} == {"q0", "q1", "q2"}
    assert {(labels[s], labels[t]) for s, t, a in edges if a.get("penwidth") == "2.5"} == {("q0", "q1"), ("q0", "q2")}
    app = press(app, "next", panel)
    nodes, _ = parse_dot([c.proto.spec for c in app.get("graphviz_chart")][-1])
    assert {a["label"] for a in nodes.values() if a.get("penwidth") == "3"} == {"q3"}
    assert frame(app) == (1, 1, "Completed")


def test_j_invalid_input_shows_no_playback():
    app = simulate_regex(run_app(), "a*", "DFA", "aa")
    assert frame(app)
    app = simulate_regex(app, "a*", "DFA", "ab")
    assert frame(app) is None and app.error
    assert not controls(app)


def test_k_changed_inputs_hide_and_stop_playback():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app = press(app, "play")
    app.text_input(key="sim_regex_text").input("abb").run()
    assert frame(app) is None and not controls(app)
    assert app.session_state[PANEL].playing is False  # the old run no longer advances
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app = press(app, "play")
    app.radio(key="sim_regex_machine").set_value("NFA").run()
    assert frame(app) is None and app.session_state[PANEL].playing is False


def test_l_simulating_again_restarts_at_step_0():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app = press(app, "next")
    app = press(app, "next")
    assert frame(app)[0] == 2
    app.button(key="sim_regex_button").click()
    app.run()
    assert frame(app) == (0, 4, "Ready")


def test_m_trace_table_still_available():
    app = simulate_regex(run_app(), "(a|b)*abb", "DFA", "aabb")
    app = press(app, "next")
    tables = [f.value for f in app.dataframe if "Explanation" in f.value.columns]
    assert len(tables) == 1 and len(tables[0]) == 5


def test_n_other_features_unaffected():
    app = parse_in_app(run_app(), "(a|b)*abb")
    assert [s.value for s in app.success] == ["Valid expression"]
    app = generate_in_app(app, "ab")
    app = builder_dfa(app, "ab")
    app = convert_in_app(app, "(0|1)*01")
    charts = app.get("graphviz_chart")
    assert len(charts) == 3  # Builder DFA + Converter NFA and DFA, all static
    assert all("penwidth=3" not in c.proto.spec for c in charts)
    assert len(app.get("download_button")) == 3
    assert frame(app) is None  # no playback without a simulation


def test_large_automaton_plays_without_a_diagram():
    expression = "a*" * 40  # a 160-state ε-NFA, above the diagram limit
    app = simulate_regex(run_app(), expression, "NFA", "aa")
    assert not app.exception
    assert app.get("graphviz_chart") == []
    assert any("too large to draw" in i.value for i in app.info)
    app = press(app, "next")
    assert frame(app) == (1, 2, "Paused")
    app = press(app, "next")
    assert frame(app) == (2, 2, "Completed")
    assert verdicts(app)[0]
