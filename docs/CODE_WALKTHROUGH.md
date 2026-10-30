# FiniteTrace Code Walkthrough

A guided tour of the source code for someone who knows basic Python but is new to automata software. Every name below is a real function, class or file in this repository, and every example can be run from the project root with the virtual environment's Python.

For the big picture, see [ARCHITECTURE.md](ARCHITECTURE.md). For using the app, see [USER_GUIDE.md](USER_GUIDE.md).

## 1. The automaton model: `core/automata.py`

Every automaton in FiniteTrace, whether DFA or NFA and wherever it came from, is a `FiniteAutomaton`:

```python
from core.automata import FiniteAutomaton

nfa = FiniteAutomaton(
    machine_type="NFA",
    states={"q0", "q1", "q2"},
    alphabet={"a", "b"},
    initial_state="q0",
    accepting_states={"q2"},
    transitions={
        ("q0", "a"): {"q0", "q1"},   # nondeterminism: two destinations
        ("q0", "b"): {"q0"},
        ("q1", "b"): {"q2"},
        ("q1", None): {"q2"},        # ε-transition: the symbol is None
    },
)
nfa.validate()                        # raises AutomatonValidationError if anything is wrong
print(nfa.get_destinations("q0", "a"))  # {'q0', 'q1'}
print(nfa.transition_list())          # every arrow as (source, symbol, destination), in stable order
```

- **States, alphabet, accepting states** are Python sets.
- **Transitions** map `(state, symbol)` to a *set* of destinations. A DFA has exactly one destination per state and symbol; an NFA may have none, one or several.
- **ε** is `None`. The character `ε` is only used when displaying, so the letter `e` is never confused with it.
- `validate(require_complete=True)` checks that every referenced state exists and every symbol is in the alphabet. For a DFA it also checks there are no ε-moves, no nondeterminism and no missing transitions.
- `state_sort_key` sorts names like a person would (`q2` before `q10`), so tables and diagrams always appear in the same order.

## 2. Parsing regular expressions: `core/regex_parser.py`

`parse_regex` runs four small stages:

1. `tokenize`: turns characters into `Token(kind, value, position)` objects. `|` becomes `UNION`, `\|` becomes a literal `|`, and `ε`/`λ` become `EPSILON`.
2. `check_syntax`: checks each token against the one before it and matches parentheses with a stack, raising `RegexSyntaxError` with a 1-based position.
3. `insert_concatenation`: inserts an explicit `.` wherever two operands touch (`ab` becomes `a.b`).
4. `to_postfix`: the Shunting-Yard algorithm. Operators come after their operands, and precedence is applied: `* + ?` before `.` before `|`.

```python
from core.regex_parser import parse_regex

parsed = parse_regex("(a|b)*abb")
print(parsed.explicit_form)    # (a|b)*.a.b.b
print(parsed.postfix_form)     # ab|*a.b.b.
print(sorted(parsed.alphabet)) # ['a', 'b']
```

Postfix needs no parentheses and can be evaluated left to right with a stack, which is exactly what Thompson's construction does next.

## 3. Thompson's construction: `core/thompson.py`

`construct_nfa(parsed)` reads the postfix tokens with a **stack of fragments**. An `NFAFragment` is a partial NFA with one entry state (`start`) and one exit state (`end`). The private `_Builder` class creates states `q0, q1, …` and records transitions:

| Token | `_Builder` method | Effect |
| --- | --- | --- |
| symbol / ε | `symbol_fragment` | two new states and one arrow |
| `.` | `concatenate` | ε-arrow from the first fragment's end to the second's start |
| `\|` | `union` | new start and end states, with ε-arrows into and out of both fragments |
| `*` `+` `?` | `repeat(allow_skip, allow_loop)` | `*` = skip + loop, `+` = loop only, `?` = skip only |

At the end exactly one fragment must remain: its `start` is the initial state and its `end` the accepting state. `construct_nfa` returns a `ConstructionResult` with the `automaton` and a `steps` trace (one `ConstructionStep` per token).

