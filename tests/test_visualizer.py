"""
Tests for the state-diagram generator (ui/visualizer.py) and the transition table.

parse_dot() reads the generated DOT text back into nodes and edges, written
independently of the generator, so every test compares the diagram against
the automaton itself rather than just checking that some text was produced.
"""

import re
import shutil
import subprocess

import pytest

from core.automata import DFA, NFA, FiniteAutomaton
from core.converter import convert_nfa_to_dfa, regex_to_dfa
from core.language_builder import ENDS_WITH, build_exact_string_dfa, build_language_dfa
from core.manual_builder import parse_and_build
from core.simulator import simulate
from core.thompson import regex_to_nfa
from ui.automaton_view import transition_grid_rows
from ui.visualizer import (
    MAX_DIAGRAM_EDGES,
    MAX_DIAGRAM_STATES,
    automaton_to_dot,
    build_graph,
    diagram_summary,
    is_too_large,
)

ATTRIBUTE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s\]]+)')
NODE_LINE = re.compile(r"^\t(\w+) \[(.*)\]$")
EDGE_LINE = re.compile(r"^\t(\w+) -> (\w+)(?: \[(.*)\])?$")


def _value(raw: str) -> str:
    if raw.startswith('"'):
        return re.sub(r"\\(.)", r"\1", raw[1:-1])  # undo DOT escaping of \" and \\
    return raw


def _attributes(text: str) -> dict:
    return {key: _value(value) for key, value in ATTRIBUTE.findall(text or "")}


def by_transition(edge):
    source, symbol, destination = edge
    return (source, symbol is None, symbol or "", destination)  # ε (None) sorts after symbols


def parse_dot(dot: str):
    """Return ({node id: attributes}, [(from id, to id, attributes)]) from DOT source."""
    nodes, edges = {}, []
    for line in dot.splitlines():
        if (match := EDGE_LINE.match(line)):
            edges.append((match[1], match[2], _attributes(match[3])))
        elif (match := NODE_LINE.match(line)) and match[1] not in ("node", "edge", "graph"):
            nodes[match[1]] = _attributes(match[2])
    return nodes, edges


def diagram_of(automaton: FiniteAutomaton):
    """The diagram as data: state labels, shapes, the initial state and labelled edges."""
    nodes, edges = parse_dot(automaton_to_dot(automaton))
    label = {node: attrs["label"] for node, attrs in nodes.items() if node != "start"}
    shapes = {label[node]: nodes[node].get("shape", "circle") for node in label}
    starts = [label[target] for source, target, _ in edges if source == "start"]
    transitions = sorted((
        (label[source], None if attrs["label"] == "ε" else attrs["label"], label[target])
        for source, target, attrs in edges if source != "start"
    ), key=by_transition)
    return shapes, starts, transitions


def assert_diagram_matches(automaton: FiniteAutomaton):
    shapes, starts, transitions = diagram_of(automaton)
    assert set(shapes) == automaton.states
    assert len(shapes) == len(automaton.states)  # no duplicated or extra nodes
    assert starts == [automaton.initial_state]
    for state, shape in shapes.items():
        assert shape == ("doublecircle" if state in automaton.accepting_states else "circle"), state
    expected = sorted((
        (source, symbol, destination)
        for (source, symbol), destinations in automaton.transitions.items()
        for destination in destinations
    ), key=by_transition)
    assert transitions == expected  # nothing missing, nothing invented


def make(machine_type, states, alphabet, initial, accepting, transitions):
    return FiniteAutomaton(machine_type, set(states), set(alphabet), initial, set(accepting), dict(transitions))


EVEN_ZEROS = make(DFA, ["q0", "q1"], "01", "q0", ["q0"],
                  {("q0", "0"): {"q1"}, ("q0", "1"): {"q0"}, ("q1", "0"): {"q0"}, ("q1", "1"): {"q1"}})


# --- A–C: basic notation -------------------------------------------------------

def test_basic_dfa():
    dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01")
    assert_diagram_matches(dfa)
    shapes, starts, transitions = diagram_of(dfa)
    assert shapes == {"q0": "circle", "q1": "circle", "q2": "doublecircle"}
    assert starts == ["q0"]
    assert ("q1", "1", "q2") in transitions


def test_start_marker_is_not_a_transition():
    nodes, edges = parse_dot(automaton_to_dot(EVEN_ZEROS))
    assert nodes["start"]["shape"] == "point" and nodes["start"]["label"] == ""
    start_edges = [attrs for source, _, attrs in edges if source == "start"]
    assert len(start_edges) == 1 and "label" not in start_edges[0]


def test_multiple_accepting_states():
    nfa = make(NFA, ["s", "t", "u", "v"], "a", "s", ["t", "u", "v"], {("s", "a"): {"t", "u", "v"}})
    shapes, _, _ = diagram_of(nfa)
    assert [s for s, shape in shapes.items() if shape == "doublecircle"] == ["t", "u", "v"]
    assert_diagram_matches(nfa)


