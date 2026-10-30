"""
End-to-end checks across modules (Module 09).

1. User journeys through the real interface (AppTest): build -> diagram/table ->
   convert -> simulate -> step through playback, for every input mode.
2. Fixed-seed randomized tests of the core pipeline (parse -> Thompson ->
   subset construction -> simulate) against independent oracles: Python's re
   module on compatible expressions, and a brute-force path search for random
   hand-written NFAs. Seeds are fixed, so any failure is reproducible.
"""

import itertools
import random
import re

import pytest

from core.converter import convert_nfa_to_dfa, regex_to_dfa
from core.manual_builder import parse_and_build
from core.simulator import simulate
from core.thompson import regex_to_nfa
from test_animation_app import frame, press
from test_app import builder_dfa, convert_in_app, frame_with_column, generate_in_app, run_app
from test_app_modes import EPSILON_NFA, EVEN_ZEROS, generate_rule, set_manual
from test_simulator_app import simulate_saved, verdicts
from test_visualizer import parse_dot
from ui.visualizer import automaton_to_dot


def charts(app):
    return [chart.proto.spec for chart in app.get("graphviz_chart")]


def highlighted(spec):
    nodes, _ = parse_dot(spec)
    return {a["label"] for n, a in nodes.items() if a.get("penwidth") == "3"}


def simulate_builder(app, label_part, text):
    return simulate_saved(app, "sim_builder", label_part, text)


# --- 1. user journeys ----------------------------------------------------------------

def test_workflow_1_regex_to_dfa_to_animated_simulation():
    app = builder_dfa(run_app(), "(a|b)*abb")
    dfa = regex_to_dfa("(a|b)*abb")
    assert charts(app) == [automaton_to_dot(dfa)]
    table = frame_with_column(app, "State")
    assert len(table) == 5 and list(table.columns) == ["State", "a", "b"]
    app = simulate_builder(app, "Regular Expression → DFA", "aabb")
    assert verdicts(app)[0]
    seen = [highlighted(charts(app)[-1])]
    for _ in range(4):
        app = press(app, "next", "sim_builder_outcome_playback")
        seen.append(highlighted(charts(app)[-1]))
    assert seen == [{"D0"}, {"D1"}, {"D1"}, {"D3"}, {"D4"}]
    assert frame(app) == (4, 4, "Completed")


def test_workflow_2_regex_to_epsilon_nfa():
    app = generate_in_app(run_app(), "(0|1)*01")
    (spec,) = charts(app)
    _, edges = parse_dot(spec)
    assert sum(1 for _, _, a in edges if a.get("label") == "ε") == 10
    app = simulate_builder(app, "Regular Expression → ε-NFA", "1101")
    assert verdicts(app)[0]
    app = simulate_builder(app, "Regular Expression → ε-NFA", "1110")
    assert verdicts(app)[1]


def test_workflow_3_conversion_and_equivalence():
    app = convert_in_app(run_app(), "(0|1)*01")
    mapping = frame_with_column(app, "NFA states")
    assert list(mapping["DFA state"]) == ["→ D0", "D1", "D2", "★ D3"]
    assert len(charts(app)) == 2  # original NFA and converted DFA
    construction, conversion = app.session_state["converter_outcome"][1]
    nfa, dfa = construction.automaton, conversion.dfa
    for length in range(6):
        for letters in itertools.product("01", repeat=length):
            text = "".join(letters)
            assert simulate(nfa, text).accepted == simulate(dfa, text).accepted == text.endswith("01")
    app = simulate_saved(app, "sim_converted", "Converted from regular expression", "0101")
    assert verdicts(app)[0]


def test_workflow_4_language_rule():
    app = generate_rule(run_app(), "0,1", "Ends with", pattern="01")
    assert len(charts(app)) == 1
    app = simulate_builder(app, "Language Rule", "1101")
    assert verdicts(app)[0]
    app = simulate_builder(app, "Language Rule", "011")
    assert verdicts(app)[1]


def test_workflow_5_exact_string():
    app = run_app()
    app.text_input(key="exact_alphabet").input("a,b")
    app.text_input(key="exact_text").input("aabb")
    app.button(key="exact_generate").click()
    app.run()
    app = simulate_builder(app, "Exact String", "aabb")
    assert verdicts(app)[0]
    app = simulate_builder(app, "Exact String", "aabba")
    assert verdicts(app)[1]


def test_workflow_6_manual_dfa():
    app = set_manual(run_app(), EVEN_ZEROS)
    assert len(charts(app)) == 1 and len(frame_with_column(app, "State")) == 2
    app = simulate_builder(app, "Manual Automaton → DFA", "1010")
    assert verdicts(app)[0]
    app = simulate_builder(app, "Manual Automaton → DFA", "000")
    assert verdicts(app)[1]


def test_workflow_7_manual_epsilon_nfa_converted_and_simulated_both_ways():
    app = set_manual(run_app(), EPSILON_NFA)
    _, edges = parse_dot(charts(app)[0])
    assert sorted(a["label"] for s, _, a in edges if s != "start") == ["a", "b", "ε", "ε"]
    app.button(key="convert_manual_button").click()
    app.run()
    assert list(frame_with_column(app, "NFA states")["NFA states"]) == ["{q0, q1, q2}", "{q3}", "∅"]
    for text in ["a", "b", "", "ab", "ba", "aa"]:
        # Each simulator tab keeps its own result on the page, so read each source's own run.
        app = simulate_builder(app, "Manual Automaton → NFA", text)
        source, automaton, from_nfa, _ = app.session_state["sim_builder_outcome"][1]
        assert automaton.machine_type == "NFA" and from_nfa.input_string == text
        app = simulate_saved(app, "sim_converted", "Converted from manual NFA", text)
        _, dfa, from_dfa, _ = app.session_state["sim_converted_outcome"][1]
        assert dfa.machine_type == "DFA"
        assert from_nfa.accepted == from_dfa.accepted == (text in ("a", "b")), text
    app = simulate_builder(app, "Manual Automaton → NFA", "a")
    # Page order is Builder, Simulator, Converter; the animated chart is the one with highlights.
    animated = [highlighted(spec) for spec in charts(app) if highlighted(spec)]
    assert {"q0", "q1", "q2"} in animated  # step 0 of the NFA run: the whole ε-closure


