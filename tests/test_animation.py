"""
Tests for the playback controller and frame highlighting (ui/animation.py).

The controller is plain Python with the clock passed in, so timing is tested
with explicit numbers instead of real sleeps. Highlighting is checked against
real SimulationResults by reading the generated DOT back with parse_dot.
"""

import pytest

from core.converter import convert_nfa_to_dfa, regex_to_dfa
from core.language_builder import ENDS_WITH, build_exact_string_dfa, build_language_dfa
from core.manual_builder import parse_and_build
from core.simulator import simulate
from core.thompson import regex_to_nfa
from test_visualizer import parse_dot
from ui.animation import (
    COMPLETED,
    MIN_SECONDS_PER_STEP,
    PAUSED,
    PLAYING,
    READY,
    SPEEDS,
    _tick_interval,
    advance_playback,
    frame_highlights,
    input_tape_html,
    new_playback,
    next_step,
    pause_playback,
    previous_step,
    replay_playback,
    reset_playback,
    set_speed,
    start_playback,
)
from ui.visualizer import automaton_to_dot


def playback(total_steps=5, seconds=1.0, run_id=1):
    return new_playback(run_id, total_steps, seconds)


# --- A: initialization ------------------------------------------------------

def test_new_playback_starts_ready_at_step_0():
    state = playback(run_id=7)
    assert (state.current_step, state.playing, state.run_id, state.status) == (0, False, 7, READY)


def test_new_playback_needs_at_least_step_0():
    with pytest.raises(ValueError):
        new_playback(1, 0)


# --- B–D: play, pause, resume ------------------------------------------------

def test_play_starts_clock_without_moving():
    state = playback()
    start_playback(state, now=100.0)
    assert state.playing and state.status == PLAYING
    assert state.current_step == 0 and state.last_advance == 100.0


def test_pause_keeps_step_and_resume_continues():
    state = playback()
    start_playback(state, 0.0)
    advance_playback(state, 1.0)
    advance_playback(state, 2.0)
    pause_playback(state)
    assert (state.current_step, state.playing, state.status) == (2, False, PAUSED)
    assert not advance_playback(state, 50.0)  # paused: time passing does nothing
    start_playback(state, 60.0)
    assert state.current_step == 2  # resume does not restart
    advance_playback(state, 61.0)
    assert state.current_step == 3


# --- E–H: next, previous, reset, replay --------------------------------------

def test_next_and_previous_move_exactly_one_step_and_pause():
    state = playback()
    start_playback(state, 0.0)
    next_step(state)
    assert state.current_step == 1 and not state.playing
    next_step(state)
    previous_step(state)
    assert state.current_step == 1


def test_reset_and_replay():
    state = playback()
    for _ in range(3):
        next_step(state)
    start_playback(state, 0.0)
    reset_playback(state)
    assert (state.current_step, state.playing) == (0, False)
    for _ in range(4):
        next_step(state)
    replay_playback(state, now=10.0)
    assert (state.current_step, state.playing, state.last_advance) == (0, True, 10.0)


# --- I: boundaries -----------------------------------------------------------

def test_boundaries():
    state = playback(total_steps=3)
    previous_step(state)
    assert state.current_step == 0
    for _ in range(10):
        next_step(state)
    assert state.current_step == 2 and state.status == COMPLETED


def test_playback_stops_on_last_step_and_never_overshoots():
    state = playback(total_steps=3)
    start_playback(state, 0.0)
    moves = [advance_playback(state, t) for t in (1.0, 2.0, 3.0, 4.0, 100.0)]
    assert moves == [True, True, False, False, False]
    assert (state.current_step, state.playing, state.status) == (2, False, COMPLETED)


def test_play_on_last_step_does_nothing():
    state = playback(total_steps=2)
    next_step(state)
    start_playback(state, 0.0)
    assert not state.playing and state.current_step == 1


def test_empty_string_has_a_single_frame():
    state = playback(total_steps=1)
    assert state.at_end and state.status == COMPLETED
    start_playback(state, 0.0)
    next_step(state)
    assert (state.current_step, state.playing) == (0, False)


# --- J–K: speed and clock --------------------------------------------------------

