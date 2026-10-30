"""
Graphviz state diagrams for any FiniteAutomaton.

automaton_to_dot() builds DOT source from the automaton alone (no Graphviz
executable needed); render_automaton_diagram() shows it with st.graphviz_chart,
which lays the graph out in the browser.

Notation:
    circle               ordinary state
    double circle        accepting state
    arrow from a dot     the initial state
    labelled arrow       one transition (source, symbol, destination)
    dashed ε arrow       an ε-transition (consumes no input)

Every transition triple is drawn as its own edge, in the same
(source, symbol, destination) form the simulator records, so a later module
can highlight exactly the edges a simulation step followed. Nodes get stable
internal ids (s0, s1, ... in sorted state order) and the state name is only
used as an escaped label, so user-chosen names can never alter the DOT syntax.
"""

from typing import Iterable, Optional

import graphviz
import streamlit as st

from core.automata import DFA, EPSILON_DISPLAY, FiniteAutomaton

# Diagrams beyond these sizes are slow to lay out and hard to read; the full
# automaton is still shown as a table and offered as a DOT download.
MAX_DIAGRAM_STATES = 80
MAX_DIAGRAM_EDGES = 250

DIRECTIONS = {"Left to right": "LR", "Top to bottom": "TB"}
AUTOMATIC = "Automatic"
LAYOUT_CHOICES = [AUTOMATIC, *DIRECTIONS]
# Long left-to-right diagrams are shrunk to the page width until labels become unreadable,
# while top-to-bottom ones keep their natural size and scroll. Automatic layout therefore
# uses left to right only for small automata.
AUTO_LEFT_TO_RIGHT_MAX_STATES = 15

# Dark-theme palette; meaning never depends on colour alone (shapes and labels carry it).
STATE_FILL = "#1e293b"
STATE_BORDER = "#94a3b8"
TEXT = "#e2e8f0"
INITIAL_BORDER = "#22d3ee"
ACCEPTING_BORDER = "#34d399"
EDGE = "#94a3b8"
EPSILON_EDGE = "#c084fc"
HIGHLIGHT = "#fbbf24"
HIGHLIGHT_FILL = "#422006"

Edge = tuple[str, Optional[str], str]


def node_ids(automaton: FiniteAutomaton) -> dict[str, str]:
    """Stable internal node id for each state: s0, s1, ... in sorted state order."""
    return {state: f"s{index}" for index, state in enumerate(automaton.sorted_states())}


def diagram_edges(automaton: FiniteAutomaton) -> list[Edge]:
    """Every transition as (source, symbol, destination), in stable order (ε last per source)."""
    return automaton.transition_list()


def is_too_large(automaton: FiniteAutomaton) -> bool:
    return len(automaton.states) > MAX_DIAGRAM_STATES or len(diagram_edges(automaton)) > MAX_DIAGRAM_EDGES


def _label(text: str) -> str:
    # graphviz.escape keeps backslashes and <...> literal inside quoted DOT labels.
    return graphviz.escape(text)


def build_graph(
    automaton: FiniteAutomaton,
    *,
    direction: str = "LR",
    highlight_states: Iterable[str] = (),
    highlight_edges: Iterable[Edge] = (),
) -> graphviz.Digraph:
    """
    Build a Digraph for the automaton. The optional highlight arguments only
    restyle existing states and edges; they never add or remove anything.
    """
    if direction not in DIRECTIONS.values():
        raise ValueError(f"direction must be one of {sorted(DIRECTIONS.values())}, not {direction!r}")
    ids = node_ids(automaton)
    marked_states = set(highlight_states)
    marked_edges = set(highlight_edges)

    graph = graphviz.Digraph("automaton")
    graph.attr(rankdir=direction, bgcolor="transparent", nodesep="0.45", ranksep="0.6", pad="0.2")
    graph.attr("node", shape="circle", style="filled", fillcolor=STATE_FILL, color=STATE_BORDER,
               fontcolor=TEXT, fontname="Helvetica", fontsize="13", width="0.55", margin="0.04")
    graph.attr("edge", color=EDGE, fontcolor=TEXT, fontname="Helvetica", fontsize="12", arrowsize="0.8")

    # Invisible start point with an arrow into the initial state.
    graph.node("start", label="", shape="point", width="0.06", color=INITIAL_BORDER)

    for state, node in ids.items():
        attributes = {"id": node}
        if state in automaton.accepting_states:
            attributes.update(shape="doublecircle", color=ACCEPTING_BORDER)
        if state == automaton.initial_state:
            attributes.update(color=INITIAL_BORDER, penwidth="2")
        if state in marked_states:
            # Restyle only: an accepting state keeps its double circle.
            attributes.update(color=HIGHLIGHT, fillcolor=HIGHLIGHT_FILL, penwidth="3")
        graph.node(node, label=_label(state), **attributes)

    graph.edge("start", ids[automaton.initial_state], color=INITIAL_BORDER, penwidth="1.5")

    for index, (source, symbol, destination) in enumerate(diagram_edges(automaton)):
        attributes = {"id": f"e{index}"}
        if symbol is None:
            attributes.update(label=EPSILON_DISPLAY, color=EPSILON_EDGE, fontcolor=EPSILON_EDGE, style="dashed")
        else:
            attributes["label"] = _label(symbol)
        if (source, symbol, destination) in marked_edges:
            attributes.update(color=HIGHLIGHT, penwidth="2.5")
        graph.edge(ids[source], ids[destination], **attributes)
    return graph


