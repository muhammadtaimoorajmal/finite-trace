"""Graphviz DOT text for a state diagram.

Start state green, final states blue double circles, other states white.
During an animation the current states glow yellow and the arrows just used turn yellow.
"""
GREEN, BLUE, WHITE, YELLOW, LINE = "#22c55e", "#60a5fa", "#ffffff", "#facc15", "#94a3b8"


def to_dot(machine, active=(), used=(), hide=()):
    """active: states to highlight. used: (src, dst) arrows to highlight.
    hide: states not drawn (the trap state qT; every missing arrow goes there).
    A hidden state still appears while it is active, with only the arrow just used."""
    out = [
        "digraph {",
        '  rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.5;',
        f'  node [shape=circle, style=filled, fillcolor="{WHITE}", color="{LINE}", '
        'fontname="Helvetica", fontsize=13, fontcolor="#0f172a"];',
        f'  edge [color="{LINE}", fontcolor="#e2e8f0", fontname="Helvetica", fontsize=13, arrowsize=0.7];',
        f'  start [shape=point, width=0.12, color="{GREEN}"];',
        f'  start -> "{machine.start}" [color="{GREEN}", penwidth=2];',
    ]
    for s in machine.states:
        if s in hide and s not in active:
            continue
        attrs = []
        if s in machine.finals:
            attrs += ["shape=doublecircle", f'fillcolor="{BLUE}"']
        if s == machine.start:
            attrs.append(f'fillcolor="{GREEN}"')
        if s in active:
            attrs += [f'fillcolor="{YELLOW}"', 'color="#fde047"', "penwidth=4"]
        out.append(f'  "{s}" [{", ".join(attrs)}];')

    # One arrow per (src, dst) pair, labelled with all its symbols, e.g. "a, b".
    arrows = {}
    for src, symbol, dst in machine.edges():
        if (src not in hide and dst not in hide) or (src, dst) in used:
            arrows.setdefault((src, dst), []).append(symbol)
    for (src, dst), symbols in arrows.items():
        attrs = [f'label=" {", ".join(symbols)} "']
        if (src, dst) in used:
            attrs += [f'color="{YELLOW}"', f'fontcolor="{YELLOW}"', "penwidth=3"]
        out.append(f'  "{src}" -> "{dst}" [{", ".join(attrs)}];')
    out.append("}")
    return "\n".join(out)