```python
from core.thompson import regex_to_nfa

nfa = regex_to_nfa("ab|c")
print(len(nfa.states), nfa.initial_state, nfa.accepting_states)  # 8 q6 {'q7'}
```

## 4. NFA to DFA: `core/converter.py`

- `epsilon_closure(nfa, states)`: every state reachable using only ε-arrows. It uses an iterative worklist, so ε-cycles cannot loop forever.
- `move(nfa, states, symbol)`: every state reachable by reading exactly one `symbol`. It never follows ε.
- `convert_nfa_to_dfa(nfa)`: subset construction. `D0 = ε-closure({initial})`, then for each discovered set S and each symbol x, the next state is `ε-closure(move(S, x))`. A set seen for the first time becomes `D1`, `D2`, … and goes into a queue.

A DFA state *is* a set of NFA states, because "the NFA could be in any of these states" is a single, deterministic situation. A set is accepting if it contains **any** accepting NFA state. The empty set `∅` is the **dead state**: it is non-accepting and loops to itself on every symbol, and it is only created when it is reachable.

```python
from core.converter import convert_nfa_to_dfa, format_subset
from core.thompson import regex_to_nfa

result = convert_nfa_to_dfa(regex_to_nfa("(a|b)*abb"))
for name, subset in result.state_mapping.items():
    print(name, format_subset(subset))
print(result.dfa.accepting_states)   # {'D4'}
```

The DFA is equivalent to the NFA but **not minimized**; FiniteTrace does not implement DFA minimization.

## 5. Language rules: `core/language_builder.py`

`build_language(rule, alphabet, pattern=..., symbol=..., count=...)` builds a complete DFA directly, using a general algorithm per rule:

- **Starts with:** a chain of states for the prefix, a dead state for a mismatch, and the final state loops on everything.
- **Ends with / contains:** pattern-matching states. State *i* means "the last *i* symbols are the first *i* of the pattern". `_longest_prefix_suffix` gives the next state, the idea behind the Knuth–Morris–Pratt automaton, so overlapping patterns like `aba` in `ababa` work. For *contains*, the full-match state is absorbing.
- **Does not contain / does not end with:** the same DFA with accepting and non-accepting states swapped. This is valid because the DFA is complete.
- **Even / odd count:** two parity states.
- **Exactly k:** states 0…k plus an overflow state.

`build_exact_string(text, alphabet)` builds the chain for one literal string. `as_nfa(dfa)` relabels a copy of a DFA as an NFA, since every DFA is also an NFA.

```python
from core.language_builder import ENDS_WITH, build_language_dfa
from core.simulator import accepts

dfa = build_language_dfa(ENDS_WITH, {"0", "1"}, pattern="01")
print(accepts(dfa, "1101"), accepts(dfa, "011"))   # True False
```

## 6. Manual automata: `core/manual_builder.py`

`parse_manual_definition` turns the form's text into a `ManualDefinition`. It splits comma-separated lists, reads one `source,symbol,destination` row per line, maps `ε`/`λ` to `None`, and reports problems with line numbers. A DFA is rejected if a row conflicts with an earlier one. `build_manual_automaton` builds and validates the `FiniteAutomaton`; a DFA must be complete, and missing pairs are listed rather than silently filled in. `parse_and_build` does both.

```python
from core.manual_builder import parse_and_build

nfa = parse_and_build("NFA", "a,b", "q0,q1,q2,q3", "q0", "q3", "q0,ε,q1\nq0,ε,q2\nq1,a,q3\nq2,b,q3")
print(nfa.get_destinations("q0", None))   # {'q1', 'q2'}
```

## 7. Simulation: `core/simulator.py`

`simulate(automaton, text)` keeps a **set of active states**:

```
step 0:        active = ε-closure({initial})
each symbol:   active = ε-closure(move(active, symbol))
accepted   =   active contains an accepting state, after the whole input
```