def test_workflow_8_invalid_input_recovery():
    app = builder_dfa(run_app(), "(a|b")
    assert app.error and not app.success and charts(app) == []
    app = builder_dfa(app, "(a|b)*")
    assert not app.error and app.success and len(charts(app)) == 1


def test_workflow_9_stale_input_recovery():
    app = builder_dfa(run_app(), "ab")
    app.text_input(key="regex_input").input("abc").run()
    assert charts(app) == [] and not app.success
    app = builder_dfa(app, "abc")
    assert charts(app) == [automaton_to_dot(regex_to_dfa("abc"))]


# --- 2. randomized core pipeline -------------------------------------------------------

UNION, CONCAT, POSTFIX, ATOM = 1, 2, 3, 4


def _tree(rng, depth):
    if depth == 0 or rng.random() < 0.25:
        return ("atom", rng.choice(["a", "b", "a", "b", "ε", r"\|"]))
    kind = rng.choice(["union", "concat", "concat", "star", "plus", "opt"])
    if kind in ("union", "concat"):
        return (kind, _tree(rng, depth - 1), _tree(rng, depth - 1))
    return (kind, _tree(rng, depth - 1))


def _show(node, rng, need):
    """FiniteTrace text and the equivalent Python regex, with only the parentheses precedence needs."""
    kind = node[0]
    if kind == "atom":
        ft, py, own = node[1], {"ε": "(?:)"}.get(node[1], node[1]), ATOM
    elif kind == "union":
        (l1, p1), (l2, p2) = _show(node[1], rng, UNION), _show(node[2], rng, UNION)
        gap = " " if rng.random() < 0.2 else ""  # whitespace is ignored by the parser
        ft, py, own = f"{l1}{gap}|{gap}{l2}", f"{p1}|{p2}", UNION
    elif kind == "concat":
        (l1, p1), (l2, p2) = _show(node[1], rng, CONCAT), _show(node[2], rng, CONCAT)
        sep = "." if rng.random() < 0.2 else ""  # explicit concatenation
        ft, py, own = f"{l1}{sep}{l2}", f"{p1}{p2}", CONCAT
    else:
        l, p = _show(node[1], rng, ATOM)  # postfix operands are atoms or groups (no a**)
        op = {"star": "*", "plus": "+", "opt": "?"}[kind]
        ft, py, own = f"{l}{op}", f"{p}{op}", POSTFIX
    if own < need:
        return f"({ft})", f"(?:{py})"
    return ft, py


@pytest.mark.parametrize("seed", [11, 22, 33])
def test_random_expressions_match_python_re(seed):
    # FiniteTrace and Python's re share precedence (postfix > concatenation > union), so these
    # minimal-parenthesis expressions translate token by token and re acts as an outside oracle.
    rng = random.Random(seed)
    for _ in range(40):
        ft, py = _show(_tree(rng, rng.randint(1, 5)), rng, UNION)
        oracle = re.compile(py)
        nfa = regex_to_nfa(ft)
        nfa.validate()
        dfa = convert_nfa_to_dfa(nfa).dfa
        dfa.validate(require_complete=True)
        symbols = sorted(nfa.alphabet)
        for length in range(4 if len(symbols) > 2 else 5):
            for letters in itertools.product(symbols, repeat=length):
                text = "".join(letters)
                expected = bool(oracle.fullmatch(text))
                assert simulate(nfa, text).accepted == expected, (seed, ft, text)
                assert simulate(dfa, text).accepted == expected, (seed, ft, text)
            if not symbols:
                break


def _accepts_by_search(rows, start, accepting, text):
    """Depth-first search over (state, position), following ε-moves; no closures or subsets."""
    seen, stack = set(), [(start, 0)]
    while stack:
        state, pos = stack.pop()
        if (state, pos) in seen:
            continue
        seen.add((state, pos))
        if pos == len(text) and state in accepting:
            return True
        for source, symbol, target in rows:
            if source == state and symbol == "ε":
                stack.append((target, pos))
            elif source == state and pos < len(text) and symbol == text[pos]:
                stack.append((target, pos + 1))
    return False


@pytest.mark.parametrize("seed", [5, 6])
def test_random_manual_nfas_match_path_search(seed):
    names = ["S", "A", "b1", "state-x", "q_9", "Z.z", "m'", "q10", "q2"]
    rng = random.Random(seed)
    for _ in range(60):
        states = rng.sample(names, rng.randint(1, 6))
        accepting = rng.sample(states, rng.randint(0, len(states)))
        rows = [(rng.choice(states), rng.choice("abε"), rng.choice(states)) for _ in range(rng.randint(0, 12))]
        nfa = parse_and_build("NFA", "a,b", ",".join(states), states[0], ",".join(accepting),
                              "\n".join(",".join(row) for row in rows))
        dfa = convert_nfa_to_dfa(nfa).dfa
        for length in range(5):
            for letters in itertools.product("ab", repeat=length):
                text = "".join(letters)
                expected = _accepts_by_search(rows, states[0], set(accepting), text)
                assert simulate(nfa, text).accepted == simulate(dfa, text).accepted == expected, (seed, rows, text)
