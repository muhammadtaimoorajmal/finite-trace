"""Step 2: Thompson's construction (postfix RE -> ε-NFA).

Each part of the RE becomes a fragment with ONE start state and ONE final state:
  symbol a :  s --a--> f
  R S      :  R.final --ε--> S.start
  R + S    :  new s --ε--> R.start and S.start;   R.final and S.final --ε--> new f
  R*       :  new s --ε--> R.start and f;          R.final --ε--> R.start and f
"""
from collections import deque

from .model import EPS, Automaton


def wrap(fragment, level):
    """Text of a fragment, in brackets if its operator binds weaker than `level`."""
    text, prec = fragment[2], fragment[3]
    return f"({text})" if prec < level else text


def thompson(postfix):
    """Build the ε-NFA. Returns (nfa, steps); steps lists every fragment that was built."""
    edges = []   # (src, symbol, dst) with plain integer states
    stack = []   # fragments: (start, final, text, precedence 1=union 2=concat 3=atom)
    built = []   # (operation name, fragment), in build order
    counter = iter(range(10**6))  # gives 0, 1, 2, ... as new state numbers

    for token in postfix:
        if token == "*":
            r = stack.pop()
            s, f = next(counter), next(counter)
            edges += [(s, EPS, r[0]), (s, EPS, f), (r[1], EPS, r[0]), (r[1], EPS, f)]
            fragment, operation = (s, f, wrap(r, 3) + "*", 3), "Kleene star"
        elif token == ".":
            right, left = stack.pop(), stack.pop()
            edges.append((left[1], EPS, right[0]))
            fragment, operation = (left[0], right[1], wrap(left, 2) + wrap(right, 2), 2), "Concatenation"
        elif token == "+":
            right, left = stack.pop(), stack.pop()
            s, f = next(counter), next(counter)
            edges += [(s, EPS, left[0]), (s, EPS, right[0]), (left[1], EPS, f), (right[1], EPS, f)]
            fragment, operation = (s, f, f"{left[2]} + {right[2]}", 1), "Union"
        else:
            s, f = next(counter), next(counter)
            edges.append((s, token, f))
            fragment, operation = (s, f, token, 3), f"Symbol '{token}'"
        stack.append(fragment)
        built.append((operation, fragment))

    start, final = stack[-1][0], stack[-1][1]

    # Rename states q0, q1, ... in breadth-first order from the start state, so q0 is the start.
    outgoing = {}
    for src, symbol, dst in edges:
        outgoing.setdefault(src, []).append(dst)
    names, queue = {start: "q0"}, deque([start])
    while queue:
        for dst in outgoing.get(queue.popleft(), []):
            if dst not in names:
                names[dst] = f"q{len(names)}"
                queue.append(dst)

    symbols = sorted({symbol for _, symbol, _ in edges if symbol != EPS})
    nfa = Automaton(list(names.values()), symbols, "q0", {names[final]})
    for src, symbol, dst in edges:
        nfa.add(names[src], symbol, names[dst])

    steps = [
        {"Step": i, "Operation": op, "Sub-expression": frag[2],
         "Start state": names[frag[0]], "Final state": names[frag[1]]}
        for i, (op, frag) in enumerate(built, start=1)
    ]
    return nfa, steps