For a DFA the set always holds exactly one state, the current state. For an NFA it holds every state any path could be in, so all paths are followed at once. Each step is a `SimulationStep` (`index`, `position`, `symbol`, `active_before`, `symbol_edges`, `moved_to`, `epsilon_edges`, `active_after`, `explanation`), and the whole run is a `SimulationResult`. `accepts` is `simulate(...).accepted`. Characters outside the alphabet raise `SimulationInputError`; that is different from a rejection.

```python
from core.simulator import simulate
from core.thompson import regex_to_nfa

result = simulate(regex_to_nfa("(a|b)*abb"), "aabb")
print(result.accepted)                                      # True
print([sorted(step.active_after) for step in result.steps][-1])
```

## 8. Diagrams: `ui/visualizer.py`

`automaton_to_dot(automaton)` writes Graphviz DOT text:

- Each state is a node with an internal id (`s0`, `s1`, …) and its name as an escaped label.
- Accepting states use `shape=doublecircle`.
- An invisible `start` point has an arrow into the initial state.
- Every `(source, symbol, destination)` becomes one labelled edge; ε-edges are labelled `ε` and dashed.

`render_automaton_diagram` passes the DOT to `st.graphviz_chart`, which lays it out **in the browser**, so no Graphviz program is needed on the server. `layout_direction` picks left-to-right for up to 15 states and top-to-bottom for larger automata.

```python
from core.converter import regex_to_dfa
from ui.visualizer import automaton_to_dot

print(automaton_to_dot(regex_to_dfa("ab"))[:60])
```

## 9. Playback: `ui/animation.py`

- **Frames:** each frame is one `SimulationStep`. `frame_highlights(simulation, i)` returns that step's active states and its symbol and ε edges, which are passed to `build_graph(..., highlight_states=..., highlight_edges=...)`. Highlighting only restyles existing nodes and edges.
- **Controller:** `PlaybackState` (`current_step`, `playing`, `seconds_per_step`, `last_advance`, `run_id`) lives in `st.session_state`, which is per browser session and survives Streamlit's reruns. The functions `start_playback`, `pause_playback`, `next_step`, `previous_step`, `reset_playback`, `replay_playback`, `set_speed` and `advance_playback` are plain Python. The time is passed in as `now`, which makes them easy to test.
- **Timer:** `render_animation` wraps the panel in `st.fragment(run_every=...)`. Only that panel reruns on a timer, about four times per step, and only while playing. `advance_playback` moves at most one frame per rerun, and only once a full interval has passed.

## 10. Tests: `tests/`

- **Unit tests** cover each core module.
- **Oracle checks** compare automata with independent oracles on every short string: plain Python checks such as `text.endswith(...)`, Python's `re` on compatible expressions, and a brute-force NFA path search.
- **Interface tests** drive the real app through Streamlit's `AppTest` (`tests/test_*_app.py`).
- **Integration tests** (`tests/test_integration.py`) run whole user journeys and fixed-seed randomized checks.
- **Diagram tests** read the generated DOT back and compare it with the automaton, so a missing or invented transition fails a test.
- **Browser checks:** every release was also checked in a real Chrome browser.
- **CI:** GitHub Actions runs everything on Python 3.11 and 3.13.

## Questions and answers

