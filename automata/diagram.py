"""Graphviz DOT text for a state diagram.

Start state green, final states blue double circles, other states white.
Active states (during animation) glow yellow; merged states get an orange border.
"""
from .model import EPS

GREEN, BLUE, WHITE = "#22c55e", "#60a5fa", "#ffffff"
ACTIVE, USED, MERGED, LINE = "#facc15", "#facc15", "#f97316", "#94a3b8"


def to_dot(machine, active=(), used=(), merged=(), labels=None):
    """active: states to highlight. used: (src, dst) edges to highlight. labels: extra text under a name."""
    out = [
        "digraph {",
        '  rankdir=LR; bgcolor="transparent"; nodesep=0.25; ranksep=0.3;',
        f'  node [shape=circle, style=filled, fillcolor="{WHITE}", color="{LINE}", '
        'fontname="Helvetica", fontsize=15, fontcolor="#0f172a", margin=0.02];',
        f'  edge [color="{LINE}", fontcolor="#e2e8f0", fontname="Helvetica", fontsize=15, arrowsize=0.7];',
        f'  start [shape=point, width=0.12, color="{GREEN}"];',
        f'  start -> "{machine.start}" [color="{GREEN}", penwidth=2];',
    ]
    for s in machine.states:
        attrs = []
        if s in machine.finals:
            attrs += ["shape=doublecircle", f'fillcolor="{BLUE}"']
        if s == machine.start:
            attrs.append(f'fillcolor="{GREEN}"')
        if s in merged:
            attrs += [f'color="{MERGED}"', "penwidth=3"]
        if s in active:
            attrs += [f'fillcolor="{ACTIVE}"', 'color="#fde047"', "penwidth=4"]
        if labels and s in labels:
            attrs.append(f'label="{s}\\n{labels[s]}", fontsize=10')
        out.append(f'  "{s}" [{", ".join(attrs)}];')

    # Draw one arrow per (src, dst) pair, labelled with all its symbols, e.g. "a, b".
    arrows = {}
    for src, symbol, dst in machine.edges():
        arrows.setdefault((src, dst), []).append(symbol)
    for (src, dst), symbols in arrows.items():
        attrs = [f'label=" {", ".join(symbols)} "']
        if symbols == [EPS]:
            attrs.append("style=dashed")
        if (src, dst) in used:
            attrs += [f'color="{USED}"', f'fontcolor="{USED}"', "penwidth=3"]
        out.append(f'  "{src}" -> "{dst}" [{", ".join(attrs)}];')
    out.append("}")
    return "\n".join(out)