def test_advance_needs_a_full_interval_and_moves_one_step_per_update():
    state = playback(total_steps=10, seconds=1.0)
    start_playback(state, 0.0)
    assert not advance_playback(state, 0.99)
    assert advance_playback(state, 1.0) and state.current_step == 1
    # A very late update moves only one step (no catch-up burst).
    assert advance_playback(state, 9.0) and state.current_step == 2
    assert not advance_playback(state, 9.5)


def test_speed_change_keeps_step_and_restarts_timer():
    state = playback(total_steps=10, seconds=2.0)
    start_playback(state, 0.0)
    advance_playback(state, 2.0)
    set_speed(state, 0.25, now=2.5)
    assert state.current_step == 1 and state.seconds_per_step == 0.25
    assert not advance_playback(state, 2.7)
    assert advance_playback(state, 2.75) and state.current_step == 2


@pytest.mark.parametrize("seconds", [0, -1, 0.05, float("nan")])
def test_invalid_speeds_are_rejected(seconds):
    with pytest.raises(ValueError):
        set_speed(playback(), seconds, 0.0)


def test_speed_presets_and_tick_interval():
    assert all(seconds >= MIN_SECONDS_PER_STEP for seconds in SPEEDS.values())
    state = playback(seconds=1.0)
    assert _tick_interval(state) is None  # no timer while idle
    start_playback(state, 0.0)
    assert _tick_interval(state) == 0.25
    set_speed(state, 0.25, 0.0)
    assert _tick_interval(state) == MIN_SECONDS_PER_STEP


# --- L–M: replacement and independence -------------------------------------------

def test_controllers_are_independent():
    first, second = playback(run_id=1), playback(run_id=2)
    start_playback(first, 0.0)
    next_step(second)
    advance_playback(first, 1.0)
    assert (first.current_step, first.playing) == (1, True)
    assert (second.current_step, second.playing) == (1, False)


# --- input tape -------------------------------------------------------------------

def test_input_tape_marks_progress_and_escapes_html():
    html = input_tape_html('<a&"\'|', 2)
    assert "&lt;" in html and "&amp;" in html and "&quot;" in html and "&#x27;" in html
    assert "<a&" not in html  # raw characters never reach the page
    assert html.count("#fbbf24;border") == 1  # exactly one current character
    assert "nothing to read" in input_tape_html("", 0)


# --- highlighting real traces ---------------------------------------------------

def highlighted(automaton, simulation, index):
    """(states, edges) styled as active in the DOT for frame `index`, read back from the DOT."""
    states, edges = frame_highlights(simulation, index)
    nodes, drawn = parse_dot(automaton_to_dot(automaton, highlight_states=states, highlight_edges=edges))
    label = {node: attrs["label"] for node, attrs in nodes.items() if node != "start"}
    active = {label[node] for node, attrs in nodes.items() if attrs.get("penwidth") == "3"}
    used = {(label[s], None if a["label"] == "ε" else a["label"], label[t])
            for s, t, a in drawn if a.get("penwidth") == "2.5"}
    return active, used, nodes, drawn