1. **Why Python?** The algorithms are set and dictionary manipulations, which Python expresses clearly, and the code is meant to be read and learned from.
2. **Why Streamlit?** It turns a Python script into an interactive web app, with no separate frontend, and supports the session state and timed fragments that playback needs.
3. **Why Graphviz?** Laying out circles and curved arrows without overlaps is a hard problem that Graphviz's `dot` layout already solves well. FiniteTrace only writes DOT text; the browser draws it.
4. **DFA vs NFA?** A DFA has exactly one next state for every state and symbol. An NFA may have zero, one or several, and may have ε-moves.
5. **Why can an NFA have several destinations?** The definition allows a choice; the NFA accepts if *any* sequence of choices leads to an accepting state. In code, destinations are a set.
6. **What is an ε-transition?** A move that consumes no input. It is stored with the symbol `None`.
7. **What is ε-closure?** All states reachable from a set using only ε-moves: `epsilon_closure` in `core/converter.py`.
8. **What does `move` do?** It collects every state reachable from a set by reading one given symbol, without following ε.
9. **What is Thompson's construction?** A way to build an ε-NFA from a regular expression by combining small fragments, one per operator (`core/thompson.py`).
10. **Why convert the regex to postfix?** In postfix, each operator comes after its operands, so a single left-to-right pass with a stack can build the NFA without dealing with precedence or parentheses.
11. **What is the fragment stack for?** It holds the partial NFAs built so far; each operator pops its operands and pushes the combined fragment.
12. **What is subset construction?** The algorithm in `convert_nfa_to_dfa`. It builds a DFA whose states are sets of NFA states, exploring only reachable sets.
13. **Why does a DFA state represent a set of NFA states?** Knowing *every* state the NFA could be in after some input is a single, deterministic fact, so that set can serve as one DFA state.
14. **How does the dead state work?** When no NFA state can move on a symbol, the result is the empty set. That becomes one non-accepting DFA state that loops to itself on every symbol.
15. **How is acceptance checked?** After the whole input, the final active set is intersected with the accepting states; a non-empty result means accepted.
16. **Why only after the full string?** Acceptance is defined on the whole input. Passing through an accepting state midway (as with `abba` for `(a|b)*abb`) does not count.
17. **How is the empty string handled?** An empty test string means no steps after step 0, so the answer depends only on `ε-closure({initial})`.
18. **Why not train a language model?** Automata have exact definitions and exact algorithms. A learned model could only approximate them, and the goal is correct, explainable results.
19. **How are transition tables generated?** From the same transition dictionary as the diagram: `transition_grid_rows` in `ui/automaton_view.py` builds one row per state and one column per symbol.
20. **How does Graphviz draw the automaton?** `automaton_to_dot` writes nodes and labelled edges; `st.graphviz_chart` lays them out with Graphviz compiled for the browser.
21. **How is the animation tied to real transitions?** Frame *i* highlights exactly `steps[i].active_after` and the recorded `symbol_edges + epsilon_edges`, the same `(source, symbol, destination)` triples that are drawn as edges.
22. **What is Streamlit Session State?** A per-browser-session dictionary that survives the reruns Streamlit performs after every interaction. FiniteTrace stores results there together with the inputs that produced them.
23. **What is a Streamlit fragment?** A function that can rerun on its own, here on a timer (`run_every`), without rerunning the whole page.
24. **How do Play and Pause work?** Play sets `playing=True` and starts the clock; each fragment rerun calls `advance_playback`, which moves one frame once `seconds_per_step` has passed. Pause sets `playing=False`, and the panel is recreated without a timer.
25. **How is the application tested?** See section 10: unit, oracle, interface, integration, diagram and browser tests, run in CI on Python 3.11 and 3.13.
26. **What are the limitations?** Formal regular expressions only; structured rules rather than free English; no DFA minimization; no PDA or Turing machines; documented size limits.
27. **What happens with an invalid regex?** `check_syntax` raises `RegexSyntaxError` with the position, and the app shows the message with a marker under the character instead of a result.
28. **How are manual automata supported?** `core/manual_builder.py` parses and validates the text into a `FiniteAutomaton`, which every other feature accepts.
29. **Why isn't the DFA minimized?** Subset construction already gives an equivalent DFA, and minimization is a separate algorithm outside the project's scope. The DFA can therefore have more states than necessary.
30. **How could the application be extended?** New input methods only need to produce a `FiniteAutomaton`. DFA minimization, for example, would be a new function in `core/` that takes and returns a `FiniteAutomaton`, and conversion, simulation and diagrams would all work with it unchanged.