def test_initial_state_can_be_accepting():
    shapes, starts, _ = diagram_of(EVEN_ZEROS)
    assert starts == ["q0"] and shapes["q0"] == "doublecircle"


# --- D–G: branches, ε, self-loops, cycles ----------------------------------------

def test_nfa_branches_are_all_drawn():
    nfa = parse_and_build("NFA", "a", "q0,q1,q2", "q0", "q2", "q0,a,q1\nq0,a,q2")
    _, _, transitions = diagram_of(nfa)
    assert transitions == [("q0", "a", "q1"), ("q0", "a", "q2")]


def test_parallel_symbols_stay_separate_edges():
    nfa = parse_and_build("NFA", "a,b", "q0,q1", "q0", "q1", "q0,a,q1\nq0,b,q1")
    _, _, transitions = diagram_of(nfa)
    assert transitions == [("q0", "a", "q1"), ("q0", "b", "q1")]


def test_epsilon_edges_are_labelled_and_styled():
    nfa = parse_and_build("NFA", "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3")
    assert_diagram_matches(nfa)
    _, edges = parse_dot(automaton_to_dot(nfa))
    epsilon = [attrs for source, _, attrs in edges if attrs.get("label") == "ε"]
    assert len(epsilon) == 2 and all(attrs["style"] == "dashed" for attrs in epsilon)
    assert "None" not in automaton_to_dot(nfa) and "null" not in automaton_to_dot(nfa)


def test_self_loops_for_symbols_and_epsilon():
    nfa = make(NFA, ["q0", "q1"], "a", "q0", ["q1"], {("q0", "a"): {"q0", "q1"}, ("q1", None): {"q1"}})
    _, _, transitions = diagram_of(nfa)
    assert ("q0", "a", "q0") in transitions and ("q1", None, "q1") in transitions


def test_cycles_terminate_and_are_complete():
    nfa = make(NFA, ["a", "b", "c"], "x", "a", ["c"],
               {("a", None): {"b"}, ("b", None): {"c"}, ("c", None): {"a"}, ("c", "x"): {"a"}})
    assert_diagram_matches(nfa)


# --- H–I: dead states and empty alphabets ----------------------------------------

def test_dead_state_and_its_loops_are_drawn():
    dfa = build_exact_string_dfa("ab", {"a", "b"})
    assert_diagram_matches(dfa)
    _, _, transitions = diagram_of(dfa)
    assert ("q3", "a", "q3") in transitions and ("q3", "b", "q3") in transitions


def test_empty_alphabet():
    for automaton in (regex_to_nfa("ε"), build_exact_string_dfa("", set()), make(NFA, ["only"], "", "only", [], {})):
        assert_diagram_matches(automaton)


# --- J–K: names and symbols are escaped safely ------------------------------------

def test_arbitrary_state_names_keep_one_node_each():
    nfa = parse_and_build(
        "NFA", "a,b", "start,state-final,S_1,A.b,x'y,q10,q2", "start", "state-final,q10",
        "start,a,state-final\nstate-final,b,S_1\nS_1,ε,A.b\nA.b,a,x'y\nx'y,b,q10\nq10,a,q2\nq2,ε,start",
    )
    assert_diagram_matches(nfa)
    nodes, _ = parse_dot(automaton_to_dot(nfa))
    assert all(re.fullmatch(r"s\d+|start", node) for node in nodes)  # internal ids only
    # Numeric ordering: q2 gets its id before q10.
    by_label = {attrs["label"]: node for node, attrs in nodes.items()}
    assert int(by_label["q2"][1:]) < int(by_label["q10"][1:])


@pytest.mark.parametrize("symbol", ["|", "*", ".", "\\", '"', "<", ">", "{", "[", "#", ";", "="])
def test_punctuation_symbols_are_literal_labels(symbol):
    dfa = build_exact_string_dfa(symbol, {symbol})
    assert_diagram_matches(dfa)


def test_escaped_regex_literal_labels():
    nfa = regex_to_nfa(r"a\|b\\c\*")
    _, _, transitions = diagram_of(nfa)
    assert {symbol for _, symbol, _ in transitions} == {"a", "|", "b", "\\", "c", "*", None}


# --- L: determinism ---------------------------------------------------------------

def test_dot_is_identical_for_equivalent_automata():
    forward = make(NFA, ["q0", "q1", "q10", "q2"], "ab", "q0", ["q10", "q2"],
                   {("q0", "a"): {"q1", "q2"}, ("q1", "b"): {"q10"}, ("q0", None): {"q10"}})
    backward = make(NFA, ["q2", "q10", "q1", "q0"], "ba", "q0", ["q2", "q10"],
                    {("q0", None): {"q10"}, ("q1", "b"): {"q10"}, ("q0", "a"): {"q2", "q1"}})
    assert automaton_to_dot(forward) == automaton_to_dot(backward)
    assert automaton_to_dot(forward) == automaton_to_dot(forward)