def automaton_to_dot(automaton: FiniteAutomaton, *, direction: str = "LR", **highlight) -> str:
    """DOT source for the automaton's state diagram."""
    return build_graph(automaton, direction=direction, **highlight).source


def diagram_summary(automaton: FiniteAutomaton) -> str:
    """Plain-text description of the diagram (used as alt text)."""
    accepting = ", ".join(sorted(automaton.accepting_states)) or "none"
    symbols = ", ".join(sorted(automaton.alphabet)) or "no input symbols"
    edges = diagram_edges(automaton)
    epsilon = sum(1 for _, symbol, _ in edges if symbol is None)
    kind = "DFA" if automaton.machine_type == DFA else "NFA"
    text = (
        f"{kind} state diagram with {len(automaton.states)} states, initial state {automaton.initial_state}, "
        f"accepting states {accepting}, and {len(edges)} transitions over {symbols}"
    )
    return text + (f", {epsilon} of them ε-transitions." if epsilon else ".")


def layout_direction(automaton: FiniteAutomaton, choice: str = AUTOMATIC) -> str:
    """Graphviz rankdir for a layout choice; Automatic depends only on the automaton's size."""
    if choice in DIRECTIONS:
        return DIRECTIONS[choice]
    return "LR" if len(automaton.states) <= AUTO_LEFT_TO_RIGHT_MAX_STATES else "TB"


def render_layout_control() -> None:
    """One app-wide choice of diagram direction."""
    st.radio("Diagram layout", LAYOUT_CHOICES, key="diagram_direction",
             help=f"Automatic draws automata with up to {AUTO_LEFT_TO_RIGHT_MAX_STATES} states left to right "
                  "and larger ones top to bottom, so their labels stay readable.")


LEGEND = (
    "**Reading the diagram:** circle = state · double circle = accepting state · "
    "arrow from the small dot = initial state · labelled arrow = transition on that symbol · "
    "dashed **ε** arrow = moves without reading input · an arrow back to the same state is a self-loop."
)


def render_automaton_diagram(automaton: FiniteAutomaton, *, key: str, title: Optional[str] = None,
                             file_name: Optional[str] = None, highlight_states: Iterable[str] = (),
                             highlight_edges: Iterable[Edge] = ()) -> None:
    """
    Show the state diagram (or a size notice) plus a DOT download. `key` must be unique
    on the page. Highlights only restyle the drawn states and edges; the download is
    always the plain diagram of the complete automaton.
    """
    if title:
        st.markdown(f"#### {title}")
    kind = "dfa" if automaton.machine_type == DFA else "nfa"
    file_name = file_name or f"finite-trace-{kind}.dot"
    highlight_states, highlight_edges = tuple(highlight_states), tuple(highlight_edges)
    highlighted = bool(highlight_states or highlight_edges)
    with st.container(border=True):
        direction = layout_direction(automaton, st.session_state.get("diagram_direction", AUTOMATIC))
        dot = automaton_to_dot(automaton, direction=direction)
        shown = automaton_to_dot(automaton, direction=direction, highlight_states=highlight_states,
                                 highlight_edges=highlight_edges) if highlighted else dot
        if is_too_large(automaton):
            st.warning(
                f"This automaton has {len(automaton.states)} states and {len(diagram_edges(automaton))} "
                f"transitions, more than the diagram limit of {MAX_DIAGRAM_STATES} states or "
                f"{MAX_DIAGRAM_EDGES} transitions. No partial diagram is shown; the full transition "
                "table is below and the complete DOT source can be downloaded.",
                icon="ℹ️",
            )
        else:
            alt = diagram_summary(automaton)
            if highlighted:
                active = ", ".join(sorted(highlight_states)) or "none"
                alt += f" Highlighted active states: {active}."
            st.graphviz_chart(shown, alt=alt)
            st.caption(LEGEND + (" **Amber** = active states and the transitions just used." if highlighted else ""))
        st.download_button(
            "Download DOT",
            data=dot,
            file_name=file_name,
            mime="text/vnd.graphviz",
            key=f"dot_{key}",
            on_click="ignore",
            help="Graphviz source of the complete diagram; open it in any Graphviz viewer.",
        )
