"""Step 2: NFA -> DFA by subset construction (the method from class).

1. Start with Q' = {q0}.
2. For each set in Q' and each symbol, the next set is the union of the NFA moves
   of all its states.
3. If that set is not in Q' yet, add it to Q' (the empty set φ is the dead state).
4. A DFA state is final if its set contains a final state of the NFA.
"""
from .model import Automaton, set_name


def move(nfa, states, symbol):
    """Union of the NFA moves of every state in `states` on `symbol`."""
    return frozenset(q for p in states for q in nfa.next(p, symbol))


def nfa_to_dfa(nfa):
    """Return (dfa, rows). rows[i] explains how row i of the DFA table was found."""
    start = frozenset({nfa.start})
    names = {start: set_name(start, nfa.states)}  # NFA set -> DFA state name
    queue = [start]                               # sets whose row is not done yet
    dfa = Automaton([], nfa.alphabet, names[start], set(), is_dfa=True)
    rows = []

    while queue:
        current = queue.pop(0)
        row = {"state": names[current], "work": [], "new": []}
        for symbol in nfa.alphabet:
            target = move(nfa, current, symbol)
            if target not in names:  # Step 3: a new DFA state
                names[target] = set_name(target, nfa.states)
                queue.append(target)
                row["new"].append(names[target])
            dfa.add(names[current], symbol, names[target])
            # e.g.  δ({q1,q6}, b) = δ(q1,b) ∪ δ(q6,b) = {q1} ∪ {q7} = {q1,q7}
            parts = sorted(current, key=nfa.states.index)
            row["work"].append(
                f"δ({names[current]}, {symbol}) = " + " ∪ ".join(f"δ({p},{symbol})" for p in parts)
                + " = " + " ∪ ".join(nfa.show(nfa.next(p, symbol)) for p in parts)
                + f" = {names[target]}")
        rows.append(row)

    dfa.states = list(names.values())
    dfa.finals = {name for s, name in names.items() if s & nfa.finals}  # Step 4
    return dfa, rows


def partial(dfa, rows, k):
    """The DFA as it looks after the first k rows are done (for the step-by-step animation)."""
    shown = [dfa.start] + [s for row in rows[:k] for s in row["new"]]
    part = Automaton(shown, dfa.alphabet, dfa.start, dfa.finals & set(shown), is_dfa=True)
    for row in rows[:k]:
        for symbol in dfa.alphabet:
            for dst in dfa.next(row["state"], symbol):
                part.add(row["state"], symbol, dst)
    return part