def test_direction_option():
    assert "rankdir=TB" in automaton_to_dot(EVEN_ZEROS, direction="TB")
    with pytest.raises(ValueError):
        automaton_to_dot(EVEN_ZEROS, direction="diagonal")


# --- M: large automata ------------------------------------------------------------

def test_size_limit_detection_without_truncation():
    small = regex_to_nfa("(a|b)*abb")
    assert not is_too_large(small)
    big = regex_to_nfa("a*" * 40)  # 160 states
    assert len(big.states) > MAX_DIAGRAM_STATES and is_too_large(big)
    # The DOT source is still complete, so the download contains the whole automaton.
    assert_diagram_matches(big)
    many_edges = regex_to_dfa("(a|b|c|d|e|f|g|h|i|j|k|l|m|n|o|p|q|r|s|t)*a(a|b)")
    assert len(many_edges.transition_list()) > MAX_DIAGRAM_EDGES and is_too_large(many_edges)


# --- N: optional server-side rendering --------------------------------------------

@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz 'dot' executable is not installed")
def test_dot_executable_accepts_generated_source():
    for automaton in (regex_to_nfa("(a|b)*abb"), regex_to_dfa("(a|b)*abb"), build_exact_string_dfa('"\\', {'"', "\\"})):
        output = subprocess.run(["dot", "-Tsvg"], input=automaton_to_dot(automaton), capture_output=True, text=True)
        assert output.returncode == 0, output.stderr


# --- highlighting hook (restyles only) ------------------------------------------

def test_highlight_restyles_without_changing_structure():
    nfa = regex_to_nfa("(a|b)*abb")
    step = simulate(nfa, "a").steps[1]
    plain = diagram_of(nfa)
    graph = build_graph(nfa, highlight_states=step.active_after, highlight_edges=step.symbol_edges)
    nodes, edges = parse_dot(graph.source)
    labels = {node: attrs["label"] for node, attrs in nodes.items() if node != "start"}
    assert {labels[n] for n, attrs in nodes.items() if attrs.get("penwidth") == "3"} == set(step.active_after)
    highlighted = {(labels[s], attrs["label"], labels[t]) for s, t, attrs in edges if attrs.get("penwidth") == "2.5"}
    assert highlighted == set(step.symbol_edges)
    # Same nodes and edges as the plain diagram.
    shapes, starts, transitions = plain
    assert len(edges) == len(transitions) + 1 and set(labels.values()) == set(shapes)


# --- transition table consistency -----------------------------------------------

def assert_table_matches(automaton: FiniteAutomaton):
    rows = transition_grid_rows(automaton)
    assert len(rows) == len(automaton.states)
    has_epsilon = any(symbol is None for (_, symbol) in automaton.transitions)
    for row in rows:
        marker, _, state = row["State"].rpartition(" ")
        state = state or marker
        assert ("→" in row["State"]) == (state == automaton.initial_state)
        assert ("★" in row["State"]) == (state in automaton.accepting_states)
        symbols = sorted(automaton.alphabet) + ([None] if has_epsilon else [])
        assert len(row) == 1 + len(symbols)
        for symbol in symbols:
            destinations = automaton.transitions.get((state, symbol), set())
            cell = row["ε" if symbol is None else symbol]
            if automaton.machine_type == DFA:
                assert cell == next(iter(destinations))
            elif destinations:
                assert set(cell.strip("{}").split(", ")) == destinations
            else:
                assert cell == "∅"


@pytest.mark.parametrize(
    "automaton",
    [
        EVEN_ZEROS,
        regex_to_nfa("(a|b)*abb"),
        regex_to_dfa("(a|b)*abb"),
        build_exact_string_dfa("aabb", {"a", "b"}),
        convert_nfa_to_dfa(parse_and_build("NFA", "a,b", "A,B,C", "A", "C", "A,a,A\nA,b,A\nA,a,B\nB,a,C\nB,b,C")).dfa,
        parse_and_build("NFA", "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3"),
    ],
    ids=["even-zeros", "regex-nfa", "regex-dfa", "exact", "converted", "manual-epsilon"],
)
def test_diagram_and_table_describe_the_same_automaton(automaton):
    assert_diagram_matches(automaton)
    assert_table_matches(automaton)


def test_summary_text():
    text = diagram_summary(regex_to_dfa("(a|b)*abb"))
    assert text == ("DFA state diagram with 5 states, initial state D0, accepting states D4, "
                    "and 10 transitions over a, b.")
    assert "11 of them ε-transitions" in diagram_summary(regex_to_nfa("(a|b)*abb"))


def test_simulation_results_unchanged_by_visualization():
    nfa = regex_to_nfa("(a|b)*abb")
    before = [simulate(nfa, t).accepted for t in ["abb", "aabb", "abab", ""]]
    automaton_to_dot(nfa)
    build_graph(nfa, highlight_states={"q0"})
    assert [simulate(nfa, t).accepted for t in ["abb", "aabb", "abab", ""]] == before == [True, True, False, False]