SOURCES = {
    "regex-dfa": (regex_to_dfa("(a|b)*abb"), ["aabb", "abab", ""]),
    "regex-nfa": (regex_to_nfa("(a|b)*abb"), ["aabb", "abab", ""]),
    "language-rule": (build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01"), ["1101", "10"]),
    "exact-string": (build_exact_string_dfa("aabb", {"a", "b"}), ["aabb", "aabba"]),
    "manual-dfa": (parse_and_build("DFA", "0,1", "q0,q1", "q0", "q0", "q0,0,q1\nq0,1,q0\nq1,0,q0\nq1,1,q1"), ["1010", "0"]),
    "manual-nfa": (parse_and_build("NFA", "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3"), ["a", "b", "ab", ""]),
    "manual-converted": (convert_nfa_to_dfa(parse_and_build("NFA", "a,b", "A,B,C", "A", "C",
                                                            "A,a,A\nA,b,A\nA,a,B\nB,a,C\nB,b,C")).dfa, ["aab", "ba"]),
}


@pytest.mark.parametrize("name", SOURCES)
def test_every_frame_highlights_exactly_the_recorded_states_and_edges(name):
    automaton, strings = SOURCES[name]
    plain_nodes, plain_edges = parse_dot(automaton_to_dot(automaton))
    for text in strings:
        simulation = simulate(automaton, text)
        for index, step in enumerate(simulation.steps):
            active, used, nodes, drawn = highlighted(automaton, simulation, index)
            assert active == set(step.active_after)
            assert used == set(step.symbol_edges) | set(step.epsilon_edges)
            # Restyling only: same nodes (ids, labels, shapes) and the same edges in the same order.
            assert {n: (a["label"], a.get("shape")) for n, a in nodes.items()} == \
                   {n: (a["label"], a.get("shape")) for n, a in plain_nodes.items()}
            assert [(s, t, a.get("label"), a.get("id")) for s, t, a in drawn] == \
                   [(s, t, a.get("label"), a.get("id")) for s, t, a in plain_edges]


def test_dfa_frames_follow_the_trace():
    dfa = regex_to_dfa("(a|b)*abb")
    simulation = simulate(dfa, "aabb")
    frames = [highlighted(dfa, simulation, i)[:2] for i in range(len(simulation.steps))]
    assert [sorted(states) for states, _ in frames] == [["D0"], ["D1"], ["D1"], ["D3"], ["D4"]]
    assert frames[3][1] == {("D1", "b", "D3")}


def test_epsilon_nfa_step_0_and_branches():
    nfa = SOURCES["manual-nfa"][0]
    simulation = simulate(nfa, "a")
    states, edges = highlighted(nfa, simulation, 0)[:2]
    assert states == {"q0", "q1", "q2"}
    assert edges == {("q0", None, "q1"), ("q0", None, "q2")}
    assert highlighted(nfa, simulation, 1)[:2] == ({"q3"}, {("q1", "a", "q3")})


def test_multiple_branches_self_loop_and_epsilon_cycle():
    nfa = parse_and_build("NFA", "a,b", "q0,q1,q2,q3,q4", "q0", "q3,q4",
                          "q0,a,q1\nq0,a,q2\nq1,b,q3\nq2,b,q4\nq3,a,q3\nq4,ε,q4")
    simulation = simulate(nfa, "aba")
    assert highlighted(nfa, simulation, 1)[:2] == ({"q1", "q2"}, {("q0", "a", "q1"), ("q0", "a", "q2")})
    states, edges = highlighted(nfa, simulation, 2)[:2]
    assert states == {"q3", "q4"} and {("q1", "b", "q3"), ("q2", "b", "q4"), ("q4", None, "q4")} == edges
    assert highlighted(nfa, simulation, 3)[:2] == ({"q3"}, {("q3", "a", "q3")})  # self-loop
    cycle = parse_and_build("NFA", "a", "q0,q1,q2", "q0", "q2", "q0,ε,q1\nq1,ε,q2\nq2,ε,q0")
    states, edges = highlighted(cycle, simulate(cycle, ""), 0)[:2]
    assert states == {"q0", "q1", "q2"} and len(edges) == 3


def test_empty_active_set_highlights_nothing():
    nfa = parse_and_build("NFA", "a,b", "q0,q1", "q0", "q1", "q0,a,q1")
    simulation = simulate(nfa, "ab")
    assert highlighted(nfa, simulation, 1)[:2] == ({"q1"}, {("q0", "a", "q1")})
    assert highlighted(nfa, simulation, 2)[:2] == (set(), set())
    assert not simulation.accepted


def test_identical_frames_give_identical_dot():
    dfa = regex_to_dfa("(a|b)*abb")
    simulation = simulate(dfa, "abab")
    states, edges = frame_highlights(simulation, 2)
    assert automaton_to_dot(dfa, highlight_states=states, highlight_edges=edges) == \
           automaton_to_dot(dfa, highlight_states=states, highlight_edges=edges)
    # Frame 0 after a reset is the same picture as frame 0 at the start.
    assert frame_highlights(simulation, 0) == frame_highlights(simulate(dfa, "abab"), 0)
